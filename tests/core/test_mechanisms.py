"""
Tests for the behavioural mechanisms that the engine now actually applies:
resistance/recency blending and the resistance override. These parameters were
previously inert (only described in prompts), so these tests guard against a
regression back to dead code.
"""
from __future__ import annotations

import uuid

from lightningfish_core.models import AgentPersona
from lightningfish_core.resistance import blend_opinion, compute_effective_resistance


def _agent(resistance: float, recency: float, opinion: float, override=None) -> AgentPersona:
    return AgentPersona(
        unique_id=str(uuid.uuid4()),
        archetype="T",
        opinion_resistance=resistance,
        recency_bias=recency,
        contrarian_tendency=0.0,
        influence_weight=0.5,
        proportion=0.1,
        current_opinion=opinion,
        metadata={"resistance_override_fn": override} if override else {},
    )


def test_high_resistance_barely_moves():
    agent = _agent(resistance=0.95, recency=0.5, opinion=0.0)
    updated = blend_opinion(agent, llm_signal=1.0, social_signal=0.0)
    # alpha = 0.5 * (1 - 0.95) = 0.025 → tiny move toward 1.0
    assert 0.0 < updated < 0.1


def test_low_resistance_high_recency_snaps_to_signal():
    agent = _agent(resistance=0.05, recency=0.95, opinion=0.0)
    updated = blend_opinion(agent, llm_signal=1.0, social_signal=0.0)
    # alpha = 0.95 * 0.95 ≈ 0.90 → most of the way to 1.0
    assert updated > 0.85


def test_blend_stays_in_bounds():
    agent = _agent(resistance=0.0, recency=1.0, opinion=-1.0)
    assert blend_opinion(agent, llm_signal=5.0, social_signal=0.0) <= 1.0
    assert blend_opinion(agent, llm_signal=-5.0, social_signal=0.0) >= -1.0


def _short_seller_override(agent: AgentPersona, social_signal: float) -> float:
    opposing = (social_signal * agent.current_opinion) < 0
    if opposing and abs(social_signal) > 0.6:
        return min(1.0, agent.opinion_resistance * 1.3)
    return agent.opinion_resistance


def test_override_raises_resistance_under_opposing_pressure():
    # Bearish short-seller (opinion < 0) facing a strong bullish crowd (signal > 0).
    agent = _agent(resistance=0.6, recency=0.5, opinion=-0.5, override=_short_seller_override)
    eff = compute_effective_resistance(agent, social_signal=0.8, override_fn=_short_seller_override)
    assert eff > agent.opinion_resistance  # digs in

    # Same agent moves LESS toward a bullish signal than it would without the override.
    with_override = blend_opinion(agent, llm_signal=0.9, social_signal=0.8, override_fn=_short_seller_override)
    plain = _agent(resistance=0.6, recency=0.5, opinion=-0.5)
    without_override = blend_opinion(plain, llm_signal=0.9, social_signal=0.8)
    assert with_override < without_override


def test_override_inactive_when_signal_weak():
    agent = _agent(resistance=0.6, recency=0.5, opinion=-0.5, override=_short_seller_override)
    eff = compute_effective_resistance(agent, social_signal=0.3, override_fn=_short_seller_override)
    assert eff == agent.opinion_resistance
