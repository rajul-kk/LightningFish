from lightningfish_core.models import (
    AgentPersona,
    BacktestResult,
    EnrichedSeed,
)


def test_agent_persona_defaults():
    p = AgentPersona(
        unique_id="a1", archetype="Test",
        opinion_resistance=0.5, recency_bias=0.5,
        contrarian_tendency=0.2, influence_weight=0.6,
        proportion=0.1,
    )
    assert p.current_opinion == 0.0
    assert p.metadata == {}


def test_enriched_seed_scraped_context_defaults_empty():
    seed = EnrichedSeed(
        domain_id="test", raw_input={}, summary="s",
        entities=[], event_type="other", metadata={},
    )
    assert seed.scraped_context == []


def test_backtest_result_fields():
    r = BacktestResult(
        direction_match=True, magnitude_correlation=0.7,
        domain_metric={"price_direction_match": True},
        total_tier1_calls=10, estimated_cost_usd=0.05,
    )
    assert r.direction_match is True
