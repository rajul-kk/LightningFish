from __future__ import annotations
import os
from lightningfish_core.adapter import DomainAdapter
from lightningfish_core.models import (
    EnrichedSeed, AgentPersona, GroundTruthRecord, SimulationResult, BacktestResult,
)
from .personas import build_coding_personas
from .seed_enricher import enrich_coding_seed
from .ground_truth import get_coding_ground_truth


class CodingDomainAdapter(DomainAdapter):
    domain_id = "coding"
    display_name = "Code Review"
    opinion_labels = ("block", "approve")

    def enrich_seed(self, raw_input: dict) -> EnrichedSeed:
        return enrich_coding_seed(
            raw_input["pr_url"],
            github_token=os.environ["GITHUB_TOKEN"],
        )

    def build_personas(
        self,
        n_agents: int,
        archetype_config: dict[str, float] | None = None,
    ) -> list[AgentPersona]:
        return build_coding_personas(n_agents, archetype_config)

    def agent_system_prompt(self, seed: EnrichedSeed, persona: AgentPersona) -> str:
        meta = seed.metadata
        return (
            f"You are a {persona.archetype} on a code review team.\n\n"
            f"Pull request context:\n{seed.summary}\n"
            f"Diff size: {meta.get('diff_size_tier', 'unknown')}. "
            f"Languages: {', '.join(meta.get('languages_touched', []))}. "
            f"Tests included: {meta.get('is_test_included')}. "
            f"Author has {meta.get('author_pr_history', 0)} prior merged PRs.\n\n"
            f"Your characteristics:\n"
            f"- Opinion resistance: {persona.opinion_resistance} (1=rarely changes stance)\n"
            f"- Recency bias: {persona.recency_bias} (1=highly reactive to new information)\n"
            f"- Current opinion: {persona.current_opinion:.2f} (-1=block, +1=approve)\n\n"
            f"Output your review opinion as a single float between -1.0 (block) and 1.0 (approve). "
            f"Output ONLY the number."
        )

    def get_ground_truth(self, seed: EnrichedSeed) -> GroundTruthRecord | None:
        meta = seed.metadata
        if not all(k in meta for k in ("owner", "repo", "pr_number")):
            return None
        return get_coding_ground_truth(
            meta["owner"], meta["repo"], meta["pr_number"],
            token=os.environ["GITHUB_TOKEN"],
        )

    def score(self, result: SimulationResult, truth: GroundTruthRecord) -> BacktestResult:
        simulated_consensus = "approve" if result.trajectory[-1] > 0 else "reject"
        outcome_match = (simulated_consensus == "approve") == truth.data["merged"]
        active_count = (
            len(result.round_events[-1].active_agent_ids) if result.round_events else 0
        )
        comment_volume_ratio = active_count / max(truth.data["comment_count"], 1)

        return BacktestResult(
            direction_match=outcome_match,
            magnitude_correlation=comment_volume_ratio,
            domain_metric={
                "outcome_match": outcome_match,
                "simulated_consensus": simulated_consensus,
                "actual_merged": truth.data["merged"],
                "comment_volume_ratio": comment_volume_ratio,
            },
            total_tier1_calls=result.total_tier1_calls,
            estimated_cost_usd=result.total_cost_usd,
        )
