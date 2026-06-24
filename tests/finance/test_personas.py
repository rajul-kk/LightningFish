import statistics
from lightningfish_finance.personas import build_finance_personas, short_seller_resistance
from lightningfish_core.models import AgentPersona


def test_persona_count_close_to_n():
    personas = build_finance_personas(500)
    assert 490 <= len(personas) <= 510


def test_all_archetypes_present():
    personas = build_finance_personas(500)
    archetypes = {p.archetype for p in personas}
    expected = {
        "ValueInvestor", "MomentumTrader", "RetailFOMO",
        "ShortSeller", "InstitutionalAnalyst", "MacroTourist", "PassiveLurker",
    }
    assert expected == archetypes


def test_proportions_roughly_match_config():
    personas = build_finance_personas(1000)
    retail = [p for p in personas if p.archetype == "RetailFOMO"]
    assert 300 <= len(retail) <= 400


def test_opinions_start_near_neutral():
    personas = build_finance_personas(100)
    for p in personas:
        assert -0.5 <= p.current_opinion <= 0.5


def test_short_seller_resistance_increases_under_pressure():
    agent = AgentPersona(
        unique_id="ss", archetype="ShortSeller",
        opinion_resistance=0.90, recency_bias=0.30,
        contrarian_tendency=0.95, influence_weight=0.70,
        proportion=0.05, current_opinion=-0.8,
    )
    result = short_seller_resistance(agent, social_signal=0.8)
    assert result > agent.opinion_resistance
    assert result <= 1.0


def test_short_seller_resistance_unchanged_when_signal_weak():
    agent = AgentPersona(
        unique_id="ss", archetype="ShortSeller",
        opinion_resistance=0.90, recency_bias=0.30,
        contrarian_tendency=0.95, influence_weight=0.70,
        proportion=0.05, current_opinion=-0.8,
    )
    result = short_seller_resistance(agent, social_signal=0.3)
    assert result == agent.opinion_resistance
