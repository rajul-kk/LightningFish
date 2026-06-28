from __future__ import annotations

import pytest

from lightningfish_core.models import AgentPersona
from lightningfish_core.social import PostStore, SocialMetrics, SocialPost


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
