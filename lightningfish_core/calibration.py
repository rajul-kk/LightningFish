"""
Grid-search calibration: find the engine parameters that maximize backtest
accuracy on held-out events, instead of leaving them hand-set.

Runs the full backtest once per parameter combination and picks the setting with
the highest sim accuracy (tie-broken by lowest p-value). Meaningful only against
a real, sufficiently large event set — small samples overfit.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable

from .adapter import DomainAdapter
from .backtest import BacktestEvent, BacktestReport, run_backtest
from .engine import SimulationEngine


@dataclass
class CalibrationResult:
    best_params: dict[str, float]
    best_report: BacktestReport
    all_results: list[tuple[dict[str, float], BacktestReport]]


@dataclass
class PopulationSweepResult:
    best_config_name: str
    best_report: BacktestReport
    all_results: list[tuple[str, BacktestReport]]


def grid_search(
    adapter: DomainAdapter,
    events: list[BacktestEvent],
    param_grid: dict[str, list[float]],
    engine_factory: Callable[[dict[str, float]], SimulationEngine],
    n_agents: int = 100,
    n_rounds: int = 8,
    baselines: dict[str, Callable[[BacktestEvent], int]] | None = None,
) -> CalibrationResult:
    """
    Sweep the Cartesian product of ``param_grid`` (name -> candidate values),
    building an engine per combination via ``engine_factory`` and scoring it with
    run_backtest. Returns the best combination and every result.
    """
    names = list(param_grid)
    combos = [dict(zip(names, values)) for values in product(*(param_grid[n] for n in names))]

    results: list[tuple[dict[str, float], BacktestReport]] = []
    for params in combos:
        engine = engine_factory(params)
        report = run_backtest(adapter, engine, events, n_agents=n_agents,
                              n_rounds=n_rounds, baselines=baselines)
        results.append((params, report))

    # Maximize accuracy; break ties toward the more statistically significant edge.
    best_params, best_report = max(
        results, key=lambda pr: (pr[1].sim_accuracy, -pr[1].p_value_vs_best)
    )
    return CalibrationResult(
        best_params=best_params,
        best_report=best_report,
        all_results=results,
    )


def sweep_population(
    adapter: DomainAdapter,
    engine: SimulationEngine,
    events: list[BacktestEvent],
    configs: dict[str, dict[str, float]],
    n_agents: int = 100,
    n_rounds: int = 8,
    baselines: dict[str, Callable[[BacktestEvent], int]] | None = None,
) -> PopulationSweepResult:
    """
    Score named archetype population mixes (e.g. "default", "no_juniors")
    against backtest accuracy with engine dynamics held fixed, to test whether
    an aggregate bias (e.g. always predicting approve) traces to population mix
    rather than the per-agent dynamics. Each value in ``configs`` is an
    archetype_config dict as accepted by DomainAdapter.build_personas.
    """
    results: list[tuple[str, BacktestReport]] = []
    for name, archetype_config in configs.items():
        report = run_backtest(adapter, engine, events, n_agents=n_agents,
                              n_rounds=n_rounds, baselines=baselines,
                              archetype_config=archetype_config)
        results.append((name, report))

    best_name, best_report = max(
        results, key=lambda nr: (nr[1].sim_accuracy, -nr[1].p_value_vs_best)
    )
    return PopulationSweepResult(
        best_config_name=best_name,
        best_report=best_report,
        all_results=results,
    )
