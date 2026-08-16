"""
Archetype population sweep — tests whether a backtest's aggregate bias (e.g.
always predicting approve/viral) traces to population mix rather than
per-agent dynamics, by re-scoring the same cached events under different
archetype proportions with engine dynamics held fixed.

Fully offline: reads from the local event cache populated by a prior
run_backtest CLI run — no network calls.

    python -m tests.integration.run_population_sweep coding <owner> <repo>
    python -m tests.integration.run_population_sweep hn

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

# Candidate population mixes per domain, compared against the domain default.
# The "critical"/"skeptics_heavy" mix overweights the archetypes most likely to
# dissent — if accuracy jumps here, the default mix's bias is a population
# effect. The "*_only" mixes isolate the dominant compliant archetype and the
# most skeptical archetypes respectively.
_CONFIGS_BY_DOMAIN = {
    "coding": {
        "default": None,
        "critical": {
            "SecurityReviewer": 0.30, "PerformanceReviewer": 0.20,
            "DomainExpertMaintainer": 0.30, "StyleMaintainability": 0.10,
            "JuniorContributor": 0.10,
        },
        "juniors_only": {"JuniorContributor": 1.0},
        "experts_only": {"DomainExpertMaintainer": 1.0, "SecurityReviewer": 1.0},
    },
    "hn": {
        "default": None,
        "skeptics_heavy": {
            "ContrarianSkeptic": 0.35, "GreybeardCynic": 0.35,
            "DomainExpertPedant": 0.20, "CasualLurkerVoter": 0.10,
        },
        "lurkers_only": {"CasualLurkerVoter": 1.0},
        "cynics_only": {"GreybeardCynic": 1.0, "ContrarianSkeptic": 1.0},
    },
}


def _resolve(args: list[str]):
    if not args or args[0] not in ("coding", "hn"):
        print(__doc__)
        sys.exit(0)
    domain = args[0]
    if domain == "coding":
        if len(args) < 3:
            print("Usage: run_population_sweep coding <owner> <repo>")
            sys.exit(1)
        owner, repo = args[1], args[2]
        from lightningfish_coding.config import CodingDomainAdapter
        return domain, CodingDomainAdapter(), EventCache(f"{owner}_{repo}")
    from lightningfish_hn.config import HNDomainAdapter
    return domain, HNDomainAdapter(), EventCache("hn_stories")


def main() -> None:
    domain, inner, cache = _resolve(sys.argv[1:])
    model = os.environ.get("LIGHTNINGFISH_MODEL", "ollama:qwen2.5:7b")
    n_agents = int(os.environ.get("LIGHTNINGFISH_N_AGENTS", 24))
    n_rounds = int(os.environ.get("LIGHTNINGFISH_N_ROUNDS", 4))

    event_ids = [e for e in cache.event_ids() if not e.startswith("__list__:")]
    if not event_ids:
        print("No cached events. Run run_backtest for this domain first.")
        sys.exit(1)

    events = [BacktestEvent(eid, cache.get_seed(eid)) for eid in event_ids]  # type: ignore[arg-type]
    events = [e for e in events if cache.has_ground_truth(e.event_id)]
    if not events:
        print("No cached events have ground truth yet — the run_backtest CLI "
              "populates it incrementally; wait for it to finish and re-run.")
        sys.exit(1)
    print(f"domain={domain}  Using {len(events)}/{len(event_ids)} cached events "
          f"with known ground truth.\n")

    adapter = CachingAdapter(inner, cache)
    engine = SimulationEngine(adapter, model=model)
    baselines = {
        "naive": lambda e: sign(adapter.naive_prediction(e.seed)),
        "single_llm": llm_baseline(adapter, engine),
    }

    result = sweep_population(adapter, engine, events, _CONFIGS_BY_DOMAIN[domain],
                              n_agents=n_agents, n_rounds=n_rounds, baselines=baselines)

    print("All population mixes (sim accuracy):")
    for name, report in sorted(result.all_results, key=lambda nr: -nr[1].sim_accuracy):
        print(f"  {name:<16} {report.summary_line()}")
    print(f"\nBest: {result.best_config_name}")


if __name__ == "__main__":
    main()
