from unittest.mock import MagicMock, patch

import pytest

from lightningfish_core.models import EnrichedSeed
from lightningfish_hn.early_comments import (
    DEFAULT_EARLY_WINDOW_SECONDS,
    EARLY_COMMENT_THRESHOLD,
    assert_window_is_early,
    early_engagement_prediction,
    enrich_hn_seed_with_early_comments,
    fetch_early_comments,
)
from lightningfish_hn.ground_truth import AGE_CUTOFF_SECONDS

_STORY_CREATED = 1767225600
_WINDOW = DEFAULT_EARLY_WINDOW_SECONDS  # 7200s


def _mock_get(url, **kwargs):
    """Mocks the three Algolia calls. The comment search deliberately returns a
    comment posted well AFTER the window, as if the server-side numericFilters
    had been ignored — the local re-check must drop it."""
    mock = MagicMock()
    params = kwargs.get("params", {})
    tags = str(params.get("tags", ""))

    if tags.startswith("comment,"):
        mock.json.return_value = {"hits": [
            {"author": "early_bird", "comment_text": "This is genuinely useful, nice work.",
             "created_at_i": _STORY_CREATED + 600},
            {"author": "second_voice", "comment_text": "Been waiting for something like this.",
             "created_at_i": _STORY_CREATED + 3000},
            {"author": "latecomer", "comment_text": "Arrived a day later, must not count.",
             "created_at_i": _STORY_CREATED + 50000},
            {"author": "empty_person", "comment_text": "   ",
             "created_at_i": _STORY_CREATED + 100},
        ]}
    elif tags.startswith("story_"):
        mock.json.return_value = {"hits": [{
            "title": "Show HN: A new tool for X",
            "story_text": "I built this over the weekend.",
            "url": "https://example.com/tool",
            "author": "buildername",
            "created_at": "2026-01-01T00:00:00.000Z",
            "created_at_i": _STORY_CREATED,
            "_tags": ["story", "story_12345", "show_hn"],
            # Distinctive sentinels: if either string appears in the seed text,
            # it can only have come from the ground-truth fields.
            "points": 88371,
            "num_comments": 55129,
            "objectID": "12345",
        }]}
    elif "/users/" in url:
        mock.json.return_value = {"username": "buildername", "karma": 4200}
    else:
        mock.json.return_value = {}
    return mock


def test_comments_after_the_window_are_excluded():
    with patch("lightningfish_hn.early_comments.requests.get", side_effect=_mock_get), \
         patch("lightningfish_hn.seed_enricher.requests.get", side_effect=_mock_get):
        comments = fetch_early_comments(12345, _WINDOW, _STORY_CREATED)

    authors = [c["author"] for c in comments]
    assert "early_bird" in authors
    assert "second_voice" in authors
    assert "latecomer" not in authors, (
        "a comment posted after the early window leaked into the seed — this is "
        "the point-in-time invariant the whole experiment rests on"
    )


def test_blank_comments_are_dropped():
    with patch("lightningfish_hn.early_comments.requests.get", side_effect=_mock_get), \
         patch("lightningfish_hn.seed_enricher.requests.get", side_effect=_mock_get):
        comments = fetch_early_comments(12345, _WINDOW, _STORY_CREATED)

    assert all(c["text"].strip() for c in comments)
    assert "empty_person" not in [c["author"] for c in comments]


def test_comments_are_ordered_oldest_first():
    with patch("lightningfish_hn.early_comments.requests.get", side_effect=_mock_get), \
         patch("lightningfish_hn.seed_enricher.requests.get", side_effect=_mock_get):
        comments = fetch_early_comments(12345, _WINDOW, _STORY_CREATED)

    times = [c["created_at_i"] for c in comments]
    assert times == sorted(times)


def test_window_overlapping_settlement_is_rejected():
    with pytest.raises(ValueError, match="overlaps the outcome"):
        assert_window_is_early(AGE_CUTOFF_SECONDS)
    with pytest.raises(ValueError, match="overlaps the outcome"):
        assert_window_is_early(int(AGE_CUTOFF_SECONDS * 0.5))
    with pytest.raises(ValueError):
        assert_window_is_early(0)
    assert_window_is_early(DEFAULT_EARLY_WINDOW_SECONDS)  # must not raise


def test_enriched_seed_never_leaks_points_or_num_comments():
    with patch("lightningfish_hn.early_comments.requests.get", side_effect=_mock_get), \
         patch("lightningfish_hn.seed_enricher.requests.get", side_effect=_mock_get):
        seed = enrich_hn_seed_with_early_comments(12345, _WINDOW)

    assert isinstance(seed, EnrichedSeed)
    assert "points" not in seed.metadata
    assert "num_comments" not in seed.metadata
    # Both values are present in the mocked API response; neither may appear
    # anywhere in the text the agents actually read.
    assert "88371" not in seed.summary
    assert "55129" not in seed.summary
    assert "88371" not in str(seed.metadata)
    assert "55129" not in str(seed.metadata)


def test_enriched_seed_carries_the_early_reaction():
    with patch("lightningfish_hn.early_comments.requests.get", side_effect=_mock_get), \
         patch("lightningfish_hn.seed_enricher.requests.get", side_effect=_mock_get):
        seed = enrich_hn_seed_with_early_comments(12345, _WINDOW)

    assert seed.metadata["early_comment_count"] == 2
    assert seed.metadata["early_window_seconds"] == _WINDOW
    assert "Early community reaction" in seed.summary
    assert "genuinely useful" in seed.summary
    assert "Arrived a day later" not in seed.summary


def test_seed_with_no_early_comments_says_so():
    def _no_comments(url, **kwargs):
        if str(kwargs.get("params", {}).get("tags", "")).startswith("comment,"):
            mock = MagicMock()
            mock.json.return_value = {"hits": []}
            return mock
        return _mock_get(url, **kwargs)

    with patch("lightningfish_hn.early_comments.requests.get", side_effect=_no_comments), \
         patch("lightningfish_hn.seed_enricher.requests.get", side_effect=_no_comments):
        seed = enrich_hn_seed_with_early_comments(12345, _WINDOW)

    assert seed.metadata["early_comment_count"] == 0
    assert "no comments yet" in seed.summary


def test_early_engagement_baseline_splits_on_the_threshold():
    def _seed_with(count):
        return EnrichedSeed(
            domain_id="hn", raw_input={}, summary="", entities=[], event_type="story",
            metadata={"early_comment_count": count},
        )

    assert early_engagement_prediction(_seed_with(EARLY_COMMENT_THRESHOLD)) > 0
    assert early_engagement_prediction(_seed_with(EARLY_COMMENT_THRESHOLD + 5)) > 0
    assert early_engagement_prediction(_seed_with(EARLY_COMMENT_THRESHOLD - 1)) < 0
    assert early_engagement_prediction(_seed_with(0)) < 0


def test_early_engagement_baseline_abstains_on_submission_only_seeds():
    """A seed with no early window must not be silently scored as 'flop' —
    that would make the baseline look good on the wrong data."""
    plain = EnrichedSeed(
        domain_id="hn", raw_input={}, summary="", entities=[], event_type="story",
        metadata={"author_karma": 900},
    )
    assert early_engagement_prediction(plain) == 0.0
