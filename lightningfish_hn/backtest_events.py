"""
Programmatic, class-balanced backtest event source for the Hacker News domain.
Mirrors lightningfish_coding.backtest_events: naively pulling "N most recent
settled stories" risks a degenerate, non-representative split (found on a
different domain's naive sampler this session), so this pulls roughly half
the events above a high threshold and half below a low threshold for a chosen
metric.
"""
from __future__ import annotations

import time

import requests

from lightningfish_core.backtest import BacktestEvent

from .ground_truth import AGE_CUTOFF_SECONDS, COMMENTS_HIGH, COMMENTS_LOW, POINTS_HIGH, POINTS_LOW
from .seed_enricher import enrich_hn_seed

_ALGOLIA_BASE = "https://hn.algolia.com/api/v1"

_THRESHOLDS: dict[str, tuple[int, int]] = {
    "points": (POINTS_HIGH, POINTS_LOW),
    "num_comments": (COMMENTS_HIGH, COMMENTS_LOW),
}


def _search_story_ids(metric_filter: str, count: int) -> list[int]:
    cutoff = int(time.time()) - AGE_CUTOFF_SECONDS
    resp = requests.get(
        f"{_ALGOLIA_BASE}/search_by_date",
        params={  # type: ignore[arg-type]
            "tags": "story",
            "numericFilters": f"created_at_i<{cutoff},{metric_filter}",
            "hitsPerPage": count,
        },
    )
    data = resp.json()
    hits = data.get("hits", []) if isinstance(data, dict) else []
    return [int(h["objectID"]) for h in hits if "objectID" in h]


def pull_hn_events(metric: str = "points", limit: int = 20) -> list[BacktestEvent]:
    """
    Fetch a class-balanced set of up to ``limit`` settled (>=24h old) stories:
    half with ``metric`` >= its high threshold, half < its low threshold.
    ``metric`` is "points" or "num_comments".
    """
    if metric not in _THRESHOLDS:
        raise ValueError(f"Unknown metric {metric!r}; expected one of {list(_THRESHOLDS)}")
    high, low = _THRESHOLDS[metric]
    half = max(1, limit // 2)
    high_ids = _search_story_ids(f"{metric}>={high}", half)
    low_ids = _search_story_ids(f"{metric}<{low}", half)

    # Interleave so a truncated/rate-limited run still sees both classes.
    ids: list[int] = []
    for i in range(max(len(high_ids), len(low_ids))):
        if i < len(high_ids):
            ids.append(high_ids[i])
        if i < len(low_ids):
            ids.append(low_ids[i])

    events: list[BacktestEvent] = []
    for story_id in ids:
        try:
            seed = enrich_hn_seed(story_id)
        except Exception:
            continue  # skip stories we cannot enrich (deleted, API hiccup)
        events.append(BacktestEvent(event_id=f"hn:{story_id}", seed=seed))
    return events
