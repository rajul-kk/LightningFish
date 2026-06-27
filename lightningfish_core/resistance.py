from __future__ import annotations

from typing import Callable

from .models import AgentPersona


def compute_effective_resistance(
    agent: AgentPersona,
    social_signal: float,
    override_fn: Callable[[AgentPersona, float], float] | None = None,
) -> float:
    raw = override_fn(agent, social_signal) if override_fn else agent.opinion_resistance
    return min(1.0, max(0.0, raw))
