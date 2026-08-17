from __future__ import annotations

from lightningfish_core.adapter import DomainAdapter
from lightningfish_core.backtest import BacktestEvent
from lightningfish_core.event_cache import CachingAdapter, EventCache, cached_pull_events
from lightningfish_core.models import (
    BacktestResult,
    EnrichedSeed,
    GroundTruthRecord,
)


def _seed(sid: str) -> EnrichedSeed:
    return EnrichedSeed(
        domain_id="stub", raw_input={}, summary=sid,
        entities=[], event_type="e", metadata={"id": sid},
    )


class _StubAdapter(DomainAdapter):
    domain_id = "stub"
    display_name = "Stub"
    opinion_labels = ("no", "yes")

    def __init__(self):
        self.ground_truth_calls = 0

    def enrich_seed(self, r): return _seed("x")
    def build_personas(self, n, archetype_config=None): return []
    def agent_system_prompt(self, seed, persona): return ""
    def argument_taxonomy(self): return ["a", "b", "c", "d", "e", "f", "g", "h"]
    def post_system_prompt(self, seed, persona, feed, viral): return ""
    def score(self, result, truth): return BacktestResult(True, 0.0, {}, 0, 0.0)

    def cache_key(self, seed):
        return seed.metadata["id"]

    def get_ground_truth(self, seed):
        self.ground_truth_calls += 1
        return GroundTruthRecord(data={"actual": 1})


def test_event_cache_roundtrips_seed_and_truth(tmp_path):
    cache = EventCache("k", cache_dir=tmp_path)
    seed = _seed("e1")
    truth = GroundTruthRecord(data={"merged": True})
    cache.put("e1", seed, truth)
    cache.save()

    reloaded = EventCache("k", cache_dir=tmp_path)
    assert reloaded.get_seed("e1").summary == "e1"
    assert reloaded.get_ground_truth("e1").data == {"merged": True}
    assert reloaded.has_ground_truth("e1")


def test_event_cache_persists_none_ground_truth(tmp_path):
    cache = EventCache("k", cache_dir=tmp_path)
    cache.put("e1", _seed("e1"), None)
    cache.save()
    reloaded = EventCache("k", cache_dir=tmp_path)
    assert reloaded.has_ground_truth("e1")  # known-absent is still "known"
    assert reloaded.get_ground_truth("e1") is None


def test_caching_adapter_only_hits_inner_once(tmp_path):
    inner = _StubAdapter()
    cache = EventCache("k", cache_dir=tmp_path)
    wrapped = CachingAdapter(inner, cache)
    seed = _seed("e1")

    t1 = wrapped.get_ground_truth(seed)
    t2 = wrapped.get_ground_truth(seed)
    assert t1.data == t2.data == {"actual": 1}
    assert inner.ground_truth_calls == 1  # second call served from cache


def test_caching_adapter_bypasses_cache_when_no_cache_key(tmp_path):
    class NoKeyAdapter(_StubAdapter):
        def cache_key(self, seed):
            return None

    inner = NoKeyAdapter()
    wrapped = CachingAdapter(inner, EventCache("k", cache_dir=tmp_path))
    wrapped.get_ground_truth(_seed("e1"))
    wrapped.get_ground_truth(_seed("e1"))
    assert inner.ground_truth_calls == 2  # never cached


def test_cached_pull_events_only_fetches_once(tmp_path):
    cache = EventCache("k", cache_dir=tmp_path)
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return [BacktestEvent("e1", _seed("e1")), BacktestEvent("e2", _seed("e2"))]

    first = cached_pull_events(cache, "list1", fetch)
    second = cached_pull_events(cache, "list1", fetch)
    assert calls["n"] == 1
    assert [e.event_id for e in first] == [e.event_id for e in second] == ["e1", "e2"]


def test_cached_pull_events_different_keys_dont_collide(tmp_path):
    cache = EventCache("k", cache_dir=tmp_path)
    a = cached_pull_events(cache, "listA", lambda: [BacktestEvent("a1", _seed("a1"))])
    b = cached_pull_events(cache, "listB", lambda: [BacktestEvent("b1", _seed("b1"))])
    assert a[0].event_id == "a1"
    assert b[0].event_id == "b1"


def test_copy_ground_truth_from_pairs_two_caches(tmp_path):
    """HN points keep accruing and the API serves only current totals, so a
    second run over the same events must reuse the first run's measurement
    rather than silently re-measuring a moved outcome."""
    from lightningfish_core.event_cache import EventCache
    from lightningfish_core.models import EnrichedSeed, GroundTruthRecord

    def seed(n):
        return EnrichedSeed(domain_id="hn", raw_input={}, summary=f"s{n}",
                            entities=[], event_type="story", metadata={"story_id": n})

    base = EventCache("base", cache_dir=tmp_path)
    base.put("hn:1", seed(1), GroundTruthRecord(data={"points": 4}))
    base.put("hn:2", seed(2), GroundTruthRecord(data={"points": 90}))
    base.save()

    enriched = EventCache("enriched", cache_dir=tmp_path)
    enriched.put_seed_only("hn:1", seed(1))
    enriched.put_seed_only("hn:2", seed(2))
    assert not enriched.has_ground_truth("hn:1")

    assert enriched.copy_ground_truth_from(base) == 2
    assert enriched.get_ground_truth("hn:1").data["points"] == 4
    assert enriched.get_ground_truth("hn:2").data["points"] == 90


def test_copy_ground_truth_from_never_overwrites(tmp_path):
    from lightningfish_core.event_cache import EventCache
    from lightningfish_core.models import EnrichedSeed, GroundTruthRecord

    s = EnrichedSeed(domain_id="hn", raw_input={}, summary="s", entities=[],
                     event_type="story", metadata={"story_id": 1})
    base = EventCache("base2", cache_dir=tmp_path)
    base.put("hn:1", s, GroundTruthRecord(data={"points": 4}))

    target = EventCache("target2", cache_dir=tmp_path)
    target.put("hn:1", s, GroundTruthRecord(data={"points": 108}))

    assert target.copy_ground_truth_from(base) == 0
    assert target.get_ground_truth("hn:1").data["points"] == 108
