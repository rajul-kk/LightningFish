from lightningfish_core.resistance import compute_effective_resistance
from lightningfish_core.models import AgentPersona


def _make_agent(resistance: float, opinion: float = 0.3) -> AgentPersona:
    return AgentPersona(
        unique_id="x", archetype="T", opinion_resistance=resistance,
        recency_bias=0.5, contrarian_tendency=0.2, influence_weight=0.5,
        proportion=0.1, current_opinion=opinion,
    )


def test_default_returns_agent_resistance():
    agent = _make_agent(0.7)
    assert compute_effective_resistance(agent, social_signal=0.5) == 0.7


def test_override_fn_is_called():
    agent = _make_agent(0.7)
    result = compute_effective_resistance(
        agent, social_signal=0.8,
        override_fn=lambda a, s: a.opinion_resistance * 1.3,
    )
    assert abs(result - 0.91) < 1e-9


def test_result_clamped_to_one():
    agent = _make_agent(0.9)
    result = compute_effective_resistance(
        agent, social_signal=0.9,
        override_fn=lambda a, s: a.opinion_resistance * 2.0,
    )
    assert result <= 1.0
