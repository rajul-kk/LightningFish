"""
Finance domain backtest runner.
Usage: python -m lightningfish_finance.run_backtest

Fetches 30 real 8-K filings from SEC EDGAR, runs the simulation harness
on each, and prints a calibration report.

Requires env vars: ANTHROPIC_API_KEY, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
                   SEC_EDGAR_USER_AGENT, REDDIT_USER_AGENT
"""
from __future__ import annotations

import os
import statistics

from edgar import Company, set_identity

from lightningfish_core.backtest_base import BacktestHarness
from lightningfish_core.models import BacktestResult, EnrichedSeed

from .config import FinanceDomainAdapter
from .seed_enricher import enrich_finance_seed

# Tickers covering diverse 8-K event types for meaningful calibration
_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM",
    "BAC", "WMT", "PFE", "JNJ", "XOM", "CVX", "GE", "BA", "DIS",
    "NFLX", "UBER", "LYFT", "SNAP", "RIVN", "PLTR", "COIN",
    "AMC", "GME", "SPCE", "LCID", "F", "GM",
]

N_AGENTS = 200
N_ROUNDS = 8


class FinanceBacktestHarness(BacktestHarness):
    def __init__(self, adapter: FinanceDomainAdapter, seeds: list[EnrichedSeed]) -> None:
        super().__init__(adapter)
        self._seeds = seeds

    def get_seed_events(self) -> list[EnrichedSeed]:
        return self._seeds


def fetch_seeds(n: int = 30) -> list[EnrichedSeed]:
    set_identity(os.environ["SEC_EDGAR_USER_AGENT"])
    seeds: list[EnrichedSeed] = []

    for ticker in _TICKERS:
        if len(seeds) >= n:
            break
        try:
            company = Company(ticker)
            filings = company.get_filings(form="8-K").head(2)
            for filing in filings:
                if len(seeds) >= n:
                    break
                try:
                    doc = filing.obj()
                    text = str(doc)[:4000]
                    filing_date = str(filing.filing_date)
                    seed = enrich_finance_seed(ticker, text, filing_date)
                    seeds.append(seed)
                    print(f"  Fetched {ticker} {filing_date} ({seed.event_type})")
                except Exception as e:
                    print(f"  Skip {ticker} filing: {e}")
        except Exception as e:
            print(f"  Skip {ticker}: {e}")

    return seeds


def print_report(results: list[BacktestResult], held_out: list[BacktestResult]) -> None:
    all_direction = [r.direction_match for r in results]
    all_corr = [r.magnitude_correlation for r in results]
    all_cost = [r.estimated_cost_usd for r in results]
    held_direction = [r.direction_match for r in held_out]

    held_acc = sum(held_direction) / len(held_direction) if held_direction else 0.0

    print("\n" + "=" * 60)
    print("LIGHTNINGFISH — FINANCE DOMAIN CALIBRATION REPORT")
    print("=" * 60)
    print(f"Total simulations:          {len(results)}")
    print(f"Direction accuracy (all):   {sum(all_direction)/len(all_direction):.2%}")
    print(f"Direction accuracy (held):  {held_acc:.2%}  (n={len(held_out)})")
    print(f"Mean magnitude correlation: {statistics.mean(all_corr):.3f}")
    print(f"Mean cost per simulation:   ${statistics.mean(all_cost):.4f}")
    print(f"Total estimated cost:       ${sum(all_cost):.4f}")
    print(f"\nBeat-random threshold (0.55): {'PASS' if held_acc > 0.55 else 'FAIL — reported honestly'}")
    print("=" * 60)


def main() -> None:
    print("Fetching 8-K seed events from SEC EDGAR...")
    seeds = fetch_seeds(n=30)
    if len(seeds) < 10:
        print(f"Only {len(seeds)} seeds fetched — check SEC_EDGAR_USER_AGENT env var.")
        return

    adapter = FinanceDomainAdapter()
    held_seeds = seeds[-10:]
    results: list[BacktestResult] = []
    held_results: list[BacktestResult] = []

    print(f"\nRunning backtest on {len(seeds)} events ({N_AGENTS} agents, {N_ROUNDS} rounds each)...")
    harness = FinanceBacktestHarness(adapter, seeds)

    for i, seed in enumerate(seeds):
        ticker = seed.metadata.get("ticker")
        date = seed.metadata.get("filing_date")
        print(f"  [{i+1}/{len(seeds)}] {ticker} {date} — {seed.event_type}")
        try:
            result = harness.run(seed, n_agents=N_AGENTS, n_rounds=N_ROUNDS)
            results.append(result)
            if seed in held_seeds:
                held_results.append(result)
        except ValueError as e:
            print(f"    Skipped (no ground truth): {e}")
        except Exception as e:
            print(f"    Error: {e}")

    if results:
        print_report(results, held_results or results[-10:])
    else:
        print("No successful simulations — check API keys and network access.")


if __name__ == "__main__":
    main()
