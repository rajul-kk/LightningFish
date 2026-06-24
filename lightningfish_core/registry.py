from __future__ import annotations
from importlib.metadata import entry_points
from .adapter import DomainAdapter


class DomainRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, DomainAdapter] = {}

    def register(self, adapter: DomainAdapter) -> None:
        self._adapters[adapter.domain_id] = adapter

    def get(self, domain_id: str) -> DomainAdapter:
        if domain_id not in self._adapters:
            raise KeyError(f"No domain adapter registered for '{domain_id}'")
        return self._adapters[domain_id]

    def all(self) -> list[DomainAdapter]:
        return list(self._adapters.values())

    def load_entry_points(self) -> None:
        """Auto-discover adapters declared under 'lightningfish.domains' entry point group."""
        for ep in entry_points(group="lightningfish.domains"):
            adapter = ep.load()
            self.register(adapter)


# Module-level singleton used by domain __init__ files and service startup
registry = DomainRegistry()
