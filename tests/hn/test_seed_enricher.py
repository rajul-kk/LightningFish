from unittest.mock import MagicMock, patch

from lightningfish_core.models import EnrichedSeed
from lightningfish_hn.seed_enricher import enrich_hn_seed, fetch_author_karma, fetch_hn_item


def _mock_get(url, **kwargs):
    mock = MagicMock()
    params = kwargs.get("params", {})
    if "/search" in url and str(params.get("tags", "")).startswith("story_"):
        mock.json.return_value = {"hits": [{
            "title": "Show HN: A new tool for X",
            "story_text": "I built this over the weekend because Y.",
            "url": "https://example.com/tool",
            "author": "buildername",
            "created_at": "2026-01-01T00:00:00.000Z",
            "created_at_i": 1767225600,
            "_tags": ["story", "author_buildername", "story_12345", "show_hn"],
            "points": 87,
            "num_comments": 42,
            "objectID": "12345",
        }]}
    elif "/users/" in url:
        mock.json.return_value = {"username": "buildername", "karma": 4200}
    else:
        mock.json.return_value = {}
    return mock


def test_enrich_returns_enriched_seed():
    with patch("lightningfish_hn.seed_enricher.requests.get", side_effect=_mock_get):
        result = enrich_hn_seed(12345)

    assert isinstance(result, EnrichedSeed)
    assert result.domain_id == "hn"
    assert result.metadata["story_id"] == 12345
    assert result.metadata["author"] == "buildername"
    assert result.metadata["author_karma"] == 4200
    assert result.metadata["url_domain"] == "example.com"
    assert result.metadata["tag"] == "show_hn"
    assert "A new tool for X" in result.summary
    assert "built this over the weekend" in result.summary


def test_enriched_seed_never_leaks_outcome_fields():
    # HARD CONSTRAINT: points/num_comments are the prediction target and must
    # never appear in the seed the sim reacts to.
    with patch("lightningfish_hn.seed_enricher.requests.get", side_effect=_mock_get):
        result = enrich_hn_seed(12345)

    assert "points" not in result.metadata
    assert "num_comments" not in result.metadata
    assert "point" not in result.summary.lower()
    assert "comment" not in result.summary.lower()


def test_fetch_hn_item_raises_on_no_hits():
    def empty_get(url, **kwargs):
        mock = MagicMock()
        mock.json.return_value = {"hits": []}
        return mock

    with patch("lightningfish_hn.seed_enricher.requests.get", side_effect=empty_get):
        try:
            fetch_hn_item(999)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


def test_fetch_author_karma_returns_none_on_missing_username():
    assert fetch_author_karma("") is None


def test_fetch_author_karma_parses_response():
    with patch("lightningfish_hn.seed_enricher.requests.get", side_effect=_mock_get):
        assert fetch_author_karma("buildername") == 4200
