"""
Ground truth for the Hacker News domain: a story's current points/num_comments,
served only once the story is settled (>=24h old per design review — HN
front-page dynamics mostly resolve within a day).
"""
from __future__ import annotations

import time

from lightningfish_core.models import GroundTruthRecord

from .seed_enricher import fetch_hn_item

# Direction thresholds. A gap zone between LOW and HIGH is treated as no
# signal (truth_direction returns 0, skipped by the backtest) rather than an
# arbitrary tie-break. Named constants so they're easy to retune once real
# data is seen. Shared with backtest_events.py (balanced sampling) and
# config.py (truth_direction).
POINTS_HIGH = 40
POINTS_LOW = 15
COMMENTS_HIGH = 20
COMMENTS_LOW = 5

AGE_CUTOFF_SECONDS = 24 * 60 * 60


def get_hn_ground_truth(story_id: int) -> GroundTruthRecord | None:
    item = fetch_hn_item(story_id)
    created_at_i = item.get("created_at_i", 0)
    age_seconds = time.time() - created_at_i
    if age_seconds < AGE_CUTOFF_SECONDS:
        return None  # too young — points/comments have not settled yet

    return GroundTruthRecord(data={
        "points": item.get("points", 0),
        "num_comments": item.get("num_comments", 0),
        "created_at_i": created_at_i,
    })
