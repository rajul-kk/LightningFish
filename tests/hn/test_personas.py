import statistics

from lightningfish_hn.personas import build_hn_personas


def test_all_archetypes_present():
    personas = build_hn_personas(500)
    archetypes = {p.archetype for p in personas}
    expected = {
        "CasualLurkerVoter", "EarlyAdopterHypeBeast", "ContrarianSkeptic",
        "DomainExpertPedant", "GreybeardCynic", "ShowHNFounder",
    }
    assert expected == archetypes


def test_proportions_roughly_match_config():
    personas = build_hn_personas(1000)
    lurkers = [p for p in personas if p.archetype == "CasualLurkerVoter"]
    assert 250 <= len(lurkers) <= 350  # ~30% of 1000


def test_opinions_start_near_neutral():
    personas = build_hn_personas(100)
    for p in personas:
        assert -0.3 <= p.current_opinion <= 0.3


def test_within_archetype_parameters_are_jittered():
    personas = build_hn_personas(500)
    lurkers = [p.opinion_resistance for p in personas if p.archetype == "CasualLurkerVoter"]
    assert len(lurkers) > 10
    assert statistics.stdev(lurkers) > 0.01


def test_archetype_config_override_normalizes_proportions():
    personas = build_hn_personas(100, archetype_config={"GreybeardCynic": 1.0})
    assert {p.archetype for p in personas} == {"GreybeardCynic"}
    assert len(personas) == 100
