"""
Archetype population sweep — tests whether a backtest's aggregate bias (e.g.
always predicting approve) traces to population mix rather than per-agent
dynamics, by re-scoring the same cached events under different archetype
proportions with engine dynamics held fixed.

Fully offline: reads from the local event cache populated by a prior
run_backtest CLI run — no network calls.

    python -m tests.integration.run_population_sweep <owner> <repo>

Model via LIGHTNINGFISH_MODEL (default ollama:qwen2.5:7b).
"""
from __future__ import annotations

import io
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from lightningfish_core.backtest import BacktestEvent, llm_baseline, sign
from lightningfish_core.calibration import sweep_population
from lightningfish_core.engine import SimulationEngine
from lightningfish_core.event_cache import CachingAdapter, EventCache

# Candidate population mixes to compare against the domain default. "critical"
# overweights the archetypes most likely to block (Security/Performance/Domain
# Expert, dropping the large deferential JuniorContributor share) — if accuracy
# jumps here, the default mix's approve-bias is a population effect.
_CONFIGS = {
    "default": None,  # adapter's built-in proportions
    "critical": {
        "SecurityReviewer": 0.30, "PerformanceReviewer": 0.20,
        "DomainExpertMaintainer": 0.30, "StyleMaintainability": 0.10,
        "JuniorContributor": 0.10,
    },
    "juniors_only": {"JuniorContributor": 1.0},
    "experts_only": {"DomainExpertMaintainer": 1.0, "SecurityReviewer": 1.0},
}


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(0)
    owner, repo = sys.argv[1], sys.argv[2]
    model = os.environ.get("LIGHTNINGFISH_MODEL", "ollama:qwen2.5:7b")
    n_agents = int(os.environ.get("LIGHTNINGFISH_N_AGENTS", 24))
    n_rounds = int(os.environ.get("LIGHTNINGFISH_N_ROUNDS", 4))

    from lightningfish_coding.config import CodingDomainAdapter

    cache = EventCache(f"{owner}_{repo}")
    event_ids = [e for e in cache.event_ids() if not e.startswith("__list__:")]
    if not event_ids:
        print(f"No cached events for {owner}/{repo}. Run run_backtest first.")
        sys.exit(1)

    events = [BacktestEvent(eid, cache.get_seed(eid)) for eid in event_ids]  # type: ignore[arg-type]
    events = [e for e in events if cache.has_ground_truth(e.event_id)]
    if not events:
        print("No cached events have ground truth yet — the run_backtest CLI "
              "populates it incrementally; wait for it to finish and re-run.")
        sys.exit(1)
    print(f"Using {len(events)}/{len(event_ids)} cached events with known ground truth.\n")

    inner = CodingDomainAdapter()
    adapter = CachingAdapter(inner, cache)
    engine = SimulationEngine(adapter, model=model)
    baselines = {
        "naive": lambda e: sign(adapter.naive_prediction(e.seed)),
        "single_llm": llm_baseline(adapter, engine),
    }

    result = sweep_population(adapter, engine, events, _CONFIGS,
                              n_agents=n_agents, n_rounds=n_rounds, baselines=baselines)

    print("All population mixes (sim accuracy):")
    for name, report in sorted(result.all_results, key=lambda nr: -nr[1].sim_accuracy):
        print(f"  {name:<14} {report.summary_line()}")
    print(f"\nBest: {result.best_config_name}")


if __name__ == "__main__":
    main()
