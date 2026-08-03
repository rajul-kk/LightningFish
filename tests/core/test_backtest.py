from __future__ import annotations

from unittest.mock import MagicMock

from lightningfish_core.adapter import DomainAdapter
from lightningfish_core.backtest import BacktestEvent, run_backtest, sign
from lightningfish_core.models import (
    BacktestResult,
    EnrichedSeed,
    GroundTruthRecord,
    SimulationResult,
)


def _seed(sid: str) -> EnrichedSeed:
    return EnrichedSeed(
        domain_id="stub", raw_input={}, summary=sid,
        entities=[], event_type="e", metadata={"id": sid},
    )


class _StubAdapter(DomainAdapter):
    """Adapter whose truth/baseline/sim outcomes are driven by seed metadata."""
    domain_id = "stub"
    display_name = "Stub"
    opinion_labels = ("no", "yes")

    def __init__(self, table):
        # table[id] = (actual_dir, baseline_pred, has_truth)
        self._table = table

    def enrich_seed(self, r): return _seed("x")
    def build_personas(self, n, archetype_config=None): return []
    def agent_system_prompt(self, seed, persona): return ""
    def argument_taxonomy(self): return ["a", "b", "c", "d", "e", "f", "g", "h"]
    def post_system_prompt(self, seed, persona, feed, viral): return ""
    def score(self, result, truth): return BacktestResult(True, 0.0, {}, 0, 0.0)

    def get_ground_truth(self, seed):
        actual, _, has_truth = self._table[seed.metadata["id"]]
        return GroundTruthRecord(data={"actual": actual}) if has_truth else None

    def truth_direction(self, truth):
        return truth.data["actual"]

    def naive_prediction(self, seed):
        return self._table[seed.metadata["id"]][1]


def _engine_returning(sim_by_id):
    """Fake engine whose final trajectory value encodes the sim direction per seed."""
    engine = MagicMock()

    def run(seed, agents, n_rounds):
        return SimulationResult(
            seed=seed, trajectory=[0.0, sim_by_id[seed.metadata["id"]]],
            round_events=[], final_distribution=[], total_tier1_calls=0,
            total_cost_usd=0.0,
        )
    engine.run.side_effect = run
    return engine


def test_sign():
    assert sign(0.3) == 1
    assert sign(-0.3) == -1
    assert sign(0.0) == 0


def test_sim_beats_baseline_when_more_accurate():
    # Two events, opposite directions (majority reference = 50%).
    # Sim gets both right; naive baseline gets both wrong.
    table = {
        "e1": (1, -1.0, True),   # actual up, baseline says down
        "e2": (-1, 1.0, True),   # actual down, baseline says up
    }
    adapter = _StubAdapter(table)
    engine = _engine_returning({"e1": 0.5, "e2": -0.5})  # sim matches actual
    events = [BacktestEvent("e1", _seed("e1")), BacktestEvent("e2", _seed("e2"))]

    report = run_backtest(adapter, engine, events, n_agents=1, n_rounds=1)
    assert report.n_events == 2
    assert report.sim_accuracy == 1.0
    assert report.baseline_accuracy["naive"] == 0.0
    assert report.beats_baselines["naive"] is True
    assert report.majority_class_accuracy == 0.5


def test_baseline_beats_sim():
    table = {"e1": (1, 1.0, True), "e2": (-1, -1.0, True)}  # baseline right, sim wrong
    adapter = _StubAdapter(table)
    engine = _engine_returning({"e1": -0.5, "e2": 0.5})
    events = [BacktestEvent("e1", _seed("e1")), BacktestEvent("e2", _seed("e2"))]
    report = run_backtest(adapter, engine, events, 1, 1)
    assert report.sim_accuracy == 0.0
    assert report.baseline_accuracy["naive"] == 1.0
    assert report.beats_baselines["naive"] is False


def test_majority_class_accuracy_reflects_skew():
    # 3 up, 1 down → majority-class predictor is 75% accurate.
    table = {i: (1, 0.0, True) for i in ("e1", "e2", "e3")}
    table["e4"] = (-1, 0.0, True)
    adapter = _StubAdapter(table)
    engine = _engine_returning({i: 0.1 for i in ("e1", "e2", "e3", "e4")})
    events = [BacktestEvent(i, _seed(i)) for i in ("e1", "e2", "e3", "e4")]
    report = run_backtest(adapter, engine, events, 1, 1)
    assert report.majority_class_accuracy == 0.75


def test_events_without_truth_or_direction_are_skipped():
    table = {
        "e1": (0, 1.0, True),    # has truth but no direction → skip
        "e2": (1, 1.0, False),   # no truth → skip
        "e3": (1, 1.0, True),    # scored
    }
    adapter = _StubAdapter(table)
    engine = _engine_returning({"e1": 0.1, "e2": 0.1, "e3": 0.5})
    events = [BacktestEvent(i, _seed(i)) for i in ("e1", "e2", "e3")]
    report = run_backtest(adapter, engine, events, 1, 1)
    assert report.n_events == 1
    assert report.skipped == 2


def test_finance_baseline_and_truth_direction():
    from lightningfish_finance.config import FinanceDomainAdapter
    a = FinanceDomainAdapter()
    bull = _seed("x")
    bull.summary = "Company beats estimates, record growth, analyst upgrade, shares surge"
    assert sign(a.naive_prediction(bull)) == 1
    bear = _seed("y")
    bear.summary = "Accounting scandal and fraud investigation, delisting, shares crash"
    assert sign(a.naive_prediction(bear)) == -1
    assert a.truth_direction(GroundTruthRecord(data={"price_change_pct": 0.05})) == 1
    assert a.truth_direction(GroundTruthRecord(data={"price_change_pct": -0.05})) == -1


def test_coding_baseline_and_truth_direction():
    from lightningfish_coding.config import CodingDomainAdapter
    a = CodingDomainAdapter()
    with_tests = _seed("x")
    with_tests.metadata = {"is_test_included": True, "ci_pass_rate": 1.0}
    assert sign(a.naive_prediction(with_tests)) == 1
    no_tests = _seed("y")
    no_tests.metadata = {"is_test_included": False, "ci_pass_rate": 0.0}
    assert sign(a.naive_prediction(no_tests)) == -1
    assert a.truth_direction(GroundTruthRecord(data={"merged": True})) == 1
    assert a.truth_direction(GroundTruthRecord(data={"merged": False})) == -1
