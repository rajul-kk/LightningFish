"""
Per-archetype opinion breakdown on cached real seeds — investigates whether a
backtest's aggregate bias (e.g. always predicting approve/viral) comes from
every archetype agreeing (a genuine data/dynamics effect) or from population
mix (a large compliant archetype outvoting dissenting ones).

Fully offline: reads seeds already fetched by a prior run_backtest CLI run from
the local event cache — no network calls, so this can be re-run freely
regardless of API rate-limit budget.

    python -m tests.integration.run_archetype_breakdown coding <owner> <repo>
    python -m tests.integration.run_archetype_breakdown hn

Model via LIGHTNINGFISH_MODEL (default ollama:qwen2.5:7b). Errors if the
relevant cache doesn't exist yet — run run_backtest for that domain first.
"""
from __future__ import annotations

import io
import os
import statistics
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from lightningfish_core.engine import SimulationEngine
from lightningfish_core.event_cache import EventCache


def _real_event_ids(cache: EventCache) -> list[str]:
    return [eid for eid in cache.event_ids() if not eid.startswith("__list__:")]


def _resolve(args: list[str]) -> tuple[object, EventCache, str]:
    """Returns (adapter, cache, ground-truth-run-command-hint)."""
    if not args or args[0] not in ("coding", "hn"):
        print(__doc__)
        sys.exit(0)
    if args[0] == "coding":
        if len(args) < 3:
            print("Usage: run_archetype_breakdown coding <owner> <repo>")
            sys.exit(1)
        owner, repo = args[1], args[2]
        from lightningfish_coding.config import CodingDomainAdapter
        return (CodingDomainAdapter(), EventCache(f"{owner}_{repo}"),
                f"run_backtest coding {owner} {repo}")
    from lightningfish_hn.config import HNDomainAdapter
    return HNDomainAdapter(), EventCache("hn_stories"), "run_backtest hn"


def _actual_label(domain: str, truth) -> str:
    if truth is None:
        return "?"
    if domain == "coding":
        return "approve" if truth.data.get("merged") else "block"
    return f"points={truth.data.get('points')} comments={truth.data.get('num_comments')}"


def main() -> None:
    domain = sys.argv[1] if len(sys.argv) > 1 else ""
    adapter, cache, hint = _resolve(sys.argv[1:])
    model = os.environ.get("LIGHTNINGFISH_MODEL", "ollama:qwen2.5:7b")
    n_agents = int(os.environ.get("LIGHTNINGFISH_N_AGENTS", 24))
    n_rounds = int(os.environ.get("LIGHTNINGFISH_N_ROUNDS", 4))

    event_ids = _real_event_ids(cache)
    if not event_ids:
        print(f"No cached events. Run 'python -m tests.integration.{hint}' first.")
        sys.exit(1)

    neg, pos = adapter.opinion_labels
    engine = SimulationEngine(adapter, model=model)
    print(f"domain={domain}  model={model}  agents={n_agents}  rounds={n_rounds}  "
          f"events={len(event_ids)} (from cache, no network)\n")

    positive_count = 0
    for event_id in event_ids:
        seed = cache.get_seed(event_id)
        truth = cache.get_ground_truth(event_id)
        actual = _actual_label(domain, truth)

        agents = adapter.build_personas(n_agents)
        result = engine.run(seed, agents, n_rounds=n_rounds)
        final = result.trajectory[-1]
        verdict = pos if final > 0 else neg
        positive_count += verdict == pos

        by_arch: dict[str, list[float]] = {}
        for a, op in zip(agents, result.final_distribution):
            by_arch.setdefault(a.archetype, []).append(op)

        print(f"[{event_id}] sim={final:+.3f} ({verdict})  actual={actual}  "
              f"parse={result.mean_parse_success_rate:.2f}")
        for arch in sorted(by_arch):
            vals = by_arch[arch]
            mean = statistics.mean(vals)
            tag = pos if mean > 0 else neg
            print(f"    {arch:<24} n={len(vals):<3} mean={mean:+.3f} ({tag})")
        print()

    print(f"Summary: {positive_count}/{len(event_ids)} events predicted '{pos}'")


if __name__ == "__main__":
    main()
