"""
Early-comment enrichment for the Hacker News domain: the first comments a story
received, as a point-in-time-safe leading indicator of reception.

WHY THIS EXISTS. Submission-only seeds hit a measured ceiling: author karma
alone predicts the points direction at 69%, no combination of the other static
fields beats it, and the simulation does not clear it (see ARCHITECTURE.md §10).
Early community reaction is the one signal class that is genuinely different in
kind — dynamic rather than static — and so the one lever with real headroom.

POINT-IN-TIME SAFETY. This module loosens what the seed may contain, so its
constraints are stated explicitly and enforced in code:

- Only comments created within ``window_seconds`` of the story's OWN creation
  are returned. A comment posted at T+30min is genuinely observable at T+30min;
  one posted at T+10h is not, and would leak the future into the seed.
- ``window_seconds`` must stay well below the 24h settlement window, or the
  "early" observation would overlap the outcome it is meant to predict.
  Enforced by ``assert_window_is_early``.
- Points and num_comments are still never read or stored. The comment COUNT
  within the early window is a different quantity from the 24h num_comments
  target (a strict prefix of it), and is legitimately observable at T+window.

THE PREDICTION TASK CHANGES. With early comments the task becomes "given the
submission AND its first N minutes of reaction, predict reception at 24h".
That is strictly easier than the submission-only task and its accuracy numbers
are NOT comparable to submission-only numbers. Any baseline must be given the
same window (see ``early_engagement_prediction``) or the comparison is rigged
in the simulation's favour.

CAVEAT ON THE COMMENTS AXIS. Early comment count is a strict prefix of the 24h
num_comments target, so on that axis it partially self-predicts. Points is the
honest axis for this experiment; treat comments-axis numbers as compromised.
"""
from __future__ import annotations

import html
import re

import requests

from lightningfish_core.models import EnrichedSeed

from .ground_truth import AGE_CUTOFF_SECONDS
from .seed_enricher import _ALGOLIA_BASE, enrich_hn_seed, fetch_hn_item

# Two hours. Long enough that a story which is going to get traction usually
# shows some, short enough to leave 22 of the 24 settlement hours unobserved.
# A first-pass constant, not calibrated — calibrating it against backtest
# accuracy would be fitting the window to the test set.
DEFAULT_EARLY_WINDOW_SECONDS = 2 * 60 * 60

# The early window must be a small fraction of the settlement window, not
# merely less than it: observing 23 of 24 hours would be "early" by the letter
# of the rule while being almost the whole outcome.
_MAX_WINDOW_FRACTION = 0.25

_MAX_EARLY_COMMENTS = 12
_MAX_COMMENT_CHARS = 280

# 2+ comments inside the early window as the traction cutoff. Chosen a priori
# from HN's shape (most submissions get zero discussion at all), deliberately
# NOT tuned against the backtest — a threshold fitted to the test set would
# make this baseline unfairly strong and the comparison meaningless.
EARLY_COMMENT_THRESHOLD = 2

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_comment_text(raw: str) -> str:
    """Algolia returns comment bodies as HTML fragments (``<p>``, ``&#x2F;``).
    Agents read this text directly, so strip the markup rather than making the
    model parse entities."""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def assert_window_is_early(window_seconds: int) -> None:
    """Guard the core point-in-time invariant. Raises rather than clamping: a
    caller asking for a window that overlaps settlement has a broken
    experiment, and silently shrinking it would hide that."""
    if window_seconds <= 0:
        raise ValueError(f"early window must be positive, got {window_seconds}")
    limit = AGE_CUTOFF_SECONDS * _MAX_WINDOW_FRACTION
    if window_seconds > limit:
        raise ValueError(
            f"early window {window_seconds}s exceeds {_MAX_WINDOW_FRACTION:.0%} of the "
            f"{AGE_CUTOFF_SECONDS}s settlement window ({limit:.0f}s). An 'early' "
            f"observation that large overlaps the outcome it predicts."
        )


def fetch_early_comments(
    story_id: int,
    window_seconds: int = DEFAULT_EARLY_WINDOW_SECONDS,
    story_created_at_i: int | None = None,
) -> list[dict]:
    """
    Comments on ``story_id`` posted within ``window_seconds`` of the story's
    creation, oldest first. Returns [] for stories with no early discussion.

    ``story_created_at_i`` may be passed to avoid a redundant story fetch when
    the caller already has the item.
    """
    assert_window_is_early(window_seconds)

    if story_created_at_i is None:
        story_created_at_i = fetch_hn_item(story_id).get("created_at_i", 0)
    if not story_created_at_i:
        return []
    deadline = story_created_at_i + window_seconds

    resp = requests.get(
        f"{_ALGOLIA_BASE}/search",
        params={  # type: ignore[arg-type]
            "tags": f"comment,story_{story_id}",
            "numericFilters": f"created_at_i<={deadline}",
            "hitsPerPage": _MAX_EARLY_COMMENTS,
        },
    )
    data = resp.json()
    hits = data.get("hits", []) if isinstance(data, dict) else []

    comments = []
    for hit in hits:
        created = hit.get("created_at_i") or 0
        text = _clean_comment_text(hit.get("comment_text") or "")
        # Re-check the deadline locally rather than trusting the server filter:
        # this is the invariant the whole experiment rests on.
        if not text or not created or created > deadline:
            continue
        comments.append({
            "author": hit.get("author") or "unknown",
            "text": text[:_MAX_COMMENT_CHARS],
            "created_at_i": created,
            "seconds_after_story": created - story_created_at_i,
        })
    comments.sort(key=lambda c: c["created_at_i"])
    return comments


def early_engagement_prediction(seed: EnrichedSeed) -> float:
    """
    Content-free early-engagement baseline: did this story draw any discussion
    in its first window? This is the bar the simulation must clear to show it
    is reading the comment TEXT rather than just noticing comments exist.
    """
    count = seed.metadata.get("early_comment_count")
    if count is None:
        return 0.0
    return 1.0 if count >= EARLY_COMMENT_THRESHOLD else -1.0


def enrich_hn_seed_with_early_comments(
    story_id: int,
    window_seconds: int = DEFAULT_EARLY_WINDOW_SECONDS,
) -> EnrichedSeed:
    """
    A normal HN seed plus the story's early comment window. Builds on
    ``enrich_hn_seed`` so the submission-only fields stay byte-identical and
    the two seed variants differ by exactly the added reaction section.
    """
    assert_window_is_early(window_seconds)

    seed = enrich_hn_seed(story_id)
    created_at_i = fetch_hn_item(story_id).get("created_at_i", 0)
    comments = fetch_early_comments(story_id, window_seconds, created_at_i)

    window_label = f"{window_seconds // 3600}h" if window_seconds >= 3600 else f"{window_seconds // 60}m"
    if comments:
        lines = "\n".join(f"  [{c['author']}] {c['text']}" for c in comments)
        reaction = (
            f"\n\nEarly community reaction (first {window_label}, "
            f"{len(comments)} comment{'s' if len(comments) != 1 else ''}):\n{lines}"
        )
    else:
        reaction = f"\n\nEarly community reaction (first {window_label}): no comments yet."

    seed.summary += reaction
    seed.metadata["early_comment_count"] = len(comments)
    seed.metadata["early_window_seconds"] = window_seconds
    seed.metadata["early_comments"] = comments
    return seed
