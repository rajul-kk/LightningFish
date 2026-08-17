"""The controversy axis scores whether the crowd splits, not which way it leans."""
from lightningfish_core.models import EnrichedSeed, GroundTruthRecord, SimulationResult
from lightningfish_hn.config import HNControversyAdapter, HNDomainAdapter


def _truth(points, comments):
    return GroundTruthRecord(data={"points": points, "num_comments": comments})


_SEED = EnrichedSeed(domain_id="hn", raw_input={}, summary="A story",
                     entities=[], event_type="story", metadata={})


def _result(distribution, final_mean=0.0):
    return SimulationResult(
        seed=_SEED, trajectory=[final_mean], final_distribution=distribution,
        round_events=[], total_tier1_calls=0, total_cost_usd=0.0,
    )


def test_high_comment_ratio_is_contested():
    a = HNControversyAdapter()
    assert a.truth_direction(_truth(110, 217)) == 1     # ratio 1.97
    assert a.truth_direction(_truth(56, 76)) == 1       # ratio 1.36


def test_low_comment_ratio_is_consensus():
    a = HNControversyAdapter()
    assert a.truth_direction(_truth(103, 4)) == -1      # ratio 0.04
    assert a.truth_direction(_truth(182, 24)) == -1     # ratio 0.13


def test_midrange_ratio_is_skipped():
    assert HNControversyAdapter().truth_direction(_truth(100, 50)) == 0  # 0.50


def test_low_point_stories_are_skipped_not_called_uncontroversial():
    """0 comments on a 1-point story is obscurity, not agreement. Scoring it as
    consensus would flood the sample with a class that carries no signal."""
    a = HNControversyAdapter()
    assert a.truth_direction(_truth(1, 0)) == 0
    assert a.truth_direction(_truth(4, 0)) == 0
    assert a.truth_direction(_truth(19, 0)) == 0


def test_split_crowd_predicts_contested():
    a = HNControversyAdapter()
    polarised = [-0.9, 0.9, -0.8, 0.85, -0.95, 0.9]
    assert a.sim_direction(_result(polarised)) == 1


def test_converged_crowd_predicts_consensus():
    a = HNControversyAdapter()
    agreed = [0.71, 0.69, 0.72, 0.70, 0.68, 0.71]
    assert a.sim_direction(_result(agreed)) == -1


def test_dispersion_is_independent_of_which_way_the_crowd_leans():
    """The whole point: two runs with opposite means but identical spread must
    produce the same controversy call."""
    a = HNControversyAdapter()
    positive = [0.1, 0.9, 0.2, 0.95, 0.15, 0.85]
    negative = [-x for x in positive]
    assert a.sim_direction(_result(positive, 0.5)) == a.sim_direction(_result(negative, -0.5))


def test_default_adapter_still_scores_the_mean():
    """The new hook must not change existing domains' behaviour."""
    a = HNDomainAdapter()
    assert a.sim_direction(_result([0.0], final_mean=0.4)) == 1
    assert a.sim_direction(_result([0.0], final_mean=-0.4)) == -1


def test_controversy_llm_baseline_asks_about_disagreement():
    """Rung 2 must be asked the same question the sim answers, or it is rigged."""
    seed = EnrichedSeed(domain_id="hn", raw_input={}, summary="A story",
                        entities=[], event_type="story", metadata={})
    prompt = HNControversyAdapter().baseline_llm_prompt(seed).lower()
    assert "disagreement" in prompt or "contested" in prompt
    assert "viral" not in prompt
