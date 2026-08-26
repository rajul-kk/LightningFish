"""
Cross-run track record per (domain, archetype): how often that archetype's
opinion direction agreed with the eventual settled outcome, accumulated
across every backtest run that has scored it, not within one simulation.

A single knowledge-graph-scoped agent memory can't do this: a GreybeardCynic
wrong 80% of the time over the last 40 debates carries that record into the
next one, persisted to disk between separate process invocations.
"""
from __future__ import annotations

import json
from pathlib import Path

_DEFAULT_PATH = Path(".cache/lightningfish/persona_memory.json")


class PersonaMemoryStore:
    def __init__(self, path: "Path | str" = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._data: dict[str, dict[str, list[int]]] = {}
        if self._path.exists():
            self._data = json.loads(self._path.read_text())

    def record(self, domain_id: str, archetype: str, correct: bool) -> None:
        bucket = self._data.setdefault(domain_id, {}).setdefault(archetype, [])
        bucket.append(1 if correct else 0)

    def track_record(
        self, domain_id: str, archetype: str, window: int = 50
    ) -> "tuple[int, int] | None":
        """(correct, total) over the most recent `window` recorded outcomes
        for this domain+archetype, or None if it has never been scored."""
        bucket = self._data.get(domain_id, {}).get(archetype)
        if not bucket:
            return None
        recent = bucket[-window:]
        return sum(recent), len(recent)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data))
