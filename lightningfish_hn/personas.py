from __future__ import annotations

import random
import uuid

# NOTE: Parameter values below are first-pass estimates pending validation
# against real Hacker News data. Not grounded in published literature — same
# caveat as lightningfish_coding/personas.py. Treat calibration results as
# provisional until validated by a real backtest run.
from lightningfish_core.jitter import jitter
from lightningfish_core.models import AgentPersona

_ARCHETYPE_CONFIGS: list[dict] = [
    dict(archetype="CasualLurkerVoter",     opinion_resistance=0.35, recency_bias=0.45, contrarian_tendency=0.10, influence_weight=0.10, proportion=0.30, herding_coefficient=0.45),
    dict(archetype="EarlyAdopterHypeBeast", opinion_resistance=0.15, recency_bias=0.90, contrarian_tendency=0.05, influence_weight=0.35, proportion=0.18, herding_coefficient=0.70),
    dict(archetype="ContrarianSkeptic",     opinion_resistance=0.75, recency_bias=0.25, contrarian_tendency=0.75, influence_weight=0.45, proportion=0.15, herding_coefficient=-0.20),
    dict(archetype="DomainExpertPedant",    opinion_resistance=0.80, recency_bias=0.20, contrarian_tendency=0.35, influence_weight=0.85, proportion=0.15, herding_coefficient=0.15),
    dict(archetype="GreybeardCynic",        opinion_resistance=0.92, recency_bias=0.10, contrarian_tendency=0.85, influence_weight=0.55, proportion=0.12, herding_coefficient=-0.30),
    dict(archetype="ShowHNFounder",         opinion_resistance=0.20, recency_bias=0.85, contrarian_tendency=0.05, influence_weight=0.30, proportion=0.10, herding_coefficient=0.50),
]


def build_hn_personas(
    n_agents: int,
    archetype_config: dict[str, float] | None = None,
) -> list[AgentPersona]:
    """
    Build agent personas for the Hacker News domain.

    archetype_config: optional mapping of archetype name -> proportion.
    Only archetypes present in the dict are included; proportions are
    normalized to sum to 1.0. Pass None to use defaults.
    """
    by_name = {cfg["archetype"]: cfg for cfg in _ARCHETYPE_CONFIGS}

    if archetype_config is not None:
        raw = {k: v for k, v in archetype_config.items() if k in by_name and v > 0}
        total = sum(raw.values()) or 1.0
        proportions = {k: v / total for k, v in raw.items()}
    else:
        proportions = {cfg["archetype"]: cfg["proportion"] for cfg in _ARCHETYPE_CONFIGS}

    personas: list[AgentPersona] = []
    for archetype, proportion in proportions.items():
        cfg = by_name[archetype]
        for _ in range(max(1, round(proportion * n_agents))):
            personas.append(AgentPersona(
                unique_id=str(uuid.uuid4()),
                archetype=archetype,
                opinion_resistance=jitter(cfg["opinion_resistance"]),
                recency_bias=jitter(cfg["recency_bias"]),
                contrarian_tendency=jitter(cfg["contrarian_tendency"]),
                influence_weight=jitter(cfg["influence_weight"]),
                proportion=proportion,
                herding_coefficient=jitter(cfg.get("herding_coefficient", 0.3), lo=-1.0, hi=1.0),
                current_opinion=random.uniform(-0.15, 0.15),
            ))
    return personas
