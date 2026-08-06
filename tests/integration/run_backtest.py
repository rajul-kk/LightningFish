"""
Backtest CLI: does the simulation beat a naive baseline on real outcomes?

Coding (fully programmatic, objective):
    GITHUB_TOKEN=... python -m tests.integration.run_backtest coding <owner> <repo> [limit]

Finance (price ground truth is point-in-time; event text is not — see
lightningfish_finance.backtest_events caveat). Events come from a small built-in
list of (ticker, date, headline); edit or extend as needed:
    python -m tests.integration.run_backtest finance

Model is controlled via LIGHTNINGFISH_MODEL (default: claude-haiku-4-5-20251001;
use ollama:llama3.2 for a free local run, though small models weaken the sim).

Ground truth (and, for coding, the pulled PR list) is cached to .cache/lightningfish/
so repeated runs against the same events don't re-spend API rate limit. Set
LIGHTNINGFISH_NO_CACHE=1 to force a fresh pull.
"""
from __future__ import annotations

import io
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from lightningfish_core.backtest import (
    BacktestReport,
    llm_baseline,
    run_backtest,
    sign,
)
from lightningfish_core.engine import SimulationEngine
from lightningfish_core.event_cache import CachingAdapter, EventCache, cached_pull_events

_NO_CACHE = os.environ.get("LIGHTNINGFISH_NO_CACHE") == "1"


def _baselines(adapter, engine):
    return {
        "naive": lambda e: sign(adapter.naive_prediction(e.seed)),
        "single_llm": llm_baseline(adapter, engine),
    }


def _sim_size(default_agents: int, default_rounds: int) -> tuple[int, int]:
    """Agent/round counts, overridable via env for cheap local runs."""
    return (
        int(os.environ.get("LIGHTNINGFISH_N_AGENTS", default_agents)),
        int(os.environ.get("LIGHTNINGFISH_N_ROUNDS", default_rounds)),
    )

# A tiny seed list for the finance path. Point-in-time headline text is supplied
# so the naive baseline is not leaking current news. Extend freely.
_FINANCE_EVENTS = [
    ("SMCI", "2024-10-31", "Accounting scandal: auditor resigns, delisting notice, shares crash"),
    ("NVDA", "2024-05-23", "Beats estimates with record data-center revenue, shares surge"),
    ("SIVB", "2023-03-09", "Bank announces large loss and emergency equity raise amid deposit outflows"),
    ("META", "2022-02-02", "Misses on earnings, user growth stalls, shares plunge"),
    ("AAPL", "2024-11-01", "Beats estimates on strong iPhone and services growth"),
]


def _print_report(label: str, report: BacktestReport) -> None:
    print(f"\n=== {label} ===")
    print(report.summary_line())
    base_names = list(report.baseline_accuracy)
    header = "  " + f"{'event':<28} {'sim':>4} " + " ".join(f"{n[:8]:>8}" for n in base_names)
    print(header + f" {'actual':>6}  result")
    for o in report.outcomes:
        mark = "ok " if o.sim_correct else "MISS"
        bases = " ".join(f"{o.baseline_directions[n]:>+8}" for n in base_names)
        print(f"  {o.event_id:<28} {o.sim_direction:>+4} {bases} "
              f"{o.actual_direction:>+6}  {mark}")


def _run_coding(args: list[str]) -> None:
    from lightningfish_coding.backtest_events import pull_pr_events
    from lightningfish_coding.config import CodingDomainAdapter

    if len(args) < 2:
        print("Usage: run_backtest coding <owner> <repo> [limit]")
        sys.exit(1)
    owner, repo = args[0], args[1]
    limit = int(args[2]) if len(args) > 2 else 20
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Note: GITHUB_TOKEN not set — using unauthenticated GitHub API "
              "(60 req/hr; keep limit small, ~8 PRs).")

    adapter = CodingDomainAdapter()
    list_key = f"coding:{owner}/{repo}:{limit}"

    if _NO_CACHE:
        print(f"Pulling up to {limit} closed PRs from {owner}/{repo}... (cache disabled)")
        events = pull_pr_events(owner, repo, token, limit=limit)
    else:
        cache = EventCache(f"{owner}_{repo}")
        adapter = CachingAdapter(adapter, cache)
        events = cached_pull_events(
            cache, list_key, lambda: pull_pr_events(owner, repo, token, limit=limit)
        )
        print(f"Pulling up to {limit} closed PRs from {owner}/{repo}... "
              f"(cache: {len(cache)} entries on disk)")
    print(f"  got {len(events)} events")

    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    engine = SimulationEngine(adapter, model=model)
    n_agents, n_rounds = _sim_size(60, 6)
    report = run_backtest(adapter, engine, events, n_agents=n_agents,
                          n_rounds=n_rounds, baselines=_baselines(adapter, engine))
    _print_report(f"coding {owner}/{repo}", report)


def _run_finance() -> None:
    from lightningfish_finance.backtest_events import pull_ticker_events
    from lightningfish_finance.config import FinanceDomainAdapter

    if not (os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET")):
        print("Warning: REDDIT_CLIENT_ID/SECRET not set — ground truth fetch will fail.")

    print(f"Building {len(_FINANCE_EVENTS)} finance events...")
    events = pull_ticker_events(_FINANCE_EVENTS)
    print(f"  got {len(events)} events")

    adapter = FinanceDomainAdapter()
    if not _NO_CACHE:
        adapter = CachingAdapter(adapter, EventCache("finance_events"))  # type: ignore[assignment]
    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    engine = SimulationEngine(adapter, model=model)
    n_agents, n_rounds = _sim_size(100, 8)
    report = run_backtest(adapter, engine, events, n_agents=n_agents,
                          n_rounds=n_rounds, baselines=_baselines(adapter, engine))
    _print_report("finance", report)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("coding", "finance"):
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] == "coding":
        _run_coding(sys.argv[2:])
    else:
        _run_finance()


if __name__ == "__main__":
    main()
