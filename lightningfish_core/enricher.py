from __future__ import annotations
from abc import ABC, abstractmethod
from .models import EnrichedSeed


class EnricherPlugin(ABC):
    @abstractmethod
    def enrich(self, seed: EnrichedSeed) -> EnrichedSeed: ...
