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
    def __init__(self, excluded_argument_tags: "set[str] | None" = None) -> None:
        self._posts: list[SocialPost] = []
        self._by_round: dict[int, list[SocialPost]] = {}
        # Counterfactual replay lever: a post tagged with one of these never
        # enters circulation. "This argument was never raised," not "was
        # raised but discounted."
        self._excluded_tags = excluded_argument_tags or set()

    def add(self, post: SocialPost) -> None:
        if post.argument_tag in self._excluded_tags:
            return
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
    network_churn: float = 0.0         # fraction of follow-edges that changed this round (0 when static)


def rewire_follower_graph(
    agents: list[AgentPersona],
    graph: dict[str, set[str]],
    disagreement_bound: float = 1.2,
    n_influencers: int = 3,
    n_peers: int = 2,
) -> tuple[dict[str, set[str]], float]:
    """
    Reconsider each agent's follow list against current opinions: drop a
    followed peer who's drifted more than disagreement_bound away, refill
    from same-archetype accounts within the bound. Top-influence accounts
    are exempt (followed for reach, not agreement), so only the echo-chamber
    slots rewire: people unfollow peers who turned out to disagree, not the
    loudest voice in the room.

    Returns (new_graph, churn), churn being the fraction of edges that
    changed across all agents, for the round's SocialMetrics.
    """
    by_id = {a.unique_id: a for a in agents}
    top_ids = {
        a.unique_id
        for a in sorted(agents, key=lambda a: a.influence_weight, reverse=True)[:n_influencers]
    }
    by_arch: dict[str, list[str]] = {}
    for a in agents:
        by_arch.setdefault(a.archetype, []).append(a.unique_id)

    new_graph: dict[str, set[str]] = {}
    changed_edges = 0
    total_edges = 0
    for a in agents:
        current = graph.get(a.unique_id, set())
        kept = {
            fid for fid in current
            if fid in top_ids or (
                fid in by_id
                and abs(by_id[fid].current_opinion - a.current_opinion) <= disagreement_bound
            )
        }
        peer_slots = max(0, n_peers - len(kept - top_ids))
        candidates = [
            x for x in by_arch[a.archetype]
            if x != a.unique_id and x not in kept
            and abs(by_id[x].current_opinion - a.current_opinion) <= disagreement_bound
        ]
        refill = random.sample(candidates, min(peer_slots, len(candidates))) if candidates else []
        followed = (kept | top_ids | set(refill)) - {a.unique_id}
        new_graph[a.unique_id] = followed
        changed_edges += len(current ^ followed)
        total_edges += len(current | followed)
    churn = changed_edges / total_edges if total_edges else 0.0
    return new_graph, churn
