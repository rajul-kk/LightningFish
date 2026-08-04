from __future__ import annotations

import re

import requests

from lightningfish_core.models import EnrichedSeed

_TEST_PATTERNS = re.compile(r"(test_|_test\.|spec\.|\.spec\.|__tests__)", re.IGNORECASE)
_GITHUB_NAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]{0,98}[a-zA-Z0-9])?$")
_EXTENSION_TO_LANG = {
    "py": "python", "js": "javascript", "ts": "typescript",
    "go": "go", "rs": "rust", "java": "java", "rb": "ruby",
    "cpp": "cpp", "c": "c", "cs": "csharp", "php": "php",
}


def classify_diff_size(total_lines: int) -> str:
    if total_lines < 50:
        return "xs"
    if total_lines < 200:
        return "s"
    if total_lines < 500:
        return "m"
    if total_lines < 1000:
        return "l"
    return "xl"


def _parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not m:
        raise ValueError(f"Cannot parse GitHub PR URL: {pr_url}")
    return m.group(1), m.group(2), int(m.group(3))


def gh_headers(token: str | None) -> dict[str, str]:
    """GitHub API headers; auth is added only when a token is supplied so
    public repos work unauthenticated (at the lower 60-req/hr rate limit)."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_ci_pass_rate(owner: str, repo: str, sha: str, token: str | None) -> float | None:
    """Fraction of CI check-runs on ``sha`` that succeeded, or None if unknown."""
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/check-runs",
            headers=gh_headers(token),
        )
        runs = resp.json().get("check_runs", []) if isinstance(resp.json(), dict) else []
    except Exception:
        return None
    if not runs:
        return None
    passed = sum(1 for r in runs if r.get("conclusion") == "success")
    return passed / len(runs)


def _diff_summary(files: object, max_files: int = 8, max_patch_chars: int = 600) -> str:
    """Compact per-file change list plus a short patch excerpt from the biggest
    files — signal about the actual change the naive baseline cannot see."""
    if not isinstance(files, list) or not files:
        return ""
    ranked = sorted(
        files, key=lambda f: f.get("additions", 0) + f.get("deletions", 0), reverse=True
    )
    lines = [
        f"  {f.get('filename', '?')} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})"
        for f in ranked[:max_files]
    ]
    out = "Files changed:\n" + "\n".join(lines)
    patches = "\n".join(f.get("patch", "") for f in ranked[:2] if f.get("patch"))
    if patches:
        out += "\n\nDiff excerpt:\n" + patches[:max_patch_chars]
    return out


def enrich_coding_seed(pr_url: str, github_token: str | None) -> EnrichedSeed:
    owner, repo, pr_number = _parse_pr_url(pr_url)
    if not _GITHUB_NAME_RE.match(owner) or not _GITHUB_NAME_RE.match(repo):
        raise ValueError(f"Invalid GitHub owner/repo name: {owner!r}/{repo!r}")
    headers = gh_headers(github_token)
    base = f"https://api.github.com/repos/{owner}/{repo}"

    pr = requests.get(f"{base}/pulls/{pr_number}", headers=headers).json()
    files = requests.get(f"{base}/pulls/{pr_number}/files", headers=headers).json()
    author = pr["user"]["login"]

    author_search = requests.get(
        "https://api.github.com/search/issues",
        headers=headers,
        params={  # type: ignore[arg-type]
            "q": f"author:{author} repo:{owner}/{repo} type:pr is:merged",
            "per_page": 1,
        },
    ).json()
    author_pr_history = author_search.get("total_count", 0)

    total_lines = pr.get("additions", 0) + pr.get("deletions", 0)
    filenames = [f["filename"] for f in files] if isinstance(files, list) else []
    extensions = {fn.rsplit(".", 1)[-1] for fn in filenames if "." in fn}
    languages = sorted({_EXTENSION_TO_LANG[ext] for ext in extensions if ext in _EXTENSION_TO_LANG})
    is_test_included = any(_TEST_PATTERNS.search(fn) for fn in filenames)

    body = pr.get("body") or ""
    linked_issue = re.search(r"(?:closes?|fixes?|resolves?)\s+#(\d+)", body, re.IGNORECASE)
    linked_issue_num = int(linked_issue.group(1)) if linked_issue else None

    head_sha = pr.get("head", {}).get("sha")
    ci_pass_rate = fetch_ci_pass_rate(owner, repo, head_sha, github_token) if head_sha else None
    ci_str = "unknown" if ci_pass_rate is None else f"{ci_pass_rate:.0%} passing"

    description = body.strip()
    if len(description) > 400:
        description = description[:400] + "..."
    diff_summary = _diff_summary(files)

    summary = (
        f"PR #{pr_number} in {owner}/{repo}: {pr.get('title', '')}. "
        f"{total_lines} lines changed ({classify_diff_size(total_lines)}), "
        f"languages: {', '.join(languages) or 'unknown'}. "
        f"Tests {'included' if is_test_included else 'not included'}. "
        f"CI: {ci_str}. Author has {author_pr_history} prior merged PRs."
    )
    if description:
        summary += f"\n\nDescription: {description}"
    if diff_summary:
        summary += f"\n\n{diff_summary}"

    return EnrichedSeed(
        domain_id="coding",
        raw_input={"pr_url": pr_url, "pr_number": pr_number, "owner": owner, "repo": repo},
        summary=summary,
        entities=[f"{owner}/{repo}", f"PR#{pr_number}"],
        event_type="bugfix" if linked_issue_num else "feature",
        metadata={
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
            "diff_size_tier": classify_diff_size(total_lines),
            "languages_touched": languages,
            "is_test_included": is_test_included,
            "author_pr_history": author_pr_history,
            "linked_issue": linked_issue_num,
            "ci_pass_rate": ci_pass_rate,
        },
    )
