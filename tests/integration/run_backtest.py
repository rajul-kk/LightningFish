"""
Backtest CLI: does the simulation beat a naive baseline on real outcomes?

Coding (fully programmatic, objective):
    GITHUB_TOKEN=... python -m tests.integration.run_backtest coding <owner> <repo> [limit]

Finance (price ground truth is point-in-time; event text is not — see
lightningfish_finance.backtest_events caveat). Events come from a small built-in
list of (ticker, date, headline); edit or extend as needed:
    python -m tests.integration.run_backtest finance

Hacker News (fully programmatic, objective, free unauthenticated API):
    python -m tests.integration.run_backtest hn [limit]

Hacker News + early comments — the same stories re-seeded with their first
2h of community reaction, to test whether dynamic signal beats the measured
submission-only ceiling (METHODOLOGY.md). Requires a prior `hn` run:
    python -m tests.integration.run_backtest hn-early [limit]

Hacker News controversy — scores whether the crowd SPLITS (dispersion of the
final opinion distribution) rather than which way it leans. The only axis
where the simulation's output differs in kind from one raw model call:
    python -m tests.integration.run_backtest hn-controversy [limit]

Add "blind" to restrict to stories that drew no early discussion — the only
subgroup where the early-comment count baseline carries no information and
the simulation must read submission content to beat it:
    python -m tests.integration.run_backtest hn-early blind

Runs BOTH a points-direction (reception/virality) and a num_comments-direction
(engagement) backtest against the SAME simulated events — one simulation per
event, scored twice via score_precomputed(). See
specs/2026-08-09-hn-sentiment-domain-design.md.

Model is controlled via LIGHTNINGFISH_MODEL (default: claude-haiku-4-5-20251001;
use ollama:llama3.2 for a free local run, though small models weaken the sim).

Ground truth (and, for coding/hn, the pulled event list) is cached to
.cache/lightningfish/ so repeated runs against the same events don't re-spend
API rate limit. Set LIGHTNINGFISH_NO_CACHE=1 to force a fresh pull.
"""
from __future__ import annotations

import io
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from lightningfish_core.backtest import (
    BacktestReport,
    llm_baseline,
    run_backtest,
    score_precomputed,
    sign,
)
from lightningfish_core.engine import SimulationEngine
from lightningfish_core.event_cache import CachingAdapter, EventCache, cached_pull_events
from lightningfish_core.models import SimulationResult

_NO_CACHE = os.environ.get("LIGHTNINGFISH_NO_CACHE") == "1"


def _baselines(adapter, engine):
    return {
        "naive": lambda e: sign(adapter.naive_prediction(e.seed)),
        "single_llm": llm_baseline(adapter, engine),
    }


def _sim_size(default_agents: int, default_rounds: int) -> tuple[int, int]:
    """Agent/round counts, overridable via env for cheap local runs."""
    return (
        int(os.environ.get("LIGHTNINGFISH_N_AGENTS", default_agents)),
        int(os.environ.get("LIGHTNINGFISH_N_ROUNDS", default_rounds)),
    )

# A tiny seed list for the finance path. Point-in-time headline text is supplied
# so the naive baseline is not leaking current news. Extend freely.
_FINANCE_EVENTS = [
    ("SMCI", "2024-10-31", "Accounting scandal: auditor resigns, delisting notice, shares crash"),
    ("NVDA", "2024-05-23", "Beats estimates with record data-center revenue, shares surge"),
    ("SIVB", "2023-03-09", "Bank announces large loss and emergency equity raise amid deposit outflows"),
    ("META", "2022-02-02", "Misses on earnings, user growth stalls, shares plunge"),
    ("AAPL", "2024-11-01", "Beats estimates on strong iPhone and services growth"),
]


def _print_report(label: str, report: BacktestReport) -> None:
    print(f"\n=== {label} ===")
    print(report.summary_line())
    base_names = list(report.baseline_accuracy)
    header = "  " + f"{'event':<28} {'sim':>4} " + " ".join(f"{n[:8]:>8}" for n in base_names)
    print(header + f" {'actual':>6}  result")
    for o in report.outcomes:
        mark = "ok " if o.sim_correct else "MISS"
        bases = " ".join(f"{o.baseline_directions[n]:>+8}" for n in base_names)
        print(f"  {o.event_id:<28} {o.sim_direction:>+4} {bases} "
              f"{o.actual_direction:>+6}  {mark}")


def _run_coding(args: list[str]) -> None:
    from lightningfish_coding.backtest_events import pull_pr_events
    from lightningfish_coding.config import CodingDomainAdapter

    if len(args) < 2:
        print("Usage: run_backtest coding <owner> <repo> [limit]")
        sys.exit(1)
    owner, repo = args[0], args[1]
    limit = int(args[2]) if len(args) > 2 else 20
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Note: GITHUB_TOKEN not set — using unauthenticated GitHub API "
              "(60 req/hr; keep limit small, ~8 PRs).")

    adapter = CodingDomainAdapter()
    list_key = f"coding:{owner}/{repo}:{limit}"

    if _NO_CACHE:
        print(f"Pulling up to {limit} closed PRs from {owner}/{repo}... (cache disabled)")
        events = pull_pr_events(owner, repo, token, limit=limit)
    else:
        cache = EventCache(f"{owner}_{repo}")
        adapter = CachingAdapter(adapter, cache)
        events = cached_pull_events(
            cache, list_key, lambda: pull_pr_events(owner, repo, token, limit=limit)
        )
        print(f"Pulling up to {limit} closed PRs from {owner}/{repo}... "
              f"(cache: {len(cache)} entries on disk)")
    print(f"  got {len(events)} events")

    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    engine = SimulationEngine(adapter, model=model)
    n_agents, n_rounds = _sim_size(60, 6)
    report = run_backtest(adapter, engine, events, n_agents=n_agents,
                          n_rounds=n_rounds, baselines=_baselines(adapter, engine))
    _print_report(f"coding {owner}/{repo}", report)


def _run_finance() -> None:
    from lightningfish_finance.backtest_events import pull_ticker_events
    from lightningfish_finance.config import FinanceDomainAdapter

    if not (os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET")):
        print("Warning: REDDIT_CLIENT_ID/SECRET not set — ground truth fetch will fail.")

    print(f"Building {len(_FINANCE_EVENTS)} finance events...")
    events = pull_ticker_events(_FINANCE_EVENTS)
    print(f"  got {len(events)} events")

    adapter = FinanceDomainAdapter()
    if not _NO_CACHE:
        adapter = CachingAdapter(adapter, EventCache("finance_events"))  # type: ignore[assignment]
    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    engine = SimulationEngine(adapter, model=model)
    n_agents, n_rounds = _sim_size(100, 8)
    report = run_backtest(adapter, engine, events, n_agents=n_agents,
                          n_rounds=n_rounds, baselines=_baselines(adapter, engine))
    _print_report("finance", report)


def _run_hn(args: list[str]) -> None:
    from lightningfish_hn.backtest_events import pull_hn_events
    from lightningfish_hn.config import HNCommentsAdapter, HNDomainAdapter

    limit = int(args[0]) if args else 20
    points_adapter = HNDomainAdapter()
    comments_adapter = HNCommentsAdapter()
    list_key = f"hn:points:{limit}"

    if _NO_CACHE:
        print(f"Pulling up to {limit} class-balanced HN stories (by points)... (cache disabled)")
        events = pull_hn_events(metric="points", limit=limit)
    else:
        cache = EventCache("hn_stories")
        points_adapter = CachingAdapter(points_adapter, cache)  # type: ignore[assignment]
        comments_adapter = CachingAdapter(comments_adapter, cache)  # type: ignore[assignment]
        events = cached_pull_events(
            cache, list_key, lambda: pull_hn_events(metric="points", limit=limit)
        )
        print(f"Pulling up to {limit} class-balanced HN stories (by points)... "
              f"(cache: {len(cache)} entries on disk)")
    print(f"  got {len(events)} events")

    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    engine = SimulationEngine(points_adapter, model=model)
    n_agents, n_rounds = _sim_size(60, 6)

    # Simulate each event once (the expensive step) — score it twice (cheap),
    # once per ground-truth axis. See "Backtest integration" in
    # specs/2026-08-09-hn-sentiment-domain-design.md. Note: the single_llm
    # baseline is still called once per adapter (twice total) since it isn't
    # part of the expensive simulation loop — an accepted, minor v1 cost.
    pairs = []
    for event in events:
        agents = points_adapter.build_personas(n_agents)
        result = engine.run(event.seed, agents, n_rounds=n_rounds)
        pairs.append((event, result))

    points_report = score_precomputed(points_adapter, pairs, baselines=_baselines(points_adapter, engine))
    comments_report = score_precomputed(comments_adapter, pairs, baselines=_baselines(comments_adapter, engine))

    _print_report("hn (points / reception)", points_report)
    _print_report("hn (num_comments / engagement)", comments_report)


def _run_hn_early(args: list[str]) -> None:
    """
    The early-comments experiment: same stories as a prior `hn` run, but each
    seed also carries the story's first-N-hours of community reaction.

    Deliberately PAIRED — story ids are read from the submission-only cache
    rather than pulled fresh, so any accuracy difference is attributable to the
    added reaction section and not to a different sample of stories.

    The baseline ladder gains a rung: "naive_early" predicts purely from the
    early comment COUNT. The simulation only earns a result here by beating
    that, which is what would show it is reading the comment TEXT rather than
    just noticing that comments exist.
    """
    from lightningfish_core.backtest import BacktestEvent
    from lightningfish_hn.config import HNCommentsAdapter, HNDomainAdapter
    from lightningfish_hn.early_comments import (
        DEFAULT_EARLY_WINDOW_SECONDS,
        EARLY_COMMENT_THRESHOLD,
        assert_window_is_early,
        early_engagement_prediction,
        enrich_hn_seed_with_early_comments,
    )

    window = int(os.environ.get("LIGHTNINGFISH_HN_EARLY_WINDOW", DEFAULT_EARLY_WINDOW_SECONDS))
    assert_window_is_early(window)

    base_cache = EventCache("hn_stories")
    story_ids = [
        int(eid.split(":")[1]) for eid in base_cache.event_ids()
        if not eid.startswith("__list__:") and ":" in eid
    ]
    if not story_ids:
        print("No submission-only HN cache found. Run "
              "'python -m tests.integration.run_backtest hn 40' first — this "
              "experiment reuses those exact stories so the comparison is paired.")
        sys.exit(1)

    # "blind" restricts to stories that drew NO early discussion. The
    # early-comment count baseline is saturated where comments exist (every
    # such story in the sample went viral) and blind here, guessing "flop" for
    # all of them — so this subgroup is the only place the simulation can show
    # it reads submission content rather than counting reactions.
    blind_only = "blind" in args
    limits = [a for a in args if a.isdigit()]
    if limits:
        story_ids = story_ids[: int(limits[0])]

    def _pull() -> list[BacktestEvent]:
        built = []
        for i, sid in enumerate(story_ids, 1):
            try:
                seed = enrich_hn_seed_with_early_comments(sid, window)
            except Exception as exc:
                print(f"  [{i}/{len(story_ids)}] skip {sid}: {exc}")
                continue
            built.append(BacktestEvent(event_id=f"hn:{sid}", seed=seed))
            print(f"  [{i}/{len(story_ids)}] {sid}: "
                  f"{seed.metadata['early_comment_count']} early comments")
        return built

    early_cache = EventCache("hn_stories_early")
    points_adapter = CachingAdapter(HNDomainAdapter(), early_cache)
    comments_adapter = CachingAdapter(HNCommentsAdapter(), early_cache)
    events = cached_pull_events(early_cache, f"hn:early:{window}:{len(story_ids)}", _pull)

    # Reuse the base run's measurements. HN points keep accruing and Algolia
    # only serves current totals, so re-fetching here would re-measure and make
    # this "paired" run unpaired against the submission-only one.
    reused = early_cache.copy_ground_truth_from(base_cache)
    if reused:
        print(f"  reused {reused} ground-truth measurements from the base run "
              f"(avoids re-measuring drifting outcomes)")

    counts = [e.seed.metadata.get("early_comment_count", 0) for e in events]
    with_comments = sum(1 for c in counts if c > 0)
    above_thresh = sum(1 for c in counts if c >= EARLY_COMMENT_THRESHOLD)
    print(f"  {len(events)} events ({with_comments} with >=1 early comment, "
          f"{above_thresh} with >={EARLY_COMMENT_THRESHOLD}, max={max(counts) if counts else 0}, "
          f"window={window}s)")

    # A uniform enrichment makes naive_early a constant, which silently turns
    # this whole experiment into a no-op that still prints a plausible-looking
    # accuracy table. Observed on a run where every event came back with zero
    # early comments. Refuse rather than report a meaningless baseline.
    if above_thresh == 0 or above_thresh == len(events):
        print(
            f"\n  ABORT: early-comment enrichment is degenerate — "
            f"{above_thresh}/{len(events)} events are above the threshold, so "
            f"naive_early predicts one class for everything and the comparison "
            f"is meaningless.\n"
            f"  Either the comment fetch is failing (check network/API shape) or "
            f"this sample genuinely has no early discussion. Inspect with:\n"
            f"    EventCache('hn_stories_early') -> seed.metadata['early_comment_count']"
        )
        sys.exit(1)
    if blind_only:
        events = [e for e in events if e.seed.metadata.get("early_comment_count", 0) == 0]
        print(f"  --blind: restricted to {len(events)} zero-early-comment events")

    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    engine = SimulationEngine(points_adapter, model=model)
    n_agents, n_rounds = _sim_size(60, 6)

    def _ladder(adapter):
        return {
            "naive": lambda e: sign(adapter.naive_prediction(e.seed)),
            "naive_early": lambda e: sign(early_engagement_prediction(e.seed)),
            "single_llm": llm_baseline(adapter, engine),
        }

    pairs = []
    for i, event in enumerate(events, 1):
        agents = points_adapter.build_personas(n_agents)
        result = engine.run(event.seed, agents, n_rounds=n_rounds)
        pairs.append((event, result))
        print(f"  simulated {i}/{len(events)}", flush=True)

    _print_report("hn+early (points / reception)",
                  score_precomputed(points_adapter, pairs, baselines=_ladder(points_adapter)))
    _print_report("hn+early (num_comments / engagement) — SELF-PREDICTING, see caveat",
                  score_precomputed(comments_adapter, pairs, baselines=_ladder(comments_adapter)))
    print("\nNote: early comment count is a strict prefix of the 24h num_comments "
          "target, so the engagement axis above partially predicts itself. The "
          "points axis is the honest one.")


def _run_hn_controversy(args: list[str]) -> None:
    """
    Scores whether the crowd SPLITS rather than which way it leans.

    Every other run here reduces a simulation to sign(final mean) — one bit,
    and the same bit one raw LLM call produces, which is why the multi-agent
    machinery has never had a structural edge to show. Dispersion is the thing
    only a population can express, so this is the first backtest where rung 2
    is a fair fight.

    Simulations are cached (trajectory + final distribution) so re-scoring
    against a different question later costs nothing.
    """
    from lightningfish_core.backtest import BacktestEvent
    from lightningfish_hn.backtest_events import pull_hn_events
    from lightningfish_hn.config import HNControversyAdapter

    limit = int(args[0]) if args else 40
    cache = EventCache("hn_stories")
    adapter = CachingAdapter(HNControversyAdapter(), cache)
    events = cached_pull_events(
        cache, f"hn:points:{limit}", lambda: pull_hn_events("points", limit)
    )

    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    engine = SimulationEngine(adapter, model=model)
    n_agents, n_rounds = _sim_size(60, 6)
    run_key = f"{model}:{n_agents}x{n_rounds}"

    # Only simulate events whose outcome is actually scoreable on this axis:
    # the comments/points ratio is meaningless for stories nobody saw, and
    # simulating them would burn most of the run on events that get skipped.
    scoreable = []
    for ev in events:
        truth = adapter.get_ground_truth(ev.seed)
        if truth is not None and adapter.truth_direction(truth) != 0:
            scoreable.append(ev)
    # flush: the UTF-8 stdout wrapper is block-buffered, so without this a long
    # first simulation shows an empty log and looks indistinguishable from a hang.
    print(f"  {len(scoreable)} of {len(events)} events have a controversy direction "
          f"(rest are mid-ratio or below the points floor)", flush=True)
    if not scoreable:
        print("  nothing to score — pull more stories with a larger limit")
        sys.exit(1)

    pairs = []
    for i, ev in enumerate(scoreable, 1):
        cached_run = cache.get_run(ev.event_id, run_key)
        if cached_run:
            result = SimulationResult(
                seed=ev.seed, trajectory=cached_run["trajectory"],
                round_events=[], final_distribution=cached_run["final_distribution"],
                total_tier1_calls=0, total_cost_usd=0.0,
                mean_parse_success_rate=cached_run["mean_parse_success_rate"],
                low_confidence=cached_run["low_confidence"],
            )
            print(f"  [{i}/{len(scoreable)}] {ev.event_id} (cached)", flush=True)
        else:
            agents = adapter.build_personas(n_agents)
            result = engine.run(ev.seed, agents, n_rounds=n_rounds)
            cache.put_run(ev.event_id, run_key, result)
            cache.save()
            print(f"  [{i}/{len(scoreable)}] {ev.event_id} simulated", flush=True)
        pairs.append((ev, result))

    report = score_precomputed(adapter, pairs, baselines=_baselines(adapter, engine))
    _print_report("hn (controversy / does the crowd split)", report)

    # A one-class predictor can still post a plausible-looking accuracy on
    # imbalanced classes — observed here when CachingAdapter silently failed
    # to delegate sim_direction and every event scored on the mean axis
    # instead of dispersion. That bug is fixed, but a constant predictor can
    # also mean the threshold is simply miscalibrated for this population/
    # model, so check every time rather than trusting the accuracy number.
    sim_dirs = [o.sim_direction for o in report.outcomes]
    if sim_dirs and len(set(sim_dirs)) == 1:
        spreads = [
            (sum((x - sum(d) / len(d)) ** 2 for x in d) / len(d)) ** 0.5
            for _, r in pairs if len((d := r.final_distribution)) >= 2
        ]
        print(
            f"\n  WARNING: the simulation predicted the SAME class for all "
            f"{len(sim_dirs)} events — its dispersion carries no information "
            f"in this run and the accuracy above is not a result.\n"
            f"  observed stddev range: "
            f"{min(spreads):.3f}-{max(spreads):.3f}" if spreads else ""
        )


def _run_hn_controversy_calibrated(args: list[str]) -> None:
    """
    Same question as hn-controversy — does the crowd split — but derives the
    stddev threshold from a held-out calibration batch instead of trusting
    the module's uncalibrated 0.35 guess, which fired on zero of 107 real
    events (METHODOLOGY.md rule 3/6: don't tune a threshold on the data it's
    scored against — including your own prior guess, once you've seen it fail).

    Pulled events are split deterministically by a hash of their event id into
    ~40% calibration / ~60% evaluation. Only the calibration half's simulated
    stddevs inform the threshold (its median); only the evaluation half's
    accuracy is reported as a result.
    """
    import hashlib

    from lightningfish_core.backtest import BacktestEvent
    from lightningfish_hn.backtest_events import pull_hn_events
    from lightningfish_hn.config import HNControversyAdapter

    limit = int(args[0]) if args else 300
    cache = EventCache("hn_stories")
    # Threshold doesn't affect get_ground_truth/truth_direction/naive_prediction,
    # so a plain adapter is fine for the filtering and simulation pass below —
    # the calibrated threshold is only plugged in for the final scoring.
    filter_adapter = CachingAdapter(HNControversyAdapter(), cache)
    events = cached_pull_events(
        cache, f"hn:points:{limit}", lambda: pull_hn_events("points", limit)
    )

    scoreable = []
    for ev in events:
        truth = filter_adapter.get_ground_truth(ev.seed)
        if truth is not None and filter_adapter.truth_direction(truth) != 0:
            scoreable.append(ev)
    print(f"  {len(scoreable)} of {len(events)} events have a controversy direction",
          flush=True)

    def _bucket(event_id: str) -> str:
        h = int(hashlib.sha256(event_id.encode()).hexdigest(), 16)
        return "calib" if h % 5 < 2 else "eval"  # ~40/60, deterministic

    calib = [e for e in scoreable if _bucket(e.event_id) == "calib"]
    evalset = [e for e in scoreable if _bucket(e.event_id) == "eval"]
    print(f"  split: {len(calib)} calibration / {len(evalset)} evaluation", flush=True)
    if len(calib) < 15 or len(evalset) < 15:
        print("  ABORT: too few events in one split to calibrate or evaluate "
              "meaningfully — pull more stories with a larger limit")
        sys.exit(1)

    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    engine = SimulationEngine(filter_adapter, model=model)
    n_agents, n_rounds = _sim_size(60, 6)
    run_key = f"{model}:{n_agents}x{n_rounds}"

    def _simulate(events_: list, label: str) -> list:
        pairs_ = []
        for i, ev in enumerate(events_, 1):
            cached_run = cache.get_run(ev.event_id, run_key)
            if cached_run:
                result = SimulationResult(
                    seed=ev.seed, trajectory=cached_run["trajectory"], round_events=[],
                    final_distribution=cached_run["final_distribution"],
                    total_tier1_calls=0, total_cost_usd=0.0,
                    mean_parse_success_rate=cached_run["mean_parse_success_rate"],
                    low_confidence=cached_run["low_confidence"],
                )
            else:
                agents = filter_adapter.build_personas(n_agents)
                result = engine.run(ev.seed, agents, n_rounds=n_rounds)
                cache.put_run(ev.event_id, run_key, result)
                cache.save()
            print(f"  [{label} {i}/{len(events_)}] {ev.event_id}", flush=True)
            pairs_.append((ev, result))
        return pairs_

    print("\n--- calibration pass ---", flush=True)
    calib_pairs = _simulate(calib, "calib")
    calib_stddevs = sorted(
        s for _, r in calib_pairs if (s := HNControversyAdapter.stddev_of(r)) is not None
    )
    if not calib_stddevs:
        print("  ABORT: no calibration simulation produced a usable distribution")
        sys.exit(1)
    threshold = calib_stddevs[len(calib_stddevs) // 2]  # median
    print(f"  calibration stddev range: {calib_stddevs[0]:.3f}-{calib_stddevs[-1]:.3f}, "
          f"median (threshold) = {threshold:.3f}", flush=True)

    print("\n--- evaluation pass ---", flush=True)
    eval_pairs = _simulate(evalset, "eval")

    eval_adapter = CachingAdapter(HNControversyAdapter(stddev_threshold=threshold), cache)
    report = score_precomputed(eval_adapter, eval_pairs, baselines=_baselines(eval_adapter, engine))
    _print_report(f"hn controversy, calibrated threshold={threshold:.3f} (held-out eval)", report)

    sim_dirs = [o.sim_direction for o in report.outcomes]
    if sim_dirs and len(set(sim_dirs)) == 1:
        print(
            f"\n  WARNING: even after calibration the predictor is constant on the "
            f"eval set ({len(sim_dirs)} events) — the calibration and evaluation "
            f"halves have different stddev distributions, or n is too small for "
            f"the median split to generalise. Not a valid result."
        )


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in (
        "coding", "finance", "hn", "hn-early", "hn-controversy", "hn-controversy-calibrated"
    ):
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] == "coding":
        _run_coding(sys.argv[2:])
    elif sys.argv[1] == "finance":
        _run_finance()
    elif sys.argv[1] == "hn-early":
        _run_hn_early(sys.argv[2:])
    elif sys.argv[1] == "hn-controversy":
        _run_hn_controversy(sys.argv[2:])
    elif sys.argv[1] == "hn-controversy-calibrated":
        _run_hn_controversy_calibrated(sys.argv[2:])
    else:
        _run_hn(sys.argv[2:])


if __name__ == "__main__":
    main()
