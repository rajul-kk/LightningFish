"""
Programmatic backtest event source for the coding domain: recent closed PRs
from a real repository, each with its merged/closed outcome available via
get_ground_truth. Fully objective — no hand-labeling.
"""
from __future__ import annotations

import requests

from lightningfish_core.backtest import BacktestEvent

from .seed_enricher import enrich_coding_seed


def pull_pr_events(
    owner: str,
    repo: str,
    token: str,
    limit: int = 20,
) -> list[BacktestEvent]:
    """
    Fetch up to ``limit`` recently-updated closed PRs and enrich each into a
    BacktestEvent. Closed PRs are used because their merge outcome is final.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls",
        headers=headers,
        params={  # type: ignore[arg-type]
            "state": "closed",
            "per_page": limit,
            "sort": "updated",
            "direction": "desc",
        },
    )
    prs = resp.json()
    events: list[BacktestEvent] = []
    if not isinstance(prs, list):
        return events
    for pr in prs:
        url = pr.get("html_url")
        number = pr.get("number")
        if not url or number is None:
            continue
        try:
            seed = enrich_coding_seed(url, github_token=token)
        except Exception:
            continue  # skip PRs we cannot enrich (deleted branch, API hiccup)
        events.append(BacktestEvent(event_id=f"{owner}/{repo}#{number}", seed=seed))
    return events
