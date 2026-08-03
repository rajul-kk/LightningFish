"""
Calibration CLI: grid-search engine parameters against a coding backtest.

    GITHUB_TOKEN=... python -m tests.integration.run_calibration <owner> <repo> [limit]

Sweeps global_herd_weight and momentum_weight and prints the best setting by
backtest accuracy. Uses the same public-repo, class-balanced PR pull as the
backtest CLI. Model via LIGHTNINGFISH_MODEL (default haiku; ollama:llama3.2 free).
Only meaningful with a real model and a reasonably large, balanced event set.
"""
from __future__ import annotations

import io
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from lightningfish_core.calibration import grid_search
from lightningfish_core.engine import SimulationEngine

_GRID = {
    "global_herd_weight": [0.2, 0.3, 0.4],
    "momentum_weight": [0.0, 0.2, 0.4],
}


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(0)
    owner, repo = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20

    from lightningfish_coding.backtest_events import pull_pr_events
    from lightningfish_coding.config import CodingDomainAdapter

    token = os.environ.get("GITHUB_TOKEN")
    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    n_agents = int(os.environ.get("LIGHTNINGFISH_N_AGENTS", 40))
    n_rounds = int(os.environ.get("LIGHTNINGFISH_N_ROUNDS", 5))

    print(f"Pulling up to {limit} balanced closed PRs from {owner}/{repo}...")
    events = pull_pr_events(owner, repo, token, limit=limit)
    print(f"  got {len(events)} events\n")

    adapter = CodingDomainAdapter()

    def factory(params: dict) -> SimulationEngine:
        return SimulationEngine(
            adapter, model=model,
            global_herd_weight=params["global_herd_weight"],
            momentum_weight=params["momentum_weight"],
        )

    result = grid_search(adapter, events, _GRID, engine_factory=factory,
                         n_agents=n_agents, n_rounds=n_rounds)

    print("All settings (sim accuracy):")
    for params, report in sorted(result.all_results, key=lambda pr: -pr[1].sim_accuracy):
        print(f"  {params}  → {report.sim_accuracy:.0%} (p={report.p_value_vs_best:.3f})")
    print(f"\nBest: {result.best_params}")
    print(f"  {result.best_report.summary_line()}")


if __name__ == "__main__":
    main()
