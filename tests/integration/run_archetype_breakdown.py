"""
Per-archetype opinion breakdown on cached real PR seeds — investigates whether a
backtest's aggregate approve-bias comes from every archetype agreeing (a genuine
data/dynamics effect) or from population mix (a large compliant archetype
outvoting dissenting ones).

Fully offline: reads seeds already fetched by a prior run_backtest CLI run from
the local event cache (.cache/lightningfish/<owner>_<repo>.json) — no network
calls, so this can be re-run freely regardless of API rate-limit budget.

    python -m tests.integration.run_archetype_breakdown <owner> <repo>

Model via LIGHTNINGFISH_MODEL (default ollama:qwen2.5:7b). Errors if the cache
for <owner>/<repo> doesn't exist yet — run run_backtest coding <owner> <repo>
first to populate it.
"""
from __future__ import annotations

import io
import os
import statistics
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from lightningfish_coding.config import CodingDomainAdapter
from lightningfish_core.engine import SimulationEngine
from lightningfish_core.event_cache import EventCache


def _real_event_ids(cache: EventCache) -> list[str]:
    return [eid for eid in cache.event_ids() if not eid.startswith("__list__:")]


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(0)
    owner, repo = sys.argv[1], sys.argv[2]
    model = os.environ.get("LIGHTNINGFISH_MODEL", "ollama:qwen2.5:7b")
    n_agents = int(os.environ.get("LIGHTNINGFISH_N_AGENTS", 24))
    n_rounds = int(os.environ.get("LIGHTNINGFISH_N_ROUNDS", 4))

    cache = EventCache(f"{owner}_{repo}")
    event_ids = _real_event_ids(cache)
    if not event_ids:
        print(f"No cached events for {owner}/{repo}. Run "
              f"'python -m tests.integration.run_backtest coding {owner} {repo}' first.")
        sys.exit(1)

    adapter = CodingDomainAdapter()
    engine = SimulationEngine(adapter, model=model)
    print(f"model={model}  agents={n_agents}  rounds={n_rounds}  "
          f"events={len(event_ids)} (from cache, no network)\n")

    approve_count = 0
    for event_id in event_ids:
        seed = cache.get_seed(event_id)
        truth = cache.get_ground_truth(event_id)
        actual = "?"
        if truth is not None:
            actual = "approve" if truth.data.get("merged") else "block"

        agents = adapter.build_personas(n_agents)
        result = engine.run(seed, agents, n_rounds=n_rounds)
        final = result.trajectory[-1]
        verdict = "approve" if final > 0 else "block"
        approve_count += verdict == "approve"

        by_arch: dict[str, list[float]] = {}
        for a, op in zip(agents, result.final_distribution):
            by_arch.setdefault(a.archetype, []).append(op)

        print(f"[{event_id}] sim={final:+.3f} ({verdict})  actual={actual}  "
              f"parse={result.mean_parse_success_rate:.2f}")
        for arch in sorted(by_arch):
            vals = by_arch[arch]
            mean = statistics.mean(vals)
            tag = "approve" if mean > 0 else "block"
            print(f"    {arch:<24} n={len(vals):<3} mean={mean:+.3f} ({tag})")
        print()

    print(f"Summary: {approve_count}/{len(event_ids)} events predicted approve")


if __name__ == "__main__":
    main()
