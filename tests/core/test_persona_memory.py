from __future__ import annotations

from lightningfish_core.persona_memory import PersonaMemoryStore


def test_unscored_archetype_returns_none(tmp_path):
    memory = PersonaMemoryStore(tmp_path / "memory.json")
    assert memory.track_record("hn", "GreybeardCynic") is None


def test_records_accumulate_correct_and_total(tmp_path):
    memory = PersonaMemoryStore(tmp_path / "memory.json")
    memory.record("hn", "GreybeardCynic", correct=True)
    memory.record("hn", "GreybeardCynic", correct=True)
    memory.record("hn", "GreybeardCynic", correct=False)
    assert memory.track_record("hn", "GreybeardCynic") == (2, 3)


def test_domains_and_archetypes_are_isolated(tmp_path):
    memory = PersonaMemoryStore(tmp_path / "memory.json")
    memory.record("hn", "GreybeardCynic", correct=True)
    memory.record("hn", "ShowHNFounder", correct=False)
    memory.record("coding", "GreybeardCynic", correct=False)
    assert memory.track_record("hn", "GreybeardCynic") == (1, 1)
    assert memory.track_record("hn", "ShowHNFounder") == (0, 1)
    assert memory.track_record("coding", "GreybeardCynic") == (0, 1)


def test_window_limits_to_most_recent_n(tmp_path):
    memory = PersonaMemoryStore(tmp_path / "memory.json")
    for _ in range(5):
        memory.record("hn", "GreybeardCynic", correct=True)
    for _ in range(5):
        memory.record("hn", "GreybeardCynic", correct=False)
    # Most recent 5 are all False.
    assert memory.track_record("hn", "GreybeardCynic", window=5) == (0, 5)
    assert memory.track_record("hn", "GreybeardCynic", window=100) == (5, 10)


def test_save_and_reload_round_trips(tmp_path):
    path = tmp_path / "nested" / "memory.json"
    memory = PersonaMemoryStore(path)
    memory.record("hn", "GreybeardCynic", correct=True)
    memory.record("hn", "GreybeardCynic", correct=False)
    memory.save()

    reloaded = PersonaMemoryStore(path)
    assert reloaded.track_record("hn", "GreybeardCynic") == (1, 2)
