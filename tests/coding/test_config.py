from lightningfish_coding.config import CodingDomainAdapter
from lightningfish_core.models import (
    EnrichedSeed,
    GroundTruthRecord,
    RoundEvent,
    SimulationResult,
)


def _seed() -> EnrichedSeed:
    return EnrichedSeed(
        "coding",
        {"pr_url": "https://github.com/owner/repo/pull/1", "pr_number": 1, "owner": "owner", "repo": "repo"},
        "PR #1: Add auth middleware. 150 lines, python. Tests included.",
        ["owner/repo", "PR#1"], "feature",
        {
            "owner": "owner", "repo": "repo", "pr_number": 1,
            "diff_size_tier": "s", "languages_touched": ["python"],
            "is_test_included": True, "author_pr_history": 5,
            "linked_issue": None, "ci_pass_rate": 0.9,
        },
    )


def _result(final_opinion: float) -> SimulationResult:
    return SimulationResult(
        seed=_seed(), trajectory=[0.1, 0.2, final_opinion],
        round_events=[
            RoundEvent(3, [final_opinion], final_opinion, 0.3, 2, ["a1", "a2"], 0.01)
        ],
        final_distribution=[final_opinion],
        total_tier1_calls=6, total_cost_usd=0.03,
    )


def test_adapter_domain_id():
    assert CodingDomainAdapter().domain_id == "coding"


def test_build_personas_includes_cibot():
    personas = CodingDomainAdapter().build_personas(100)
    assert any(p.archetype == "CIBot" for p in personas)


def test_score_outcome_match_approve():
    adapter = CodingDomainAdapter()
    truth = GroundTruthRecord(data={
        "merged": True, "comment_count": 3,
        "approval_sequence": ["APPROVED"], "ci_pass_rate": 1.0,
    })
    result = adapter.score(_result(0.5), truth)
    assert result.direction_match is True


def test_score_outcome_mismatch():
    adapter = CodingDomainAdapter()
    truth = GroundTruthRecord(data={
        "merged": False, "comment_count": 8,
        "approval_sequence": ["CHANGES_REQUESTED"], "ci_pass_rate": 0.2,
    })
    result = adapter.score(_result(0.5), truth)
    assert result.direction_match is False


def test_prompt_contains_archetype():
    adapter = CodingDomainAdapter()
    persona = adapter.build_personas(10)[0]
    prompt = adapter.agent_system_prompt(_seed(), persona)
    assert persona.archetype in prompt
