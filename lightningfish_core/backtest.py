"""
Backtest harness: does the simulation predict real outcomes better than trivial
baselines?

For each historical event we compare the simulation's final direction and one or
more baselines against the actual outcome. The report leads with whether the sim
beats each baseline (raw accuracy can look good by luck) and, once a significance
test is added, whether that edge is distinguishable from chance.

Baselines are ``(BacktestEvent) -> int`` callables returning a direction in
{-1, 0, 1}. The default "naive" baseline uses the domain's naive_prediction; the
CLI can add a "single_llm" baseline (one model call per event) to test whether
the multi-agent machinery beats simply asking the model once.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from scipy.stats import binomtest

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
    baseline_directions: dict[str, int]
    actual_direction: int
    sim_correct: bool


@dataclass
class BacktestReport:
    n_events: int
    sim_accuracy: float
    baseline_accuracy: dict[str, float]
    majority_class_accuracy: float
    beats_baselines: dict[str, bool]
    # One-sided binomial p: probability of the sim's correct count under a null
    # that only matches the best reference. Low p = the edge is unlikely chance.
    p_value_vs_best: float = 1.0
    # Structured-output health across the scored runs. A backtest dominated by
    # parse failures is uninterpretable regardless of accuracy.
    mean_parse_success_rate: float = 1.0
    low_confidence_events: int = 0
    outcomes: list[EventOutcome] = field(default_factory=list)
    skipped: int = 0  # events with no ground truth or no directional outcome

    def best_reference_accuracy(self) -> float:
        """Highest bar the sim must clear: best baseline or the majority class."""
        return max([self.majority_class_accuracy, *self.baseline_accuracy.values()])

    def summary_line(self) -> str:
        bl = ", ".join(f"{k} {v:.0%}" for k, v in self.baseline_accuracy.items())
        beats = all(self.beats_baselines.values()) and self.sim_accuracy > self.majority_class_accuracy
        verdict = "BEATS all references" if beats else "does NOT beat all references"
        conf = ""
        if self.low_confidence_events:
            conf = (f" | ⚠ {self.low_confidence_events}/{self.n_events} runs low-confidence "
                    f"(parse {self.mean_parse_success_rate:.0%})")
        return (
            f"{self.n_events} events | sim {self.sim_accuracy:.0%} | "
            f"majority {self.majority_class_accuracy:.0%} | {bl} → {verdict} "
            f"(p={self.p_value_vs_best:.3f}, {self.skipped} skipped){conf}"
        )


def _naive_baseline(adapter: DomainAdapter) -> Callable[[BacktestEvent], int]:
    return lambda event: sign(adapter.naive_prediction(event.seed))


def llm_baseline(adapter: DomainAdapter, engine: SimulationEngine) -> Callable[[BacktestEvent], int]:
    """One model call per event — the bar the multi-agent sim must clear to
    justify running many agents over many rounds."""
    def predict(event: BacktestEvent) -> int:
        opinion, _ = engine.provider.get_opinion(
            adapter.baseline_llm_prompt(event.seed),
            "Output ONLY the number.",
            engine.model,
        )
        return sign(opinion)
    return predict


def run_backtest(
    adapter: DomainAdapter,
    engine: SimulationEngine,
    events: list[BacktestEvent],
    n_agents: int = 100,
    n_rounds: int = 8,
    baselines: dict[str, Callable[[BacktestEvent], int]] | None = None,
) -> BacktestReport:
    """
    Run every event through the engine and score sim vs baselines vs truth.

    Events whose ground truth is unavailable, or whose actual outcome has no
    direction (a flat price move / unresolved PR), are skipped rather than
    scored as wrong — they carry no signal to predict.
    """
    if baselines is None:
        baselines = {"naive": _naive_baseline(adapter)}

    outcomes: list[EventOutcome] = []
    skipped = 0
    parse_rates: list[float] = []
    low_conf_events = 0

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
        parse_rates.append(result.mean_parse_success_rate)
        if result.low_confidence:
            low_conf_events += 1

        baseline_dirs = {name: fn(event) for name, fn in baselines.items()}
        outcomes.append(EventOutcome(
            event_id=event.event_id,
            sim_direction=sim_dir,
            baseline_directions=baseline_dirs,
            actual_direction=actual,
            sim_correct=(sim_dir == actual),
        ))

    n = len(outcomes)
    sim_acc = sum(o.sim_correct for o in outcomes) / n if n else 0.0
    baseline_acc = {
        name: (sum(o.baseline_directions[name] == o.actual_direction for o in outcomes) / n
               if n else 0.0)
        for name in baselines
    }
    # Majority-class reference: accuracy of always predicting the more common
    # actual outcome. A sim that cannot beat this has learned nothing.
    if n:
        counts = Counter(o.actual_direction for o in outcomes)
        majority_acc = max(counts.values()) / n
    else:
        majority_acc = 0.0

    # Is the sim's edge over the best reference distinguishable from chance?
    best_ref = max([majority_acc, *baseline_acc.values()]) if baseline_acc else majority_acc
    sim_correct_count = sum(o.sim_correct for o in outcomes)
    if n and 0.0 < best_ref < 1.0:
        p_value = binomtest(sim_correct_count, n, p=best_ref, alternative="greater").pvalue
    else:
        p_value = 1.0

    return BacktestReport(
        n_events=n,
        sim_accuracy=sim_acc,
        baseline_accuracy=baseline_acc,
        majority_class_accuracy=majority_acc,
        beats_baselines={name: sim_acc > acc for name, acc in baseline_acc.items()},
        p_value_vs_best=float(p_value),
        mean_parse_success_rate=(sum(parse_rates) / len(parse_rates) if parse_rates else 1.0),
        low_confidence_events=low_conf_events,
        outcomes=outcomes,
        skipped=skipped,
    )
