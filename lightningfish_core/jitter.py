"""Per-agent parameter jitter so agents within one archetype are not identical.

Real crowds have within-group spread: not every retail trader is equally
reactive. Adding a small perturbation to each persona's parameters gives clusters
internal variance, which makes herding and settling behave less mechanically.
"""
from __future__ import annotations

import random


def jitter(value: float, scale: float = 0.08, lo: float = 0.0, hi: float = 1.0) -> float:
    """Perturb ``value`` by up to ±scale, clamped to [lo, hi]."""
    return max(lo, min(hi, value + random.uniform(-scale, scale)))
