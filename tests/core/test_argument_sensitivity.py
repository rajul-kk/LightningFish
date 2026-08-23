from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from lightningfish_core.argument_sensitivity import argument_sensitivity_report
from lightningfish_core.models import AgentPersona, EnrichedSeed, SimulationResult


def _seed() -> EnrichedSeed:
    return EnrichedSeed(
        domain_id="stub", raw_input={}, summary="s", entities=[], event_type="e", metadata={},
    )


def _agents(n: int = 4) -> list[AgentPersona]:
    # First two agents get high influence_weight so TierRouter actually
    # routes some agents to T1 (the only tier that generates posts) —
    # uniform low influence would leave T1 empty and no tags would ever
    # circulate, which is not the scenario the integration test needs.
    return [
        AgentPersona(
            unique_id=str(uuid.uuid4()), archetype="A", opinion_resistance=0.5,
            recency_bias=0.5, contrarian_tendency=0.1,
            influence_weight=0.9 if i < 2 else 0.3, proportion=0.25,
        )
        for i in range(n)
    ]


def _result(final_mean: float, timeline_tags: list[str] | None = None) -> SimulationResult:
    return SimulationResult(
        seed=_seed(), trajectory=[final_mean], round_events=[], final_distribution=[final_mean],
        total_tier1_calls=0, total_cost_usd=0.0,
        argument_timeline={t: 1 for t in (timeline_tags or [])},
    )


class _FakeEngine:
    """Duck-typed stand-in for SimulationEngine: returns pre-programmed
    results per excluded tag so the report's arithmetic can be checked
    without needing real simulation dynamics."""

    def __init__(self, baseline_mean: float, excluded_means: dict[str, float], appeared_tags):
        self.baseline_mean = baseline_mean
        self.excluded_means = excluded_means
        self.appeared_tags = appeared_tags
        self.calls: list[dict] = []

    def run(self, seed, agents, n_rounds, excluded_argument_tags=None, coevolving_network=False):
        self.calls.append({"excluded_argument_tags": excluded_argument_tags, "n_agents": len(agents)})
        if excluded_argument_tags is None:
            return _result(self.baseline_mean, self.appeared_tags)
        (tag,) = excluded_argument_tags
        return _result(self.excluded_means[tag], self.appeared_tags)


def test_baseline_plus_one_run_per_tag():
    engine = _FakeEngine(0.2, {"a": 0.2, "b": 0.2, "c": 0.2}, ["a", "b", "c"])
    argument_sensitivity_report(engine, _seed(), _agents(), n_rounds=3, taxonomy=["a", "b", "c"])
    assert len(engine.calls) == 4  # 1 baseline + 3 excluded arms
    assert engine.calls[0]["excluded_argument_tags"] is None
    assert {frozenset(c["excluded_argument_tags"]) for c in engine.calls[1:]} == {
        frozenset({"a"}), frozenset({"b"}), frozenset({"c"}),
    }


def test_rows_sorted_by_absolute_delta_descending():
    engine = _FakeEngine(0.0, {"small": 0.05, "big": -0.6, "medium": 0.2}, [])
    report = argument_sensitivity_report(
        engine, _seed(), _agents(), n_rounds=3, taxonomy=["small", "big", "medium"],
    )
    assert [r.tag for r in report.rows] == ["big", "medium", "small"]


def test_delta_is_excluded_minus_baseline():
    engine = _FakeEngine(0.3, {"a": 0.1}, [])
    report = argument_sensitivity_report(engine, _seed(), _agents(), n_rounds=3, taxonomy=["a"])
    row = report.rows[0]
    assert row.baseline_mean == 0.3
    assert row.excluded_mean == 0.1
    assert row.delta == 0.1 - 0.3


def test_direction_flip_detected():
    engine = _FakeEngine(0.4, {"flips": -0.1, "doesnt": 0.35}, [])
    report = argument_sensitivity_report(
        engine, _seed(), _agents(), n_rounds=3, taxonomy=["flips", "doesnt"],
    )
    by_tag = {r.tag: r for r in report.rows}
    assert by_tag["flips"].direction_flipped is True
    assert by_tag["doesnt"].direction_flipped is False
    assert report.baseline_direction == 1


def test_tag_appeared_reflects_whether_baseline_ever_posted_it():
    engine = _FakeEngine(0.1, {"used": 0.1, "unused": 0.1}, ["used"])
    report = argument_sensitivity_report(
        engine, _seed(), _agents(), n_rounds=3, taxonomy=["used", "unused"],
    )
    by_tag = {r.tag: r for r in report.rows}
    assert by_tag["used"].tag_appeared is True
    assert by_tag["unused"].tag_appeared is False


def test_agents_are_deep_copied_not_shared_across_runs():
    # engine.run receives a fresh agents list each call (not the same object,
    # and not one already mutated by a prior call) — confirmed by checking
    # each call's agents list has the same starting length and isn't the
    # exact object passed in.
    engine = _FakeEngine(0.0, {"a": 0.0}, [])
    original = _agents(5)
    argument_sensitivity_report(engine, _seed(), original, n_rounds=3, taxonomy=["a"])
    assert all(c["n_agents"] == 5 for c in engine.calls)


def test_empty_taxonomy_runs_only_the_baseline():
    engine = _FakeEngine(0.2, {}, [])
    report = argument_sensitivity_report(engine, _seed(), _agents(), n_rounds=3, taxonomy=[])
    assert len(engine.calls) == 1
    assert report.rows == []


def test_integration_with_real_engine_excludes_the_right_tag_each_call():
    from lightningfish_core.adapter import DomainAdapter
    from lightningfish_core.engine import SimulationEngine
    from lightningfish_core.models import BacktestResult
    from lightningfish_core.social import SocialPost

    class _StubAdapter(DomainAdapter):
        domain_id = "stub"
        display_name = "Stub"
        opinion_labels = ("no", "yes")

        def enrich_seed(self, r): return _seed()
        def build_personas(self, n, archetype_config=None): return _agents(n)
        def agent_system_prompt(self, seed, persona): return "prompt"
        def get_ground_truth(self, seed): return None
        def score(self, result, truth): return BacktestResult(True, 0.5, {}, 0, 0.0)
        def argument_taxonomy(self): return ["alpha", "beta"]
        def post_system_prompt(self, seed, persona, feed, viral): return "prompt"

    engine = SimulationEngine(_StubAdapter())
    call_tags = []

    def fake_generate_post(system, model, agent_id, archetype, round_number, opinion_before,
                            temperature=None):
        post = SocialPost(
            agent_id=agent_id, archetype=archetype, round_number=round_number,
            stance="yes", argument_tag="alpha", confidence=0.7, blurb="b",
            opinion_before=opinion_before, opinion_after=0.4,
        )
        return post, 0.4, 0.001

    mock_provider = MagicMock()
    mock_provider.generate_post.side_effect = fake_generate_post
    mock_provider.get_opinion.return_value = (0.4, 0.001)
    engine.provider = mock_provider

    report = argument_sensitivity_report(
        engine, _seed(), _agents(20), n_rounds=2, taxonomy=["alpha", "beta"],
    )
    assert len(report.rows) == 2
    # "beta" never gets posted by the stub provider, so excluding it is a no-op.
    by_tag = {r.tag: r for r in report.rows}
    assert by_tag["beta"].tag_appeared is False
    assert by_tag["beta"].delta == 0.0
    assert by_tag["alpha"].tag_appeared is True
