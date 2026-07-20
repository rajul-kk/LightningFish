"""
Backtest harness: does the simulation predict real outcomes better than a
trivial baseline?

For each historical event we compare three directional calls against the actual
outcome:
  - the simulation's final mean opinion,
  - a naive baseline the domain defines (e.g. sign of headline sentiment), and
  - the ground truth (e.g. sign of the subsequent price move / PR merged).

A simulation that cannot beat the naive baseline is not adding value, so the
report leads with that comparison rather than raw accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .adapter import DomainAdapter
from .engine import SimulationEngine
from .models import EnrichedSeed


def sign(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)


@dataclass
class BacktestEvent:
    """A single scored event: an already-enriched seed plus a stable id."""
    event_id: str
    seed: EnrichedSeed


@dataclass
class EventOutcome:
    event_id: str
    sim_direction: int
    baseline_direction: int
    actual_direction: int
    sim_correct: bool
    baseline_correct: bool


@dataclass
class BacktestReport:
    n_events: int
    sim_accuracy: float
    baseline_accuracy: float
    beats_baseline: bool
    outcomes: list[EventOutcome] = field(default_factory=list)
    skipped: int = 0  # events with no ground truth or no directional outcome

    def summary_line(self) -> str:
        verdict = "BEATS baseline" if self.beats_baseline else "does NOT beat baseline"
        return (
            f"{self.n_events} events | sim {self.sim_accuracy:.0%} vs "
            f"baseline {self.baseline_accuracy:.0%} → {verdict} "
            f"({self.skipped} skipped)"
        )


def run_backtest(
    adapter: DomainAdapter,
    engine: SimulationEngine,
    events: list[BacktestEvent],
    n_agents: int = 100,
    n_rounds: int = 8,
) -> BacktestReport:
    """
    Run every event through the engine and score sim vs baseline vs truth.

    Events whose ground truth is unavailable, or whose actual outcome has no
    direction (a flat price move / unresolved PR), are skipped rather than
    scored as wrong — they carry no signal to predict.
    """
    outcomes: list[EventOutcome] = []
    skipped = 0

    for event in events:
        truth = adapter.get_ground_truth(event.seed)
        if truth is None:
            skipped += 1
            continue
        actual = adapter.truth_direction(truth)
        if actual == 0:
            skipped += 1
            continue

        agents = adapter.build_personas(n_agents)
        result = engine.run(event.seed, agents, n_rounds=n_rounds)

        sim_dir = sign(result.trajectory[-1]) if result.trajectory else 0
        baseline_dir = sign(adapter.naive_prediction(event.seed))

        outcomes.append(EventOutcome(
            event_id=event.event_id,
            sim_direction=sim_dir,
            baseline_direction=baseline_dir,
            actual_direction=actual,
            sim_correct=(sim_dir == actual),
            baseline_correct=(baseline_dir == actual),
        ))

    n = len(outcomes)
    sim_acc = sum(o.sim_correct for o in outcomes) / n if n else 0.0
    base_acc = sum(o.baseline_correct for o in outcomes) / n if n else 0.0
    return BacktestReport(
        n_events=n,
        sim_accuracy=sim_acc,
        baseline_accuracy=base_acc,
        beats_baseline=sim_acc > base_acc,
        outcomes=outcomes,
        skipped=skipped,
    )
