from __future__ import annotations
# NOTE: Parameter values below are first-pass estimates pending validation
# against a real PR dataset. Unlike the finance domain, these are NOT
# grounded in published literature. Treat calibration results as provisional.
import uuid
import random
from lightningfish_core.models import AgentPersona, EnrichedSeed
from lightningfish_core.rule_agent import RuleBasedAgent


class CIBot(RuleBasedAgent):
    """
    Deterministic agent. Opinion derived purely from CI test pass rate.
    Never calls the LLM. TierRouter always routes to tier-2.
    """
    def compute_opinion(self, seed: EnrichedSeed) -> float:
        pass_rate = seed.metadata.get("ci_pass_rate")
        if pass_rate is None:
            return 0.0
        return max(-1.0, min(1.0, (pass_rate * 2.0) - 1.0))


_ARCHETYPE_CONFIGS: list[dict] = [
    dict(archetype="SecurityReviewer",       opinion_resistance=0.80, recency_bias=0.20, contrarian_tendency=0.60, influence_weight=0.75, proportion=0.10),
    dict(archetype="PerformanceReviewer",    opinion_resistance=0.70, recency_bias=0.30, contrarian_tendency=0.40, influence_weight=0.55, proportion=0.10),
    dict(archetype="StyleMaintainability",   opinion_resistance=0.40, recency_bias=0.50, contrarian_tendency=0.20, influence_weight=0.35, proportion=0.20),
    dict(archetype="DomainExpertMaintainer", opinion_resistance=0.85, recency_bias=0.15, contrarian_tendency=0.50, influence_weight=0.90, proportion=0.08),
    dict(archetype="JuniorContributor",      opinion_resistance=0.20, recency_bias=0.80, contrarian_tendency=0.05, influence_weight=0.15, proportion=0.40),
]
_CIBOT_CONFIG = dict(
    archetype="CIBot", opinion_resistance=0.99, recency_bias=0.99,
    contrarian_tendency=0.0, influence_weight=0.50, proportion=0.12,
)


def build_coding_personas(n_agents: int) -> list[AgentPersona]:
    personas: list[AgentPersona] = []
    for cfg in _ARCHETYPE_CONFIGS:
        for _ in range(max(1, round(cfg["proportion"] * n_agents))):
            personas.append(AgentPersona(
                unique_id=str(uuid.uuid4()),
                archetype=cfg["archetype"],
                opinion_resistance=cfg["opinion_resistance"],
                recency_bias=cfg["recency_bias"],
                contrarian_tendency=cfg["contrarian_tendency"],
                influence_weight=cfg["influence_weight"],
                proportion=cfg["proportion"],
                current_opinion=random.uniform(-0.1, 0.1),
            ))
    for _ in range(max(1, round(_CIBOT_CONFIG["proportion"] * n_agents))):
        personas.append(CIBot(
            unique_id=str(uuid.uuid4()),
            archetype="CIBot",
            opinion_resistance=_CIBOT_CONFIG["opinion_resistance"],
            recency_bias=_CIBOT_CONFIG["recency_bias"],
            contrarian_tendency=_CIBOT_CONFIG["contrarian_tendency"],
            influence_weight=_CIBOT_CONFIG["influence_weight"],
            proportion=_CIBOT_CONFIG["proportion"],
        ))
    return personas
