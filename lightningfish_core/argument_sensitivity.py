"""
Argument sensitivity: for one already-built simulation, which single argument
mattered most to the outcome?

Unlike a backtest, this needs no ground truth — it's a before/after comparison
against the simulation's own baseline run, not against a real-world result.
Run the seed once normally, then once per taxonomy tag with that tag excluded
from circulation (engine.run(..., excluded_argument_tags={tag})), and rank
tags by how far removing them moved the final mean opinion.

Caveat: with a real LLM provider, re-running the same seed and agents is not
guaranteed to reproduce byte-identical trajectories even with nothing excluded
— the model itself is stochastic. A tag whose removal moves the outcome by
about as much as this run-to-run noise floor isn't demonstrated to matter;
only a delta clearly outside that floor is. This module doesn't estimate that
floor itself (that would need repeated baseline runs, which costs as much as
the whole sensitivity sweep again) — treat small deltas skeptically.

Confirmed in practice, not just in theory: a real run against local Ollama
inference at default temperature showed tags that were never even posted in
the baseline still carrying deltas as large as or larger than tags that
actually appeared — the noise floor was bigger than the effect being
measured. The caller should construct ``engine`` with a low ``temperature``
(SimulationEngine's own knob, not something this module sets) specifically
for this use — a normal simulation run should NOT do this, since sampling
variance is what makes personas diverge from each other in the first place.
Low temperature shrinks the floor; it does not eliminate it.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from .backtest import sign
from .models import AgentPersona, EnrichedSeed

# Reseeded before every arm (baseline and each excluded-tag run) so
# build_follower_graph's random.sample calls land identically across arms.
# Without this, two runs that exclude nothing different still diverge by a
# small amount from follower-graph sampling alone, which would read as a
# nonzero delta for a tag that never even appeared in the baseline.
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

    ``engine`` is anything exposing ``.run(seed, agents, n_rounds,
    excluded_argument_tags=None) -> SimulationResult`` — normally a
    SimulationEngine, but duck-typed so tests can substitute a stub.

    ``agents`` is used, via a fresh deep copy, for every run including the
    baseline — engine.run mutates personas in place, and reusing
    adapter.build_personas() per arm would introduce fresh jitter/random
    initial opinions that confound the comparison with population noise
    rather than isolating the effect of the exclusion.

    ``rng_seed`` reseeds Python's random module before every arm, so
    follower-graph sampling (the one other source of run-to-run randomness
    inside engine.run) is identical across the baseline and every excluded
    arm. It does NOT make a real LLM provider's output deterministic — see
    the module docstring's noise-floor caveat.
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
