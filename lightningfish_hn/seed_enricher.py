"""
Seed enrichment for the Hacker News domain: builds an EnrichedSeed from a
story's submission-time-invariant fields only.

HARD CONSTRAINT: this module must never read or store points/num_comments in
the seed — those are the backtest's prediction target. Ground truth is
fetched separately, later, by ground_truth.py. See
specs/2026-08-09-hn-sentiment-domain-design.md.
"""
from __future__ import annotations

import re

import requests

from lightningfish_core.models import EnrichedSeed

_ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
_URL_DOMAIN_RE = re.compile(r"^https?://(?:www\.)?([^/]+)")


def fetch_hn_item(story_id: int) -> dict:
    """
    Fetch a story's fields via Algolia search-by-tag. Uses the /search
    endpoint (not /items/<id>) so the response has the same flat field names
    (title, story_text, points, ...) as list/search results — the /items/<id>
    endpoint returns a differently-shaped nested comment tree.
    """
    resp = requests.get(
        f"{_ALGOLIA_BASE}/search",
        params={"tags": f"story_{story_id}"},
    )
    data = resp.json()
    hits = data.get("hits", []) if isinstance(data, dict) else []
    if not hits:
        raise ValueError(f"No Hacker News story found for id {story_id}")
    return hits[0]


def fetch_author_karma(username: str) -> int | None:
    """Author's general HN karma — safe to use since it describes their
    overall reputation, not this specific story's own outcome."""
    if not username:
        return None
    try:
        resp = requests.get(f"{_ALGOLIA_BASE}/users/{username}")
        data = resp.json()
        return data.get("karma") if isinstance(data, dict) else None
    except Exception:
        return None


def _classify_tag(tags: list) -> str:
    if "ask_hn" in tags:
        return "ask_hn"
    if "show_hn" in tags:
        return "show_hn"
    return "story"


def enrich_hn_seed(story_id: int) -> EnrichedSeed:
    item = fetch_hn_item(story_id)

    title = item.get("title") or ""
    story_text = item.get("story_text") or ""
    url = item.get("url") or ""
    author = item.get("author") or ""
    created_at = item.get("created_at") or ""
    tag = _classify_tag(item.get("_tags") or [])

    url_domain_match = _URL_DOMAIN_RE.match(url) if url else None
    url_domain = url_domain_match.group(1) if url_domain_match else ""

    karma = fetch_author_karma(author)

    summary = (
        f"Hacker News submission by {author or 'unknown'}"
        f"{f' (karma: {karma})' if karma is not None else ''}: \"{title}\". "
        f"{f'Links to {url_domain}. ' if url_domain else ''}"
        f"Type: {tag.replace('_', ' ')}."
    )
    if story_text:
        excerpt = story_text if len(story_text) <= 500 else story_text[:500] + "..."
        summary += f"\n\nText: {excerpt}"

    return EnrichedSeed(
        domain_id="hn",
        raw_input={"story_id": story_id},
        summary=summary,
        entities=[author, url_domain] if url_domain else [author],
        event_type=tag,
        metadata={
            "story_id": story_id,
            "title": title,
            "author": author,
            "author_karma": karma,
            "url": url,
            "url_domain": url_domain,
            "tag": tag,
            "created_at": created_at,
        },
    )
