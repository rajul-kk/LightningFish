from __future__ import annotations

from abc import ABC, abstractmethod

from .adapter import DomainAdapter
from .engine import SimulationEngine
from .models import BacktestResult, EnrichedSeed


class BacktestHarness(ABC):
    def __init__(self, adapter: DomainAdapter) -> None:
        self.adapter = adapter
        self.engine = SimulationEngine(adapter)

    def run(
        self,
        seed: EnrichedSeed,
        n_agents: int = 500,
        n_rounds: int = 12,
    ) -> BacktestResult:
        agents = self.adapter.build_personas(n_agents)
        result = self.engine.run(seed, agents, n_rounds)
        truth = self.adapter.get_ground_truth(seed)
        if truth is None:
            raise ValueError("Ground truth not available for this seed event")
        return self.adapter.score(result, truth)

    @abstractmethod
    def get_seed_events(self) -> list[EnrichedSeed]: ...
