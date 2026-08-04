from __future__ import annotations

import requests

from lightningfish_core.models import GroundTruthRecord

from .seed_enricher import fetch_ci_pass_rate, gh_headers

__all__ = ["fetch_ci_pass_rate", "get_coding_ground_truth"]


def get_coding_ground_truth(
    owner: str, repo: str, pr_number: int, token: str | None
) -> GroundTruthRecord:
    headers = gh_headers(token)
    base = f"https://api.github.com/repos/{owner}/{repo}"

    pr = requests.get(f"{base}/pulls/{pr_number}", headers=headers).json()
    reviews = requests.get(f"{base}/pulls/{pr_number}/reviews", headers=headers).json()

    sha = pr.get("head", {}).get("sha")
    ci_pass_rate = fetch_ci_pass_rate(owner, repo, sha, token) if sha else None

    approval_sequence = [r["state"] for r in reviews] if isinstance(reviews, list) else []

    return GroundTruthRecord(data={
        "merged": pr.get("merged", False),
        "comment_count": pr.get("comments", 0),
        "approval_sequence": approval_sequence,
        "ci_pass_rate": ci_pass_rate,
    })
