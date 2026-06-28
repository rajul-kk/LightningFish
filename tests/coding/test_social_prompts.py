from __future__ import annotations

from lightningfish_coding.config import CodingDomainAdapter
from lightningfish_core.models import AgentPersona, EnrichedSeed


def _seed() -> EnrichedSeed:
    return EnrichedSeed(
        domain_id="coding",
        raw_input={},
        summary="Add async support to the data pipeline.",
        entities=["pipeline"],
        event_type="pr_review",
        metadata={},
    )


def _persona() -> AgentPersona:
    return AgentPersona(
        unique_id="b1",
        archetype="StaffEngineer",
        opinion_resistance=0.7,
        recency_bias=0.2,
        contrarian_tendency=0.1,
        influence_weight=0.85,
        proportion=0.08,
        herding_coefficient=0.1,
    )


def test_coding_taxonomy_length():
    adapter = CodingDomainAdapter()
    taxonomy = adapter.argument_taxonomy()
    assert len(taxonomy) == 8
    assert "correctness" in taxonomy
    assert "security" in taxonomy


def test_coding_post_prompt_includes_taxonomy():
    adapter = CodingDomainAdapter()
    prompt = adapter.post_system_prompt(_seed(), _persona(), feed=[], viral=None)
    for tag in adapter.argument_taxonomy():
        assert tag in prompt


def test_coding_post_prompt_includes_format_instructions():
    adapter = CodingDomainAdapter()
    prompt = adapter.post_system_prompt(_seed(), _persona(), feed=[], viral=None)
    assert "STANCE:" in prompt
    assert "TAG:" in prompt
    assert "CONFIDENCE:" in prompt
    assert "BLURB:" in prompt
