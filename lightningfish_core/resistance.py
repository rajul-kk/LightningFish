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


def blend_opinion(
    agent: AgentPersona,
    llm_signal: float,
    social_signal: float,
    override_fn: Callable[[AgentPersona, float], float] | None = None,
) -> float:
    """
    Combine an agent's prior opinion with a fresh signal (typically the LLM's
    judgement this round), governed by the persona's behavioural parameters.

    The new signal displaces the anchor by ``alpha = recency_bias * (1 - resistance)``:
      - high resistance  → alpha → 0 → opinion barely moves (strong anchoring)
      - high recency_bias → alpha → 1 → opinion snaps to the new signal
    ``override_fn`` (e.g. the ShortSeller rule) can raise effective resistance
    when the crowd (``social_signal``) turns against the agent, so contrarians
    dig in instead of capitulating.
    """
    eff_res = compute_effective_resistance(agent, social_signal, override_fn)
    alpha = agent.recency_bias * (1.0 - eff_res)
    updated = (1.0 - alpha) * agent.current_opinion + alpha * llm_signal
    return max(-1.0, min(1.0, updated))
