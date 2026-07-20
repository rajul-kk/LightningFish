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
"""
from __future__ import annotations

import io
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from lightningfish_core.backtest import BacktestReport, run_backtest
from lightningfish_core.engine import SimulationEngine

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
    print(f"  {'event':<28} {'sim':>4} {'base':>4} {'actual':>6}  result")
    for o in report.outcomes:
        mark = "ok " if o.sim_correct else "MISS"
        print(f"  {o.event_id:<28} {o.sim_direction:>+4} {o.baseline_direction:>+4} "
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
        print("Error: GITHUB_TOKEN not set.")
        sys.exit(1)

    print(f"Pulling up to {limit} closed PRs from {owner}/{repo}...")
    events = pull_pr_events(owner, repo, token, limit=limit)
    print(f"  got {len(events)} events")

    adapter = CodingDomainAdapter()
    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    engine = SimulationEngine(adapter, model=model)
    report = run_backtest(adapter, engine, events, n_agents=60, n_rounds=6)
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
    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    engine = SimulationEngine(adapter, model=model)
    report = run_backtest(adapter, engine, events, n_agents=100, n_rounds=8)
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
