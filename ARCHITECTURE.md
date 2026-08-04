# Lightningfish — Architecture & Mechanics

Technical reference for the simulation engine: how a run works, how opinions
move, what every metric means, and how the system is validated and calibrated.
For setup and deployment see [README.md](README.md).

---

## 1. Overview

Lightningfish simulates how a population of heterogeneous agents forms (or fails
to form) consensus about an event — a market-moving headline, a GitHub PR — over
a series of rounds. Each agent holds an **opinion** in `[-1, +1]` (the poles are
domain-specific: bearish/bullish, block/approve).

The design goal is realistic social dynamics at low cost: only a small fraction
of agents call the LLM each round; the rest update through cheap deterministic
math. The engine is **domain-agnostic** — finance and coding are plugins behind a
`DomainAdapter` interface, and `lightningfish_core` contains no domain strings
(enforced by a test).

```
lightningfish_core/     Engine, models, tiers, metrics, backtest, calibration
lightningfish_finance/  7 investor archetypes + yfinance/Reddit data
lightningfish_coding/   6 reviewer archetypes + CIBot + GitHub data
lightningfish_service/  FastAPI service (local or Modal)
lightningfish_web/      Next.js streaming frontend
```

---

## 2. The simulation loop

`SimulationEngine.run_streaming()` ([engine.py](lightningfish_core/engine.py))
yields a `RoundEvent` per round and returns a `SimulationResult`. Each round:

1. **Snapshot the crowd.** `crowd_signal` = influence-weighted mean of all current
   opinions, taken *before* any updates so agents react to a consistent state.
2. **Route agents into three tiers** (`TierRouter`).
3. **Update each tier** (T1 and T2 call the LLM; T3 is pure math).
4. **Record** each agent's end-of-round opinion into its `opinion_history`.
5. **Update the settled tracker** and **compute metrics**.

### Tiers ([tier_router.py](lightningfish_core/tier_router.py))

| Tier | Who | Cap | How they update |
|------|-----|-----|-----------------|
| **T1 — originators** | highest `influence_weight` (> 0.65), not settled | ≤ 10% | LLM writes a structured post + opinion; blended in |
| **T2 — reactors** | uncertain (`\|opinion\| < 0.40`), not settled, not T1 | ≤ 20% | LLM re-evaluates after reading their feed; blended in |
| **T3 — drifters** | everyone else + rule-based agents | — | Deterministic herding math (no LLM) |

Rule-based agents (e.g. `CIBot`) are always T3 and compute their opinion directly
from the seed.

### T1/T2 opinion update — the blend ([resistance.py](lightningfish_core/resistance.py))

The LLM output is treated as a fresh *signal*, not the final opinion. It is
blended with the prior through the persona's behavioural parameters:

```
effective_resistance = override_fn(agent, crowd_signal) or agent.opinion_resistance
alpha  = recency_bias * (1 - effective_resistance)
opinion = (1 - alpha) * prior + alpha * llm_signal      # clamped to [-1, 1]
```

- High resistance → `alpha → 0` → opinion barely moves (strong anchoring).
- High recency_bias → `alpha → 1` → opinion snaps to the new signal.
- **`resistance_override_fn`** lets an archetype raise its own resistance under
  pressure. The `ShortSeller` rule multiplies resistance by 1.3 when the crowd
  signal opposes them and `|signal| > 0.6` — they *dig in* as the crowd turns,
  the mechanism behind a short squeeze.

### T3 herding update

```
cluster_mean = mean opinion of the agent's own archetype
target       = global_herd_weight * crowd_signal + (1 - global_herd_weight) * cluster_mean
effective_λ  = λ * (1 - contrarian_tendency)   if λ >= 0   else  λ
momentum     = opinion_history[-1] - opinion_history[-2]   (0 for first two rounds)
opinion      = (1 - |effective_λ|) * prior + effective_λ * target
                 + momentum_weight * momentum               # clamped to [-1, 1]
```

- **`target`** mixes the influence-weighted global crowd with the agent's own
  archetype cluster (default `global_herd_weight = 0.3`), so groups influence
  each other while in-group echo chambers still dominate.
- **Negative `herding_coefficient`** (λ) is left undamped by `contrarian_tendency`
  so diverging archetypes (ShortSeller, ValueInvestor) actively pull away from
  the target — this is what produces persistent bifurcation.
- **Momentum** (default weight 0.2) carries last round's move forward, giving
  trajectories path-dependence instead of resetting each round.

### Feeds — the follower graph ([social.py](lightningfish_core/social.py))

`build_follower_graph()` gives each agent a fixed set of followees: the top-N
highest-influence agents (whom everyone watches, so their posts propagate widely)
plus a few same-archetype peers (echo chambers). T1/T2 feeds are drawn only from
posts authored by an agent's followees — influence is **structural**, not random.

### Parse retries

Small models drop the structured post format often. A T1 post that fails to
parse is re-requested up to `_MAX_POST_RETRIES` (1) times before the fallback
(prior opinion) is accepted, so a genuine "held opinion" is distinguishable from
a swallowed format failure.

---

## 3. Metrics ([social.py](lightningfish_core/social.py) `SocialMetrics`)

Per round:

| Metric | Definition | Reading |
|--------|-----------|---------|
| **herding_index** | `1 − CSAD`, where CSAD = mean absolute deviation from the mean opinion | `[0, 1]`; 1 = full consensus, 0 = maximally split. CSAD_max = 1 for opinions in `[-1,1]`, so no arbitrary baseline. |
| **herding_delta** | change in herding_index vs previous round | negative = opinions **diverging** (bifurcation) |
| **cascade_detected** | round-over-round mean move exceeds `mean + 2σ` of the movement history (min 3 rounds, floor 0.03); fixed 0.15 threshold before enough history | a genuine regime shift, not noise |
| **cascade_trigger_archetype** | most common archetype among that round's posters | attribution, not causation |
| **argument_diversity_score** | unique taxonomy tags seen so far ÷ taxonomy size | `[0, 1]`; tags are validated against the domain taxonomy so it can't exceed 1 |
| **settled_fraction** | fraction of agents stable (`\|Δ\| < 0.03`) for ≥ 2 consecutive rounds | settled agents drop out of T1/T2; disruption un-settles them |
| **parse_success_rate** | fraction of the round's T1 posts that parsed cleanly | structured-output health |

On the whole run (`SimulationResult`):

- **mean_parse_success_rate** — average of the per-round parse rates.
- **low_confidence** — `True` when mean parse rate < `_MIN_PARSE_RATE` (0.8);
  the run is dominated by format-failure fallbacks and should not be trusted.

---

## 4. Validation — the backtest ([backtest.py](lightningfish_core/backtest.py))

Answers "does the simulation predict real outcomes better than trivial
alternatives?" For each historical event, `run_backtest()` compares three
directional calls against the actual outcome:

- **sim** — sign of the simulation's final mean opinion,
- **baselines** — a dict of `(BacktestEvent) -> int` predictors, and
- **majority class** — always predicting the more common outcome (a reference,
  not a per-event predictor).

Built-in baselines:

- **`naive`** — the domain's `naive_prediction()` (finance: headline-sentiment
  sign; coding: tests-included / CI heuristic).
- **`single_llm`** (`llm_baseline`) — one model call per event. This is the
  important bar: does the multi-agent machinery beat *just asking the model once*?

`BacktestReport` leads with `beats_baselines` and a **binomial significance test**
(`p_value_vs_best`): the one-sided probability of the sim's correct count under a
null that only matches the best reference accuracy. A low `p` means the edge is
unlikely to be chance. Events with no ground truth or a flat outcome are skipped,
not scored as wrong.

### Event sources

- **Coding** ([backtest_events.py](lightningfish_coding/backtest_events.py)) —
  `pull_pr_events()` fetches a **class-balanced** sample (half merged, half
  unmerged closed PRs) via the GitHub search API. Balancing matters: mature repos
  batch-close stale PRs, so naive "recent closed" sampling is nearly all
  rejections and a trivial always-block baseline would score ~100%. Works
  **tokenless** on public repos (60 req/hr) or with a `GITHUB_TOKEN` (5000/hr).
- **Finance** ([backtest_events.py](lightningfish_finance/backtest_events.py)) —
  `pull_ticker_events()` takes `(ticker, date, headline)` triples. Point-in-time
  headline text is **required**; events without it are skipped rather than
  backfilled with current headlines (which would leak hindsight — the price
  ground truth is historical but live headlines are not).

CLI: `python -m tests.integration.run_backtest {coding <owner> <repo> [limit] | finance}`

---

## 5. Calibration ([calibration.py](lightningfish_core/calibration.py))

`grid_search()` sweeps engine parameters against backtest accuracy instead of
leaving them hand-set. It builds an engine per parameter combination (via an
`engine_factory`), runs the full backtest, and picks the setting with the highest
sim accuracy, tie-broken by lowest p-value.

Currently swept: `global_herd_weight`, `momentum_weight` (exposed as
`SimulationEngine` attributes). Meaningful only on a real model and a
sufficiently large, balanced event set — small samples overfit.

CLI: `python -m tests.integration.run_calibration <owner> <repo> [limit]`

---

## 6. Personas

Archetypes are defined in each domain's `personas.py` with five behavioural
parameters (`opinion_resistance`, `recency_bias`, `contrarian_tendency`,
`influence_weight`, `herding_coefficient`) plus a population `proportion`. Each
built agent's parameters are **jittered** ±0.08 ([jitter.py](lightningfish_core/jitter.py))
so members of one archetype are not identical.

See the tables in [README.md](README.md) for the archetype roster. Note the
coding parameters are first-pass estimates, not literature-grounded — calibrate
before trusting them.

---

## 7. LLM providers ([llm_provider.py](lightningfish_core/llm_provider.py))

`make_provider(model, base_url)` returns:

- **`AnthropicProvider`** for `claude-*` models (real cost, tracked per call).
- **`LocalProvider`** for any `ollama:<model>` prefix or explicit `base_url` —
  an OpenAI-compatible client for Ollama / llama.cpp / vLLM, cost always `$0.00`.

Set `LIGHTNINGFISH_MODEL=ollama:llama3.2` to run entirely locally. Note small
(3B) models drop the structured format often (watch `parse_success_rate` /
`low_confidence`) and produce muted signal magnitudes — use ≥ 8B or a frontier
model for trustworthy results.

---

## 8. Extending to a new domain

Implement `DomainAdapter` ([adapter.py](lightningfish_core/adapter.py)):

- `enrich_seed`, `build_personas`, `argument_taxonomy`
- `agent_system_prompt` (T2 one-shot), `post_system_prompt` (T1 structured);
  `reactor_system_prompt` has a working default that appends the feed
- `get_ground_truth`, `score` — for backtesting
- `naive_prediction`, `truth_direction`, `baseline_llm_prompt` — for the backtest
  baselines (sensible defaults exist)

Register it so `registry.get("<id>")` resolves. Keep domain strings out of
`lightningfish_core` (a test enforces this).

---

## 9. Key constants

| Constant | Default | Where |
|----------|---------|-------|
| `MAX_T1_FRACTION` | 0.10 | tier_router |
| `MAX_T2_FRACTION` | 0.20 | tier_router |
| `T1_INFLUENCE_THRESHOLD` | 0.65 | tier_router |
| `T2_UNCERTAINTY_THRESHOLD` | 0.40 | tier_router |
| `global_herd_weight` | 0.30 | engine (tunable) |
| `momentum_weight` | 0.20 | engine (tunable) |
| `_MAX_POST_RETRIES` | 1 | engine |
| `_MIN_PARSE_RATE` | 0.80 | engine |
| SettledTracker threshold / patience | 0.03 / 2 | tier_router |
| jitter scale | ±0.08 | jitter |

---

## 10. Findings so far & how to read a run

### What has been validated

- **The mechanics do what they claim.** On a real GME short-squeeze scenario the
  ShortSeller camp diverged from a rising bullish crowd (opinions moved *opposite*
  to the majority) — the `resistance_override` firing, which was previously dead
  code. The herding index stayed in `[0, 1]` (no more `-115%` artifacts) and ADS
  stayed ≤ 1.
- **The measurement pipeline scores real data correctly.** A tokenless,
  class-balanced GitHub pull scored the naive baseline against actual PR merge
  outcomes end-to-end. This also surfaced a real sampling lesson: mature repos
  batch-close stale PRs, so samples **must** be class-balanced or a trivial
  always-block baseline looks perfect.
- **The parse retry helps.** Per-round parse rates rose from ~0.50 dips toward
  1.0; the residual failures on a 3B model are exactly what `low_confidence`
  exists to flag.
- **The metrics distinguish regimes.** The deterministic scenario tests produce
  separable fingerprints: herd (rising index, converging), shock (a cascade at
  the trigger round), and bifurcation (staying more split than the herd case).

### What has NOT been shown yet

**The core predictive claim is untested.** No run has yet measured whether the
multi-agent simulation beats a **single LLM call** (or the naive/majority
references) at predicting real outcomes on a statistically meaningful sample with
a capable model. The baselines, significance test, and calibration harness are
the apparatus to produce that number — the number itself is still pending. Until
it exists, treat Lightningfish as a **validated qualitative model, not a
validated predictor.**

Producing it requires a capable model (a ≥ 7B local model or a frontier API
model — 3B models drop the format and mute the signal) and, for a large enough
sample, a `GITHUB_TOKEN`:

```bash
GITHUB_TOKEN=... LIGHTNINGFISH_MODEL=ollama:qwen2.5:7b \
  python -m tests.integration.run_backtest coding pallets flask 24
```

### Preliminary run (NOT a verdict — n=6)

Two tokenless runs on `pallets/flask` with `qwen2.5:7b` (6 balanced PRs each):

- **Parse health was clean** (no low-confidence runs) — qwen 7B follows the
  format, so results are interpretable and the model is not the bottleneck.
- **The sim scored ~50% (chance), below the naive tests/CI baseline's 67%**, and
  did not beat the single-LLM baseline. One run collapsed to all-approve; the
  other varied but still scored 50%.
- `p ≈ 0.90` — with n=6 nothing is distinguishable from chance, so this is a
  smoke test, not evidence. A ~24+ event run is needed for any real conclusion.

Signal to chase if a larger run confirms it: the sim appears to drift toward
approval regardless of PR quality, suggesting an archetype approve-bias or
herding that flattens dissent rather than a modelling-capacity problem.

### How to read a run

1. **Confidence first.** If `low_confidence` is true (mean `parse_success_rate`
   < 0.8), stop — the result reflects format failures, not dynamics. Use a bigger
   model.
2. **Consensus.** `herding_index` near 1 = agreement; near 0 = split. A **falling**
   index (`herding_delta < 0`) means opinions are diverging (bifurcation), which
   won't show as a negative number any more.
3. **Shocks.** `cascade_detected` marks a round whose mean move is a statistical
   outlier; `cascade_trigger_archetype` is attribution, not proven causation.
4. **Backtest verdict.** Read `beats_baselines` (must clear *every* entry,
   including `single_llm`) together with `p_value_vs_best` — a high accuracy on
   few events with `p > 0.05` is not yet signal.

