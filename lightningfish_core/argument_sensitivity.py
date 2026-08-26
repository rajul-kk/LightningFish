"""
Argument sensitivity: for one already-run simulation, which argument mattered
most to the outcome? No ground truth needed, it's a before/after comparison
against the simulation's own baseline, not a real-world result. Run the seed
once normally, then once per taxonomy tag with that tag excluded
(engine.run(..., excluded_argument_tags={tag})), and rank tags by how far
their absence moves the final mean opinion.

Caveat, confirmed against real inference: the LLM is stochastic, so two runs
of identical prompts don't reproduce identical trajectories. A real run at
default temperature showed never-posted tags carrying deltas as large as
tags that actually appeared, noise bigger than the effect being measured.
Construct ``engine`` with a low ``temperature`` for this use (shrinks the
floor, doesn't eliminate it); a normal simulation should NOT do this, since
sampling variance is what makes personas diverge in the first place.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from .backtest import sign
from .models import AgentPersona, EnrichedSeed

# Reseeded before every arm so build_follower_graph's random.sample calls
# land identically across arms, otherwise a tag that never appeared would
# still show a nonzero delta from follower-graph sampling alone.
_DEFAULT_RNG_SEED = 0


@dataclass
class ArgumentSensitivityRow:
    tag: str
    tag_appeared: bool       # False if the baseline run never actually posted this tag
    baseline_mean: float
    excluded_mean: float
    delta: float             # excluded_mean - baseline_mean
    direction_flipped: bool  # sign(excluded_mean) != sign(baseline_mean)


@dataclass
class ArgumentSensitivityReport:
    baseline_mean: float
    baseline_direction: int
    rows: list[ArgumentSensitivityRow] = field(default_factory=list)


def argument_sensitivity_report(
    engine,
    seed: EnrichedSeed,
    agents: list[AgentPersona],
    n_rounds: int,
    taxonomy: list[str] | None = None,
    rng_seed: int = _DEFAULT_RNG_SEED,
) -> ArgumentSensitivityReport:
    """
    Run ``seed`` once per taxonomy tag with that tag excluded, plus once with
    nothing excluded as the baseline, and rank tags by |delta| against the
    baseline's final mean opinion.

    ``engine`` needs only ``.run(seed, agents, n_rounds,
    excluded_argument_tags=None) -> SimulationResult``, duck-typed so tests
    can substitute a stub.

    ``agents`` is deep-copied fresh for every run, including the baseline:
    engine.run mutates personas in place, and rebuilding via
    adapter.build_personas() per arm would add fresh jitter that confounds
    the comparison with population noise instead of isolating the exclusion.

    ``rng_seed`` reseeds Python's random module before every arm so
    follower-graph sampling matches across arms. It does not make a real LLM
    provider deterministic, see the module docstring's noise-floor caveat.
    """
    if taxonomy is None:
        taxonomy = []

    random.seed(rng_seed)
    baseline_result = engine.run(seed, copy.deepcopy(agents), n_rounds)
    baseline_mean = baseline_result.trajectory[-1] if baseline_result.trajectory else 0.0
    baseline_direction = sign(baseline_mean)

    rows: list[ArgumentSensitivityRow] = []
    for tag in taxonomy:
        random.seed(rng_seed)
        excluded_result = engine.run(
            seed, copy.deepcopy(agents), n_rounds, excluded_argument_tags={tag},
        )
        excluded_mean = excluded_result.trajectory[-1] if excluded_result.trajectory else 0.0
        rows.append(ArgumentSensitivityRow(
            tag=tag,
            tag_appeared=tag in baseline_result.argument_timeline,
            baseline_mean=baseline_mean,
            excluded_mean=excluded_mean,
            delta=excluded_mean - baseline_mean,
            direction_flipped=sign(excluded_mean) != baseline_direction,
        ))

    rows.sort(key=lambda r: abs(r.delta), reverse=True)
    return ArgumentSensitivityReport(
        baseline_mean=baseline_mean,
        baseline_direction=baseline_direction,
        rows=rows,
    )
