from __future__ import annotations

import random
from dataclasses import dataclass

from .models import AgentPersona


@dataclass
class SocialPost:
    agent_id: str
    archetype: str
    round_number: int
    stance: str           # domain-specific pole label e.g. "bullish" / "bearish"
    argument_tag: str     # one tag from the domain taxonomy
    confidence: float     # 0.0–1.0
    blurb: str            # one sentence, ≤60 words
    opinion_before: float
    opinion_after: float
    parse_ok: bool = True  # False if the structured LLM output could not be parsed


class PostStore:
    def __init__(self) -> None:
        self._posts: list[SocialPost] = []
        self._by_round: dict[int, list[SocialPost]] = {}

    def add(self, post: SocialPost) -> None:
        self._posts.append(post)
        self._by_round.setdefault(post.round_number, []).append(post)

    def sample_for_feed(
        self,
        agent: AgentPersona,
        round_number: int,
        followed_ids: "set[str] | None" = None,
        n_same_archetype: int = 3,
        n_cross_archetype: int = 2,
    ) -> list[SocialPost]:
        prev = [p for p in self._posts if p.round_number < round_number]
        if not prev:
            return []
        if followed_ids is not None:
            # Structured feed: only posts authored by accounts this agent follows.
            followed = [p for p in prev if p.agent_id in followed_ids]
            k = n_same_archetype + n_cross_archetype
            return random.sample(followed, min(k, len(followed))) if followed else []
        # Fallback: random same/cross-archetype mix.
        same = [p for p in prev if p.archetype == agent.archetype]
        cross = [p for p in prev if p.archetype != agent.archetype]
        return (
            random.sample(same, min(n_same_archetype, len(same)))
            + random.sample(cross, min(n_cross_archetype, len(cross)))
        )

    def viral_post(self, round_number: int) -> SocialPost | None:
        prev = self._by_round.get(round_number - 1, [])
        return max(prev, key=lambda p: p.confidence, default=None)

    def all_posts(self) -> list[SocialPost]:
        return list(self._posts)


def build_follower_graph(
    agents: list[AgentPersona],
    n_influencers: int = 3,
    n_peers: int = 2,
) -> dict[str, set[str]]:
    """
    Map each agent to the accounts it follows: the top-influence agents (whom
    everyone watches, so their posts propagate widely) plus a few same-archetype
    peers (echo chambers). Makes feed exposure structural rather than random.
    """
    top_ids = [
        a.unique_id
        for a in sorted(agents, key=lambda a: a.influence_weight, reverse=True)[:n_influencers]
    ]
    by_arch: dict[str, list[str]] = {}
    for a in agents:
        by_arch.setdefault(a.archetype, []).append(a.unique_id)

    graph: dict[str, set[str]] = {}
    for a in agents:
        peers = [x for x in by_arch[a.archetype] if x != a.unique_id]
        chosen = random.sample(peers, min(n_peers, len(peers))) if peers else []
        followed = set(top_ids) | set(chosen)
        followed.discard(a.unique_id)  # never follow self
        graph[a.unique_id] = followed
    return graph


@dataclass
class SocialMetrics:
    herding_index: float               # 1 - CSAD_t/CSAD_0; <0=bifurcation, 0=no herd, 1=full herd
    herding_delta: float               # change from previous round
    argument_tags_this_round: list[str]
    new_argument_tags: list[str]       # tags appearing for the first time
    argument_diversity_score: float    # unique tags seen / taxonomy size
    cascade_detected: bool             # movement exceeds z-score threshold vs history
    cascade_trigger_archetype: str | None
    settled_fraction: float            # fraction of agents no longer updating
    parse_success_rate: float = 1.0    # fraction of T1 posts whose format parsed cleanly
