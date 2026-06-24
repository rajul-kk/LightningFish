from __future__ import annotations
from abc import abstractmethod
from .models import AgentPersona, EnrichedSeed


class RuleBasedAgent(AgentPersona):
    """
    Deterministic agent that bypasses LLM inference entirely.
    TierRouter always routes these to tier-2 regardless of influence_weight.
    """
    @abstractmethod
    def compute_opinion(self, seed: EnrichedSeed) -> float: ...
