from __future__ import annotations

import uuid

from lightningfish_core.models import AgentPersona
from lightningfish_core.social import (
    PostStore,
    SocialMetrics,
    SocialPost,
    build_follower_graph,
    rewire_follower_graph,
)


def _agent(influence: float, archetype: str = "A") -> AgentPersona:
    return AgentPersona(
        unique_id=str(uuid.uuid4()), archetype=archetype,
        opinion_resistance=0.5, recency_bias=0.5, contrarian_tendency=0.1,
        influence_weight=influence, proportion=0.1,
    )


def test_follower_graph_everyone_follows_top_influencers():
    agents = [_agent(0.9), _agent(0.85), _agent(0.8)] + [_agent(0.2) for _ in range(10)]
    top_ids = {agents[0].unique_id, agents[1].unique_id, agents[2].unique_id}
    graph = build_follower_graph(agents, n_influencers=3, n_peers=2)
    for a in agents:
        followed = graph[a.unique_id]
        assert a.unique_id not in followed  # never follows self
        # every non-influencer follows all three top influencers
        if a.unique_id not in top_ids:
            assert top_ids <= followed


def test_rewire_drops_a_peer_who_drifted_past_the_bound():
    # No top-influencers in play (n_influencers=0) so only the peer-slot logic
    # is exercised. a follows peer initially; peer's opinion then drifts far
    # away, and rewiring should drop it in favor of a closer same-archetype peer.
    a = _agent(0.3)
    peer_far = _agent(0.3)
    peer_close = _agent(0.3)
    agents = [a, peer_far, peer_close]
    a.current_opinion = 0.0
    peer_far.current_opinion = 0.9        # outside the 0.5 bound
    peer_close.current_opinion = 0.1      # inside the 0.5 bound

    graph = {a.unique_id: {peer_far.unique_id}, peer_far.unique_id: set(), peer_close.unique_id: set()}
    new_graph, churn = rewire_follower_graph(
        agents, graph, disagreement_bound=0.5, n_influencers=0, n_peers=1
    )
    assert peer_far.unique_id not in new_graph[a.unique_id]
    assert peer_close.unique_id in new_graph[a.unique_id]
    assert churn > 0.0


def test_rewire_never_drops_a_top_influencer_for_disagreement():
    influencer = _agent(0.95)
    a = _agent(0.2)
    agents = [influencer, a]
    a.current_opinion = -0.9
    influencer.current_opinion = 0.9  # maximally disagreeing, but still top-influence

    graph = {a.unique_id: {influencer.unique_id}, influencer.unique_id: set()}
    new_graph, _ = rewire_follower_graph(
        agents, graph, disagreement_bound=0.1, n_influencers=1, n_peers=0
    )
    assert influencer.unique_id in new_graph[a.unique_id]


def test_rewire_is_a_no_op_when_nothing_has_drifted():
    a = _agent(0.3)
    peer = _agent(0.3)
    agents = [a, peer]
    a.current_opinion = 0.0
    peer.current_opinion = 0.05

    graph = {a.unique_id: {peer.unique_id}, peer.unique_id: {a.unique_id}}
    new_graph, churn = rewire_follower_graph(
        agents, graph, disagreement_bound=1.0, n_influencers=0, n_peers=1
    )
    assert new_graph[a.unique_id] == {peer.unique_id}
    assert new_graph[peer.unique_id] == {a.unique_id}
    assert churn == 0.0


def test_sample_for_feed_respects_followed_ids():
    store = PostStore()
    author = _agent(0.9)
    other = _agent(0.2)
    for a in (author, other):
        store.add(SocialPost(
            agent_id=a.unique_id, archetype="A", round_number=1,
            stance="bullish", argument_tag="x", confidence=0.5,
            blurb="b", opinion_before=0.0, opinion_after=0.1,
        ))
    reader = _agent(0.3)
    feed = store.sample_for_feed(reader, round_number=2, followed_ids={author.unique_id})
    assert feed and all(p.agent_id == author.unique_id for p in feed)


def _make_post(agent_id: str, archetype: str, rnd: int, tag: str, confidence: float = 0.7) -> SocialPost:
    return SocialPost(
        agent_id=agent_id,
        archetype=archetype,
        round_number=rnd,
        stance="bullish",
        argument_tag=tag,
        confidence=confidence,
        blurb="test blurb",
        opinion_before=0.1,
        opinion_after=0.3,
    )


def _make_agent(archetype: str = "Analyst") -> AgentPersona:
    return AgentPersona(
        unique_id="a1",
        archetype=archetype,
        opinion_resistance=0.5,
        recency_bias=0.5,
        contrarian_tendency=0.1,
        influence_weight=0.8,
        proportion=0.1,
    )


def test_poststore_add_and_all():
    store = PostStore()
    post = _make_post("a1", "Analyst", 1, "valuation")
    store.add(post)
    assert len(store.all_posts()) == 1


def test_poststore_sample_returns_empty_for_round_1():
    store = PostStore()
    store.add(_make_post("a1", "Analyst", 1, "valuation"))
    agent = _make_agent("Analyst")
    result = store.sample_for_feed(agent, round_number=1)
    assert result == []


def test_poststore_sample_prefers_same_archetype():
    store = PostStore()
    for i in range(5):
        store.add(_make_post(f"a{i}", "Analyst", 1, "valuation"))
    for i in range(5):
        store.add(_make_post(f"b{i}", "Trader", 1, "momentum"))
    agent = _make_agent("Analyst")
    feed = store.sample_for_feed(agent, round_number=2, n_same_archetype=3, n_cross_archetype=1)
    same = [p for p in feed if p.archetype == "Analyst"]
    cross = [p for p in feed if p.archetype != "Analyst"]
    assert len(same) == 3
    assert len(cross) == 1


def test_poststore_viral_post_is_highest_confidence():
    store = PostStore()
    store.add(_make_post("a1", "Analyst", 1, "valuation", confidence=0.5))
    store.add(_make_post("a2", "Trader", 1, "momentum", confidence=0.9))
    viral = store.viral_post(round_number=2)
    assert viral is not None
    assert viral.confidence == 0.9


def test_poststore_viral_post_none_if_no_prev_round():
    store = PostStore()
    viral = store.viral_post(round_number=1)
    assert viral is None


def test_social_metrics_fields():
    m = SocialMetrics(
        herding_index=0.0,
        herding_delta=0.0,
        argument_tags_this_round=[],
        new_argument_tags=[],
        argument_diversity_score=0.0,
        cascade_detected=False,
        cascade_trigger_archetype=None,
        settled_fraction=0.0,
    )
    assert m.herding_index == 0.0
    assert not m.cascade_detected


def test_agent_persona_default_herding_coefficient():
    agent = _make_agent()
    assert agent.herding_coefficient == 0.3
