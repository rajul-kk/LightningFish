from __future__ import annotations

import random

# NOTE: Parameter values below are first-pass estimates pending validation
# against a real PR dataset. Unlike the finance domain, these are NOT
# grounded in published literature. Treat calibration results as provisional.
import uuid

from lightningfish_core.jitter import jitter
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
    dict(archetype="SecurityReviewer",       opinion_resistance=0.80, recency_bias=0.20, contrarian_tendency=0.60, influence_weight=0.75, proportion=0.10, herding_coefficient=-0.10),
    dict(archetype="PerformanceReviewer",    opinion_resistance=0.70, recency_bias=0.30, contrarian_tendency=0.40, influence_weight=0.55, proportion=0.10, herding_coefficient=0.15),
    dict(archetype="StyleMaintainability",   opinion_resistance=0.40, recency_bias=0.50, contrarian_tendency=0.20, influence_weight=0.35, proportion=0.20, herding_coefficient=0.40),
    dict(archetype="DomainExpertMaintainer", opinion_resistance=0.85, recency_bias=0.15, contrarian_tendency=0.50, influence_weight=0.90, proportion=0.08, herding_coefficient=0.10),
    dict(archetype="JuniorContributor",      opinion_resistance=0.20, recency_bias=0.80, contrarian_tendency=0.05, influence_weight=0.15, proportion=0.40, herding_coefficient=0.65),
]
_CIBOT_CONFIG = dict(
    archetype="CIBot", opinion_resistance=0.99, recency_bias=0.99,
    contrarian_tendency=0.0, influence_weight=0.50, proportion=0.12, herding_coefficient=0.0,
)


def build_coding_personas(
    n_agents: int,
    archetype_config: dict[str, float] | None = None,
) -> list[AgentPersona]:
    """
    Build agent personas for the coding domain.

    archetype_config: optional mapping of archetype name → proportion.
    Only archetypes present in the dict are included (CIBot included if
    listed). Pass None to use defaults (all archetypes + CIBot).
    """
    by_name = {cfg["archetype"]: cfg for cfg in _ARCHETYPE_CONFIGS}
    by_name["CIBot"] = _CIBOT_CONFIG

    if archetype_config is not None:
        raw = {k: v for k, v in archetype_config.items() if k in by_name and v > 0}
        total = sum(raw.values()) or 1.0
        proportions = {k: v / total for k, v in raw.items()}
    else:
        proportions = {cfg["archetype"]: cfg["proportion"] for cfg in _ARCHETYPE_CONFIGS}
        proportions["CIBot"] = _CIBOT_CONFIG["proportion"]  # type: ignore[assignment]

    personas: list[AgentPersona] = []
    for archetype, proportion in proportions.items():
        cfg = by_name[archetype]
        count = max(1, round(proportion * n_agents))
        if archetype == "CIBot":
            for _ in range(count):
                personas.append(CIBot(
                    unique_id=str(uuid.uuid4()),
                    archetype="CIBot",
                    opinion_resistance=cfg["opinion_resistance"],
                    recency_bias=cfg["recency_bias"],
                    contrarian_tendency=cfg["contrarian_tendency"],
                    influence_weight=cfg["influence_weight"],
                    proportion=proportion,
                    herding_coefficient=cfg.get("herding_coefficient", 0.0),
                ))
        else:
            for _ in range(count):
                personas.append(AgentPersona(
                    unique_id=str(uuid.uuid4()),
                    archetype=archetype,
                    opinion_resistance=jitter(cfg["opinion_resistance"]),
                    recency_bias=jitter(cfg["recency_bias"]),
                    contrarian_tendency=jitter(cfg["contrarian_tendency"]),
                    influence_weight=jitter(cfg["influence_weight"]),
                    proportion=proportion,
                    herding_coefficient=jitter(cfg.get("herding_coefficient", 0.3), lo=-1.0, hi=1.0),
                    current_opinion=random.uniform(-0.1, 0.1),
                ))
    return personas
