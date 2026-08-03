from __future__ import annotations

from unittest.mock import MagicMock

from lightningfish_core.adapter import DomainAdapter
from lightningfish_core.backtest import BacktestEvent
from lightningfish_core.calibration import grid_search
from lightningfish_core.models import (
    BacktestResult,
    EnrichedSeed,
    GroundTruthRecord,
    SimulationResult,
)


def _seed(sid: str, actual: int) -> EnrichedSeed:
    return EnrichedSeed(
        domain_id="stub", raw_input={}, summary=sid,
        entities=[], event_type="e", metadata={"id": sid, "actual": actual},
    )


class _StubAdapter(DomainAdapter):
    domain_id = "stub"
    display_name = "Stub"
    opinion_labels = ("no", "yes")

    def enrich_seed(self, r): return _seed("x", 1)
    def build_personas(self, n, archetype_config=None): return []
    def agent_system_prompt(self, seed, persona): return ""
    def argument_taxonomy(self): return ["a", "b", "c", "d", "e", "f", "g", "h"]
    def post_system_prompt(self, seed, persona, feed, viral): return ""
    def score(self, result, truth): return BacktestResult(True, 0.0, {}, 0, 0.0)
    def get_ground_truth(self, seed):
        return GroundTruthRecord(data={"actual": seed.metadata["actual"]})
    def truth_direction(self, truth): return truth.data["actual"]
    def naive_prediction(self, seed): return 0.0  # baseline always wrong-ish


def _factory(good_weight: float):
    """Engine factory: the engine only predicts correctly when the swept
    global_herd_weight equals ``good_weight``."""
    def make(params):
        engine = MagicMock()
        correct = params["global_herd_weight"] == good_weight

        def run(seed, agents, n_rounds):
            actual = seed.metadata["actual"]
            val = 0.5 * actual if correct else -0.5 * actual
            return SimulationResult(
                seed=seed, trajectory=[0.0, val], round_events=[],
                final_distribution=[], total_tier1_calls=0, total_cost_usd=0.0,
            )
        engine.run.side_effect = run
        return engine
    return make


def test_grid_search_picks_best_param():
    adapter = _StubAdapter()
    events = [
        BacktestEvent("e1", _seed("e1", 1)),
        BacktestEvent("e2", _seed("e2", -1)),
        BacktestEvent("e3", _seed("e3", 1)),
    ]
    grid = {"global_herd_weight": [0.1, 0.3, 0.5]}
    result = grid_search(
        adapter, events, grid, engine_factory=_factory(0.3),
        n_agents=1, n_rounds=1,
    )
    assert result.best_params["global_herd_weight"] == 0.3
    assert result.best_report.sim_accuracy == 1.0
    assert len(result.all_results) == 3


def test_grid_search_covers_full_product():
    adapter = _StubAdapter()
    events = [BacktestEvent("e1", _seed("e1", 1))]
    grid = {"global_herd_weight": [0.1, 0.3], "momentum_weight": [0.0, 0.2, 0.4]}
    result = grid_search(
        adapter, events, grid, engine_factory=_factory(0.3), n_agents=1, n_rounds=1,
    )
    assert len(result.all_results) == 6  # 2 x 3 combinations
