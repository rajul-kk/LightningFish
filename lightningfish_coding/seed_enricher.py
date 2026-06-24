from __future__ import annotations
import re
import requests
from lightningfish_core.models import EnrichedSeed

_TEST_PATTERNS = re.compile(r"(test_|_test\.|spec\.|\.spec\.|__tests__)", re.IGNORECASE)
_EXTENSION_TO_LANG = {
    "py": "python", "js": "javascript", "ts": "typescript",
    "go": "go", "rs": "rust", "java": "java", "rb": "ruby",
    "cpp": "cpp", "c": "c", "cs": "csharp", "php": "php",
}


def classify_diff_size(total_lines: int) -> str:
    if total_lines < 50:    return "xs"
    if total_lines < 200:   return "s"
    if total_lines < 500:   return "m"
    if total_lines < 1000:  return "l"
    return "xl"


def _parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not m:
        raise ValueError(f"Cannot parse GitHub PR URL: {pr_url}")
    return m.group(1), m.group(2), int(m.group(3))


def enrich_coding_seed(pr_url: str, github_token: str) -> EnrichedSeed:
    owner, repo, pr_number = _parse_pr_url(pr_url)
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    base = f"https://api.github.com/repos/{owner}/{repo}"

    pr = requests.get(f"{base}/pulls/{pr_number}", headers=headers).json()
    files = requests.get(f"{base}/pulls/{pr_number}/files", headers=headers).json()
    author = pr["user"]["login"]

    author_search = requests.get(
        "https://api.github.com/search/issues",
        headers=headers,
        params={
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

    summary = (
        f"PR #{pr_number} in {owner}/{repo}: {pr.get('title', '')}. "
        f"{total_lines} lines changed ({classify_diff_size(total_lines)}), "
        f"languages: {', '.join(languages) or 'unknown'}. "
        f"Tests {'included' if is_test_included else 'not included'}."
    )

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
            "ci_pass_rate": None,
        },
    )
