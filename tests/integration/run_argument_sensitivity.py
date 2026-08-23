"""
Argument sensitivity for cached real events — which single argument, if it had
never been raised, would have moved a simulation's outcome the most?

For each cached event, runs the simulation once normally and once per taxonomy
tag with that tag excluded from circulation, then ranks tags by how far their
absence moves the final mean opinion. Needs no ground truth: it's a
before/after comparison against the simulation's own baseline, not a backtest.

Fully offline: reads seeds already fetched by a prior run_backtest CLI run
from the local event cache — no network calls.

    python -m tests.integration.run_argument_sensitivity coding <owner> <repo>
    python -m tests.integration.run_argument_sensitivity hn

Model via LIGHTNINGFISH_MODEL (default ollama:qwen2.5:7b). Errors if the
relevant cache doesn't exist yet — run run_backtest for that domain first.
Limits to the first LIGHTNINGFISH_SENSITIVITY_LIMIT cached events (default 5)
since this costs len(taxonomy)+1 simulations per event.
"""
from __future__ import annotations

import io
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from lightningfish_core.argument_sensitivity import argument_sensitivity_report
from lightningfish_core.engine import SimulationEngine
from lightningfish_core.event_cache import EventCache


def _real_event_ids(cache: EventCache) -> list[str]:
    return [eid for eid in cache.event_ids() if not eid.startswith("__list__:")]


def _resolve(args: list[str]):
    """Returns (adapter, cache, ground-truth-run-command-hint)."""
    if not args or args[0] not in ("coding", "hn"):
        print(__doc__)
        sys.exit(0)
    if args[0] == "coding":
        if len(args) < 3:
            print("Usage: run_argument_sensitivity coding <owner> <repo>")
            sys.exit(1)
        owner, repo = args[1], args[2]
        from lightningfish_coding.config import CodingDomainAdapter
        return (CodingDomainAdapter(), EventCache(f"{owner}_{repo}"),
                f"run_backtest coding {owner} {repo}")
    from lightningfish_hn.config import HNDomainAdapter
    return HNDomainAdapter(), EventCache("hn_stories"), "run_backtest hn"


def main() -> None:
    domain = sys.argv[1] if len(sys.argv) > 1 else ""
    adapter, cache, hint = _resolve(sys.argv[1:])
    model = os.environ.get("LIGHTNINGFISH_MODEL", "ollama:qwen2.5:7b")
    n_agents = int(os.environ.get("LIGHTNINGFISH_N_AGENTS", 24))
    n_rounds = int(os.environ.get("LIGHTNINGFISH_N_ROUNDS", 4))
    limit = int(os.environ.get("LIGHTNINGFISH_SENSITIVITY_LIMIT", 5))
    # Low, not zero (some providers reject 0.0 or treat it specially) — this
    # comparison only means something if the baseline and every excluded arm
    # are as close to identical as sampling allows. A normal simulation run
    # should NOT use this; it's what makes personas diverge in the first place.
    temperature = float(os.environ.get("LIGHTNINGFISH_SENSITIVITY_TEMPERATURE", 0.1))

    event_ids = _real_event_ids(cache)[:limit]
    if not event_ids:
        print(f"No cached events. Run 'python -m tests.integration.{hint}' first.")
        sys.exit(1)

    taxonomy = adapter.argument_taxonomy()
    engine = SimulationEngine(adapter, model=model, temperature=temperature)
    neg, pos = adapter.opinion_labels
    print(f"domain={domain}  model={model}  agents={n_agents}  rounds={n_rounds}  "
          f"temperature={temperature}\n"
          f"taxonomy={taxonomy}\n"
          f"events={len(event_ids)} (of {len(_real_event_ids(cache))} cached, limited by "
          f"LIGHTNINGFISH_SENSITIVITY_LIMIT)  "
          f"cost: {len(event_ids)} x {len(taxonomy) + 1} simulations\n")

    for event_id in event_ids:
        seed = cache.get_seed(event_id)
        agents = adapter.build_personas(n_agents)
        report = argument_sensitivity_report(engine, seed, agents, n_rounds, taxonomy)

        baseline_label = pos if report.baseline_direction > 0 else neg
        print(f"[{event_id}] baseline={report.baseline_mean:+.3f} ({baseline_label})")
        for row in report.rows:
            flag = "  <-- flips the call" if row.direction_flipped else ""
            appeared = "" if row.tag_appeared else "  (never posted this run)"
            print(f"    {row.tag:<20} without it: {row.excluded_mean:+.3f}  "
                  f"delta={row.delta:+.3f}{flag}{appeared}")
        print()


if __name__ == "__main__":
    main()
