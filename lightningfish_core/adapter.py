from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .models import AgentPersona, BacktestResult, EnrichedSeed, GroundTruthRecord, SimulationResult

if TYPE_CHECKING:
    from .social import SocialPost


class DomainAdapter(ABC):
    domain_id: str
    display_name: str
    opinion_labels: tuple[str, str]  # (negative_pole, positive_pole)

    @abstractmethod
    def enrich_seed(self, raw_input: dict) -> EnrichedSeed: ...

    @abstractmethod
    def build_personas(
        self,
        n_agents: int,
        archetype_config: dict[str, float] | None = None,
    ) -> list[AgentPersona]: ...

    @abstractmethod
    def agent_system_prompt(self, seed: EnrichedSeed, persona: AgentPersona) -> str: ...

    @abstractmethod
    def get_ground_truth(self, seed: EnrichedSeed) -> GroundTruthRecord | None: ...

    @abstractmethod
    def score(self, result: SimulationResult, truth: GroundTruthRecord) -> BacktestResult: ...

    @abstractmethod
    def argument_taxonomy(self) -> list[str]:
        """Return the ordered list of argument tags for this domain (exactly 8 items)."""
        ...

    @abstractmethod
    def post_system_prompt(
        self,
        seed: EnrichedSeed,
        persona: AgentPersona,
        feed: "list[SocialPost]",
        viral: "SocialPost | None",
    ) -> str:
        """
        System prompt for T1 (originator) agents.
        The LLM must respond in this constrained format:
            STANCE: <positive_label|negative_label>
            TAG: <one tag from argument_taxonomy()>
            CONFIDENCE: <float 0.0-1.0>
            BLURB: <one sentence ≤60 words>
            <float opinion -1.0 to 1.0>
        """
        ...
