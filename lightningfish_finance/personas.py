from __future__ import annotations
import uuid
import random
from lightningfish_core.models import AgentPersona


def short_seller_resistance(agent: AgentPersona, social_signal: float) -> float:
    """
    ShortSellers get MORE stubborn when consensus builds against them.
    Inverse resistance rule: effective_resistance *= 1.3 when social_signal
    opposes current_opinion and |social_signal| > 0.6.
    """
    opposing = (social_signal * agent.current_opinion) < 0
    if opposing and abs(social_signal) > 0.6:
        return min(1.0, agent.opinion_resistance * 1.3)
    return agent.opinion_resistance


# Parameters from Kahneman-Tversky prospect theory and behavioural finance literature.
_ARCHETYPE_CONFIGS: list[dict] = [
    dict(archetype="ValueInvestor",        opinion_resistance=0.85, recency_bias=0.10, contrarian_tendency=0.70, influence_weight=0.60, proportion=0.12),
    dict(archetype="MomentumTrader",       opinion_resistance=0.20, recency_bias=0.90, contrarian_tendency=0.05, influence_weight=0.40, proportion=0.18),
    dict(archetype="RetailFOMO",           opinion_resistance=0.15, recency_bias=0.95, contrarian_tendency=0.02, influence_weight=0.20, proportion=0.35),
    dict(archetype="ShortSeller",          opinion_resistance=0.90, recency_bias=0.30, contrarian_tendency=0.95, influence_weight=0.70, proportion=0.05, metadata={"resistance_override_fn": short_seller_resistance}),
    dict(archetype="InstitutionalAnalyst", opinion_resistance=0.60, recency_bias=0.40, contrarian_tendency=0.30, influence_weight=0.90, proportion=0.10),
    dict(archetype="MacroTourist",         opinion_resistance=0.40, recency_bias=0.60, contrarian_tendency=0.20, influence_weight=0.30, proportion=0.08),
    dict(archetype="PassiveLurker",        opinion_resistance=0.50, recency_bias=0.50, contrarian_tendency=0.10, influence_weight=0.05, proportion=0.12),
]


def build_finance_personas(n_agents: int) -> list[AgentPersona]:
    personas: list[AgentPersona] = []
    for cfg in _ARCHETYPE_CONFIGS:
        count = max(1, round(cfg["proportion"] * n_agents))
        for _ in range(count):
            personas.append(AgentPersona(
                unique_id=str(uuid.uuid4()),
                archetype=cfg["archetype"],
                opinion_resistance=cfg["opinion_resistance"],
                recency_bias=cfg["recency_bias"],
                contrarian_tendency=cfg["contrarian_tendency"],
                influence_weight=cfg["influence_weight"],
                proportion=cfg["proportion"],
                current_opinion=random.uniform(-0.15, 0.15),
                metadata=cfg.get("metadata", {}),
            ))
    return personas
