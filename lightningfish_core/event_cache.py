"""
Local JSON cache of (enriched seed, ground truth) pairs for backtest events, so
repeated backtest/calibration runs against the same real-world events do not
re-spend external API rate-limit budget on every iteration.

Caching is opt-in per adapter via DomainAdapter.cache_key(); adapters that don't
implement it (return None) are simply never cached.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Callable

from .adapter import DomainAdapter
from .backtest import BacktestEvent
from .models import (
    AgentPersona,
    BacktestResult,
    EnrichedSeed,
    GroundTruthRecord,
    ScrapedDocument,
    SimulationResult,
)

DEFAULT_CACHE_DIR = Path(".cache/lightningfish")
_LIST_PREFIX = "__list__:"


def _seed_to_dict(seed: EnrichedSeed) -> dict:
    return dataclasses.asdict(seed)


def _seed_from_dict(d: dict) -> EnrichedSeed:
    docs = [ScrapedDocument(**doc) for doc in d.get("scraped_context", [])]
    return EnrichedSeed(
        domain_id=d["domain_id"],
        raw_input=d["raw_input"],
        summary=d["summary"],
        entities=d["entities"],
        event_type=d["event_type"],
        metadata=d["metadata"],
        scraped_context=docs,
    )


class EventCache:
    """Flat JSON store of {event_id: {seed, ground_truth}} under one cache_key."""

    def __init__(self, cache_key: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
        self._path = cache_dir / f"{cache_key.replace('/', '_')}.json"
        self._data: dict[str, dict] = {}
        if self._path.exists():
            self._data = json.loads(self._path.read_text("utf-8"))

    def __len__(self) -> int:
        return len(self._data)

    def event_ids(self) -> list[str]:
        return list(self._data)

    def get_seed(self, event_id: str) -> EnrichedSeed | None:
        entry = self._data.get(event_id)
        return _seed_from_dict(entry["seed"]) if entry else None

    def put_seed_only(self, event_id: str, seed: EnrichedSeed) -> None:
        """Cache a seed without marking ground truth as known (has_ground_truth
        stays False), used when caching a freshly-pulled event list up front."""
        entry = self._data.get(event_id, {})
        entry["seed"] = _seed_to_dict(seed)
        self._data[event_id] = entry

    def get_manifest(self, list_key: str) -> list[str] | None:
        entry = self._data.get(_LIST_PREFIX + list_key)
        return entry["event_ids"] if entry else None

    def put_manifest(self, list_key: str, event_ids: list[str]) -> None:
        self._data[_LIST_PREFIX + list_key] = {"event_ids": event_ids}

    def has_ground_truth(self, event_id: str) -> bool:
        return event_id in self._data and "ground_truth" in self._data[event_id]

    def get_ground_truth(self, event_id: str) -> GroundTruthRecord | None:
        entry = self._data.get(event_id)
        if entry is None or entry.get("ground_truth") is None:
            return None
        return GroundTruthRecord(data=entry["ground_truth"])

    def put(
        self,
        event_id: str,
        seed: EnrichedSeed,
        ground_truth: GroundTruthRecord | None,
    ) -> None:
        self._data[event_id] = {
            "seed": _seed_to_dict(seed),
            "ground_truth": ground_truth.data if ground_truth is not None else None,
        }

    def put_run(self, event_id: str, run_key: str, result: SimulationResult) -> None:
        """
        Persist the parts of a finished run that scoring needs.

        Simulations are the expensive step and were previously discarded once
        printed, so re-scoring the same run against a different question (the
        crowd's dispersion rather than its mean, say) meant simulating again.
        Stores the trajectory and final distribution, not the whole object,
        so the cache stays small and JSON-serialisable.
        """
        entry = self._data.setdefault(event_id, {})
        entry.setdefault("runs", {})[run_key] = {
            "trajectory": list(result.trajectory),
            "final_distribution": list(result.final_distribution),
            "mean_parse_success_rate": result.mean_parse_success_rate,
            "low_confidence": result.low_confidence,
        }

    def get_run(self, event_id: str, run_key: str) -> dict | None:
        entry = self._data.get(event_id)
        if not entry:
            return None
        return entry.get("runs", {}).get(run_key)

    def copy_ground_truth_from(self, other: "EventCache") -> int:
        """
        Import ``other``'s ground truth for events this cache already knows,
        without touching seeds. Returns the number of records copied.

        For a second experiment over the same events with differently
        enriched seeds: without this, the new cache re-fetches truth and
        silently re-measures. Outcomes that move between measurements (HN
        points keep accruing) then unpair a "paired" comparison, observed
        flipping one story's class from flop to viral.
        """
        copied = 0
        for event_id, entry in self._data.items():
            if event_id.startswith(_LIST_PREFIX) or "ground_truth" in entry:
                continue
            truth = other.get_ground_truth(event_id)
            if truth is not None:
                entry["ground_truth"] = truth.data
                copied += 1
        if copied:
            self.save()
        return copied

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2), "utf-8")


class CachingAdapter(DomainAdapter):
    """
    Wraps a DomainAdapter so get_ground_truth is served from an EventCache when
    present, falling back to (and populating) the wrapped adapter on a miss.
    Every other method delegates unchanged. No-op (always delegates) for seeds
    whose adapter.cache_key() returns None.
    """

    def __init__(self, inner: DomainAdapter, cache: EventCache) -> None:
        self._inner = inner
        self._cache = cache
        self.domain_id = inner.domain_id
        self.display_name = inner.display_name
        self.opinion_labels = inner.opinion_labels

    def enrich_seed(self, raw_input: dict) -> EnrichedSeed:
        return self._inner.enrich_seed(raw_input)

    def build_personas(
        self, n_agents: int, archetype_config: dict[str, float] | None = None, **kwargs
    ) -> list[AgentPersona]:
        # **kwargs forwards domain-specific extras (e.g. HN's bounded_confidence,
        # memory) not part of the base DomainAdapter signature (METHODOLOGY.md
        # rule 6: this wrapper already broke once by reimplementing a hook
        # instead of forwarding through it).
        return self._inner.build_personas(n_agents, archetype_config, **kwargs)

    def agent_system_prompt(self, seed: EnrichedSeed, persona: AgentPersona) -> str:
        return self._inner.agent_system_prompt(seed, persona)

    def post_system_prompt(self, seed, persona, feed, viral) -> str:
        return self._inner.post_system_prompt(seed, persona, feed, viral)

    def reactor_system_prompt(self, seed, persona, feed, viral) -> str:
        return self._inner.reactor_system_prompt(seed, persona, feed, viral)

    def argument_taxonomy(self) -> list[str]:
        return self._inner.argument_taxonomy()

    def score(self, result: SimulationResult, truth: GroundTruthRecord) -> BacktestResult:
        return self._inner.score(result, truth)

    def sim_direction(self, result: SimulationResult) -> int:
        return self._inner.sim_direction(result)

    def naive_prediction(self, seed: EnrichedSeed) -> float:
        return self._inner.naive_prediction(seed)

    def truth_direction(self, truth: GroundTruthRecord) -> int:
        return self._inner.truth_direction(truth)

    def baseline_llm_prompt(self, seed: EnrichedSeed) -> str:
        return self._inner.baseline_llm_prompt(seed)

    def cache_key(self, seed: EnrichedSeed) -> str | None:
        return self._inner.cache_key(seed)

    def get_ground_truth(self, seed: EnrichedSeed) -> GroundTruthRecord | None:
        event_id = self._inner.cache_key(seed)
        if event_id is None:
            return self._inner.get_ground_truth(seed)
        if self._cache.has_ground_truth(event_id):
            return self._cache.get_ground_truth(event_id)
        truth = self._inner.get_ground_truth(seed)
        self._cache.put(event_id, seed, truth)
        self._cache.save()
        return truth


def cached_pull_events(
    cache: EventCache,
    list_key: str,
    fetch_fn: Callable[[], list[BacktestEvent]],
) -> list[BacktestEvent]:
    """
    Returns BacktestEvents for ``list_key`` from cache when a complete manifest
    exists; otherwise calls ``fetch_fn`` (the network pull), caches every
    returned seed plus the manifest, and returns the fresh events. This avoids
    re-spending list/search API budget on repeated runs against the same pull.
    """
    ids = cache.get_manifest(list_key)
    if ids is not None:
        cached = [(eid, cache.get_seed(eid)) for eid in ids]
        if cached and all(seed is not None for _, seed in cached):
            return [BacktestEvent(event_id=eid, seed=seed) for eid, seed in cached]  # type: ignore[arg-type]

    events = fetch_fn()
    for event in events:
        cache.put_seed_only(event.event_id, event.seed)
    cache.put_manifest(list_key, [e.event_id for e in events])
    cache.save()
    return events
