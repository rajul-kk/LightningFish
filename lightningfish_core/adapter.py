from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AgentPersona, BacktestResult, EnrichedSeed, GroundTruthRecord, SimulationResult


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
