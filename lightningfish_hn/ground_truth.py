"""
Ground truth for the Hacker News domain: a story's current points/num_comments,
served only once the story is settled (>=24h old per design review — HN
front-page dynamics mostly resolve within a day).

DRIFT WARNING. Algolia exposes only a story's *current* totals, never a
historical snapshot, so AGE_CUTOFF_SECONDS is a minimum-age gate and NOT a
measurement window: asking at 24h and asking a week later return different
numbers, and the gap can be large enough to flip an outcome's class. One story
in the sample went from 4 points to 108 four days later (HN's second-chance
pool re-surfaces old submissions), turning a "flop" into a "viral".

Two consequences, both load-bearing for backtests:

1. Every record therefore carries ``measured_at_i`` and
   ``age_at_measurement_s`` so a stale or late measurement is auditable rather
   than silently assumed to be the 24h value.
2. Comparisons across runs MUST reuse one cached measurement. Re-fetching truth
   for a second run silently re-measures and breaks the pairing — see
   ``EventCache.copy_ground_truth_from``.
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

# --- Controversy axis -------------------------------------------------------
# comments-to-points ratio. On HN a thread drawing as many comments as upvotes
# is the classic argument signature; a highly-upvoted story with few comments
# is uncontested approval.
#
# The ratio is meaningless for stories nobody saw — 0 comments on a 1-point
# story is obscurity, not consensus — so MIN_POINTS gates it out rather than
# scoring them as "uncontroversial".
#
# HIGH/LOW were placed either side of the observed median ratio to balance the
# classes, the same label-agnostic reasoning the class-balanced sampler uses.
# They were NOT tuned against any model's accuracy (rule 3 in METHODOLOGY.md).
CONTROVERSY_HIGH = 0.7
CONTROVERSY_LOW = 0.4
CONTROVERSY_MIN_POINTS = 20


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
        # Provenance for the drift problem in the module docstring: when this
        # was measured, and how old the story already was. A record whose age
        # far exceeds AGE_CUTOFF_SECONDS is a late measurement, not a 24h one.
        "measured_at_i": int(time.time()),
        "age_at_measurement_s": int(age_seconds),
    })
