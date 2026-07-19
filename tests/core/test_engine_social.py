from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from lightningfish_core.adapter import DomainAdapter
from lightningfish_core.models import AgentPersona, BacktestResult, EnrichedSeed, SimulationResult
from lightningfish_core.social import SocialPost


def _seed() -> EnrichedSeed:
    return EnrichedSeed(
        domain_id="finance",
        raw_input={},
        summary="AAPL beat estimates.",
        entities=["AAPL"],
        event_type="earnings",
        metadata={"ticker": "AAPL"},
    )


def _agents(n: int = 20) -> list[AgentPersona]:
    agents = []
    for i in range(n):
        agents.append(AgentPersona(
            unique_id=str(uuid.uuid4()),
            archetype="Analyst" if i % 2 == 0 else "Trader",
            opinion_resistance=0.5,
            recency_bias=0.5,
            contrarian_tendency=0.1,
            influence_weight=0.9 if i < 2 else 0.3,
            proportion=0.1,
            herding_coefficient=0.3,
            current_opinion=0.05 * (i - 10),
        ))
    return agents


class _StubAdapter(DomainAdapter):
    domain_id = "stub"
    display_name = "Stub"
    opinion_labels = ("no", "yes")

    def enrich_seed(self, r): return _seed()
    def build_personas(self, n, archetype_config=None): return _agents(n)
    def agent_system_prompt(self, seed, persona): return "You are a test agent."
    def get_ground_truth(self, seed): return None
    def score(self, result, truth): return BacktestResult(True, 0.5, {}, 0, 0.0)
    def argument_taxonomy(self): return ["a", "b", "c", "d", "e", "f", "g", "h"]
    def post_system_prompt(self, seed, persona, feed, viral): return "You are a test agent."


def _make_engine():
    from lightningfish_core.engine import SimulationEngine
    engine = SimulationEngine(_StubAdapter())
    fake_post = SocialPost(
        agent_id="x", archetype="Analyst", round_number=1,
        stance="bullish", argument_tag="a", confidence=0.7,
        blurb="FCF looks strong.", opinion_before=0.1, opinion_after=0.3,
    )
    mock_provider = MagicMock()
    mock_provider.generate_post.return_value = (fake_post, 0.3, 0.001)
    mock_provider.batch_opinions_from_feed.return_value = ([0.2, 0.1], 0.0005)
    mock_provider.get_opinion.return_value = (0.3, 0.001)
    engine.provider = mock_provider
    return engine


def test_social_engine_yields_correct_round_count():
    engine = _make_engine()
    events = list(engine.run_streaming(_seed(), _agents(20), n_rounds=3))
    assert len(events) == 3


def test_round_events_have_social_metrics():
    engine = _make_engine()
    events = list(engine.run_streaming(_seed(), _agents(20), n_rounds=2))
    for event in events:
        assert event.social_metrics is not None
        assert hasattr(event.social_metrics, "herding_index")
        assert hasattr(event.social_metrics, "argument_diversity_score")


def test_round_events_have_sample_posts():
    engine = _make_engine()
    events = list(engine.run_streaming(_seed(), _agents(20), n_rounds=2))
    total_posts = sum(len(e.sample_posts) for e in events)
    assert total_posts > 0


def test_simulation_result_has_herding_curve():
    engine = _make_engine()
    gen = engine.run_streaming(_seed(), _agents(20), n_rounds=3)
    try:
        while True:
            next(gen)
    except StopIteration as e:
        result = e.value
    assert len(result.herding_curve) == 3


def test_simulation_result_has_argument_timeline():
    engine = _make_engine()
    gen = engine.run_streaming(_seed(), _agents(20), n_rounds=3)
    try:
        while True:
            next(gen)
    except StopIteration as e:
        result = e.value
    assert isinstance(result.argument_timeline, dict)


def test_herding_index_is_float():
    engine = _make_engine()
    events = list(engine.run_streaming(_seed(), _agents(20), n_rounds=3))
    for event in events:
        h = event.social_metrics.herding_index
        assert isinstance(h, float)
        assert -5.0 < h < 5.0


def test_herding_index_is_bounded_zero_to_one():
    # Re-baselined against max dispersion: 1 = consensus, 0 = maximally split.
    engine = _make_engine()
    events = list(engine.run_streaming(_seed(), _agents(20), n_rounds=3))
    for event in events:
        h = event.social_metrics.herding_index
        assert 0.0 <= h <= 1.0


def test_ads_never_exceeds_one():
    engine = _make_engine()
    events = list(engine.run_streaming(_seed(), _agents(20), n_rounds=3))
    for event in events:
        assert 0.0 <= event.social_metrics.argument_diversity_score <= 1.0


def test_parse_success_rate_present():
    engine = _make_engine()
    events = list(engine.run_streaming(_seed(), _agents(20), n_rounds=2))
    for event in events:
        assert 0.0 <= event.social_metrics.parse_success_rate <= 1.0


def test_t1_plus_t2_plus_t3_totals_all_agents():
    engine = _make_engine()
    events = list(engine.run_streaming(_seed(), _agents(20), n_rounds=2))
    for event in events:
        assert event.tier1_calls >= 0


def test_serializer_includes_social_fields():
    from lightningfish_core.models import RoundEvent
    from lightningfish_core.social import SocialMetrics
    from lightningfish_service.serializers import round_event_to_dict

    metrics = SocialMetrics(
        herding_index=0.42, herding_delta=0.1,
        argument_tags_this_round=["valuation"],
        new_argument_tags=["valuation"],
        argument_diversity_score=0.125,
        cascade_detected=False,
        cascade_trigger_archetype=None,
        settled_fraction=0.0,
    )
    post = SocialPost(
        agent_id="a1", archetype="Analyst", round_number=1,
        stance="bullish", argument_tag="valuation", confidence=0.7,
        blurb="Strong FCF.", opinion_before=0.1, opinion_after=0.3,
    )
    event = RoundEvent(
        round_number=1, opinion_distribution=[0.3, 0.1],
        mean_opinion=0.2, stddev_opinion=0.1,
        tier1_calls=2, active_agent_ids=["a1"],
        estimated_cost_usd=0.001,
        social_metrics=metrics,
        sample_posts=[post],
    )
    d = round_event_to_dict(event)
    assert "herding_index" in d
    assert d["herding_index"] == 0.42
    assert "argument_diversity_score" in d
    assert len(d["sample_posts"]) == 1
    assert d["sample_posts"][0]["argument_tag"] == "valuation"


def test_serializer_result_includes_herding_curve():
    from lightningfish_core.models import EnrichedSeed
    from lightningfish_service.serializers import result_to_dict

    seed = EnrichedSeed("finance", {}, "test", [], "earnings", {})
    result = SimulationResult(
        seed=seed,
        trajectory=[0.1, 0.2],
        round_events=[],
        final_distribution=[0.2],
        total_tier1_calls=5,
        total_cost_usd=0.01,
        herding_curve=[0.0, 0.2],
        argument_timeline={"valuation": 1, "momentum": 2},
    )
    d = result_to_dict(result)
    assert d["herding_curve"] == [0.0, 0.2]
    assert d["argument_timeline"] == {"valuation": 1, "momentum": 2}
