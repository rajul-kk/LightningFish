"""
Programmatic backtest event source for the coding domain: closed PRs from a real
repository, each with its merged/closed outcome available via get_ground_truth.
Fully objective — no hand-labeling.

The sample is CLASS-BALANCED (half merged, half unmerged) via the search API,
because naively listing "recently updated closed PRs" over-samples rejections on
mature repos that batch-close stale PRs — which would let a trivial always-block
baseline look perfect. A balanced sample makes "beats baseline" meaningful.
"""
from __future__ import annotations

import requests

from lightningfish_core.backtest import BacktestEvent

from .seed_enricher import enrich_coding_seed, gh_headers


def _search_pr_numbers(
    owner: str, repo: str, qualifier: str, count: int, token: str | None
) -> list[int]:
    resp = requests.get(
        "https://api.github.com/search/issues",
        headers=gh_headers(token),
        params={  # type: ignore[arg-type]
            "q": f"repo:{owner}/{repo} is:pr {qualifier}",
            "per_page": count,
            "sort": "created",
            "order": "desc",
        },
    )
    items = resp.json().get("items", []) if isinstance(resp.json(), dict) else []
    return [it["number"] for it in items if "number" in it]


def pull_pr_events(
    owner: str,
    repo: str,
    token: str | None = None,
    limit: int = 20,
) -> list[BacktestEvent]:
    """
    Fetch a class-balanced set of up to ``limit`` closed PRs (half merged, half
    unmerged) and enrich each into a BacktestEvent. A token is optional (public
    repos work unauthenticated at 60 req/hr — keep ``limit`` small).
    """
    half = max(1, limit // 2)
    merged = _search_pr_numbers(owner, repo, "is:merged", half, token)
    unmerged = _search_pr_numbers(owner, repo, "is:unmerged is:closed", half, token)
    # Interleave so a truncated/rate-limited run still sees both classes.
    numbers: list[int] = []
    for i in range(max(len(merged), len(unmerged))):
        if i < len(merged):
            numbers.append(merged[i])
        if i < len(unmerged):
            numbers.append(unmerged[i])

    events: list[BacktestEvent] = []
    for number in numbers:
        url = f"https://github.com/{owner}/{repo}/pull/{number}"
        try:
            seed = enrich_coding_seed(url, github_token=token)
        except Exception:
            continue  # skip PRs we cannot enrich (deleted branch, API hiccup)
        events.append(BacktestEvent(event_id=f"{owner}/{repo}#{number}", seed=seed))
    return events
