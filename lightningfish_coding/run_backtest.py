"""
Coding domain backtest runner.
Usage: python -m lightningfish_coding.run_backtest

Fetches 30 closed PRs from public repos, runs the simulation harness
on each, and prints a calibration report in the same format as the finance runner.

Requires env vars: ANTHROPIC_API_KEY, GITHUB_TOKEN
"""
from __future__ import annotations

import os
import statistics

import requests

from lightningfish_core.backtest_base import BacktestHarness
from lightningfish_core.models import BacktestResult, EnrichedSeed

from .config import CodingDomainAdapter
from .ground_truth import get_coding_ground_truth
from .seed_enricher import enrich_coding_seed

# Public repos with diverse PR patterns for calibration
_REPOS = [
    ("pallets", "flask"),
    ("psf", "requests"),
    ("tiangolo", "fastapi"),
    ("django", "django"),
    ("encode", "httpx"),
    ("pydantic", "pydantic"),
    ("sqlalchemy", "sqlalchemy"),
    ("aio-libs", "aiohttp"),
]

N_AGENTS = 150
N_ROUNDS = 8


class CodingBacktestHarness(BacktestHarness):
    def __init__(self, adapter: CodingDomainAdapter, seeds: list[EnrichedSeed]) -> None:
        super().__init__(adapter)
        self._seeds = seeds

    def get_seed_events(self) -> list[EnrichedSeed]:
        return self._seeds


def fetch_seeds(n: int = 30) -> list[EnrichedSeed]:
    token = os.environ["GITHUB_TOKEN"]
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    seeds: list[EnrichedSeed] = []

    for owner, repo in _REPOS:
        if len(seeds) >= n:
            break
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers=headers,
            params={"state": "closed", "per_page": 10, "sort": "updated"},  # type: ignore[arg-type]
        )
        if resp.status_code != 200:
            print(f"  Skip {owner}/{repo}: HTTP {resp.status_code}")
            continue
        for pr in resp.json():
            if len(seeds) >= n:
                break
            pr_number = pr["number"]
            pr_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}"
            try:
                seed = enrich_coding_seed(pr_url, github_token=token)
                gt = get_coding_ground_truth(owner, repo, pr_number, token)
                seed.metadata["ci_pass_rate"] = gt.data.get("ci_pass_rate")
                seeds.append(seed)
                print(f"  Fetched {owner}/{repo}#{pr_number} ({seed.metadata['diff_size_tier']})")
            except Exception as e:
                print(f"  Skip {owner}/{repo}#{pr_number}: {e}")

    return seeds


def print_report(results: list[BacktestResult], held_out: list[BacktestResult]) -> None:
    all_match = [r.direction_match for r in results]
    all_cost = [r.estimated_cost_usd for r in results]
    held_match = [r.direction_match for r in held_out]

    held_acc = sum(held_match) / len(held_match) if held_match else 0.0

    print("\n" + "=" * 60)
    print("LIGHTNINGFISH — CODING DOMAIN CALIBRATION REPORT")
    print("=" * 60)
    print(f"Total simulations:          {len(results)}")
    print(f"Outcome accuracy (all):     {sum(all_match)/len(all_match):.2%}")
    print(f"Outcome accuracy (held):    {held_acc:.2%}  (n={len(held_out)})")
    print(f"Mean cost per simulation:   ${statistics.mean(all_cost):.4f}")
    print(f"Total estimated cost:       ${sum(all_cost):.4f}")
    print(f"\nBeat-random threshold (0.55): {'PASS' if held_acc > 0.55 else 'FAIL — reported honestly'}")
    print("=" * 60)


def main() -> None:
    print("Fetching PR seed events from GitHub...")
    seeds = fetch_seeds(n=30)
    if len(seeds) < 10:
        print(f"Only {len(seeds)} seeds fetched. Check GITHUB_TOKEN and rate limits.")
        return

    adapter = CodingDomainAdapter()
    held_seeds = seeds[-10:]
    results: list[BacktestResult] = []
    held_results: list[BacktestResult] = []

    print(f"\nRunning backtest on {len(seeds)} PRs ({N_AGENTS} agents, {N_ROUNDS} rounds each)...")
    harness = CodingBacktestHarness(adapter, seeds)

    for i, seed in enumerate(seeds):
        meta = seed.metadata
        print(f"  [{i+1}/{len(seeds)}] {meta.get('owner')}/{meta.get('repo')}#{meta.get('pr_number')}")
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
        print("No successful simulations — check API keys.")


if __name__ == "__main__":
    main()
