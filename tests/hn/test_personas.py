import statistics

from lightningfish_core.persona_memory import PersonaMemoryStore
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


def test_no_memory_leaves_metadata_empty():
    personas = build_hn_personas(20)
    assert all(p.metadata == {} for p in personas)


def test_memory_injects_track_record_for_scored_archetype(tmp_path):
    memory = PersonaMemoryStore(tmp_path / "memory.json")
    for _ in range(6):
        memory.record("hn", "GreybeardCynic", correct=True)
    for _ in range(4):
        memory.record("hn", "GreybeardCynic", correct=False)

    personas = build_hn_personas(100, archetype_config={"GreybeardCynic": 1.0}, memory=memory)
    assert all(p.metadata["track_record"] == (6, 10) for p in personas)


def test_memory_is_none_for_an_archetype_never_scored(tmp_path):
    memory = PersonaMemoryStore(tmp_path / "memory.json")  # empty — nothing recorded
    personas = build_hn_personas(20, archetype_config={"GreybeardCynic": 1.0}, memory=memory)
    assert all(p.metadata["track_record"] is None for p in personas)
