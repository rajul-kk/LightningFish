# Lightningfish — Architecture & Mechanics

Technical reference for the simulation engine: how a run works, how opinions
move, what every metric means, and how the system is validated and calibrated.
For setup and deployment see [README.md](README.md).

---

## 1. Overview

Lightningfish simulates how a population of heterogeneous agents forms (or fails
to form) consensus about an event — a market-moving headline, a GitHub PR — over
a series of rounds. Each agent holds an **opinion** in `[-1, +1]` (the poles are
domain-specific: bearish/bullish, block/approve, flop/viral).

The design goal is realistic social dynamics at low cost: only a small fraction
of agents call the LLM each round; the rest update through cheap deterministic
math. The engine is **domain-agnostic** — finance, coding, and Hacker News are
plugins behind a `DomainAdapter` interface, and `lightningfish_core` contains no
domain strings (enforced by a test).

```
lightningfish_core/     Engine, models, tiers, metrics, backtest, calibration
lightningfish_finance/  7 investor archetypes + yfinance/Reddit data
lightningfish_coding/   6 reviewer archetypes + CIBot + GitHub data
lightningfish_hn/       6 HN archetypes + Algolia seed enricher + points/comments ground truth
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

### Diagnostic: the sim discriminates on synthetic extremes, but real PR seeds
    lack the signal that determines real outcomes

A local good-vs-bad probe (two fixed synthetic PRs, qwen2.5:7b) initially looked
encouraging:

- clean, well-tested, CI-green bugfix → **+0.26 (approve)**, every archetype positive
- huge, untested, CI-failing rewrite → **−0.26 (block)**, every archetype negative

That ruled out a trivial bug (the sim *can* reach a negative verdict) — but it
does not generalize to real repo data, and later runs contradict the "thin
seeds" theory this section previously proposed.

**Seed enrichment was implemented** (`ci_pass_rate` populated at enrich time,
un-neutralizing CIBot; PR description and a diff excerpt added to the summary —
commit adding signal the naive baseline cannot see) and **did not change the
outcome.** Across three separate `pallets/flask` backtest runs (pre-enrichment,
post-enrichment, and post-enrichment with a naive-baseline bug fix — different
PR samples each time), **the sim predicted "approve" on every single real PR: 17
for 17.** That is not sampling noise — it is the sim structurally unable to
reach a block verdict on real closed-PR data, in direct contrast to the
synthetic probe.

A 4th independent `pallets/flask` run (a local event cache — see below — was
built specifically so this investigation could iterate without repeatedly
spending GitHub's unauthenticated rate limit) made it 23 approve-predictions
out of 23 real PRs across four separate runs.

**Root cause — resolved via two offline diagnostics, not a population-mix
issue:**

1. **Per-archetype breakdown** on all 6 cached real PRs
   (`run_archetype_breakdown.py`) showed **every archetype, including
   SecurityReviewer (contrarian_tendency=0.60) and DomainExpertMaintainer
   (contrarian_tendency=0.50, highest resistance)**, landing approve on nearly
   every PR — not just the compliant majority. The one exception
   (DomainExpertMaintainer, −0.06 on #6013) was on a PR that *did* merge.
   **CIBot alone is the tell**: it scored +0.86 to +1.0 (CI ~93–100% passing)
   on all 6 PRs — including the 3 that were closed *without* merging. The CI
   signal genuinely does not distinguish these outcomes.
2. **Population sweep** (`sweep_population` / `run_population_sweep.py`)
   confirmed it: `default`, `critical` (Security/Performance/DomainExpert
   overweighted), `juniors_only`, and `experts_only` (100%
   SecurityReviewer + DomainExpertMaintainer — the two most skeptical,
   highest-resistance archetypes) **all scored identically (50%, same
   approve-on-everything pattern)**. Rebalancing the population cannot fix
   this, because it was never a population problem.

**Conclusion:** the seed genuinely lacks the signal that determined these real
outcomes. Real closed-and-unmerged PRs on a mature repo are not rejected for
poor code quality visible in CI/tests/diff size — they're closed for reasons
outside the seed entirely (maintainer bandwidth, superseded by another PR, out
of scope, staleness). Every archetype, however skeptical, reasonably reads
"CI passing, tests included, reasonable diff" as approve-favorable, because it
is — the dynamics are not broken, the available signal simply does not predict
the outcome. Fixing this needs seed content that exists *outside* what GitHub's
PR metadata API exposes (e.g. the actual review thread, or an explicit
"why was this closed" signal) — not further engine or population tuning.

**Also found and fixed in this investigation:** the naive baseline's original
0.5/0.5 weighting of "tests included" vs "CI passing" could cancel to exactly 0
whenever the two disagreed — invisible while `ci_pass_rate` was always `None`,
but it silently collapsed naive accuracy from 67% to 33% the moment enrichment
started populating it. Fixed to asymmetric 0.6/0.4 weights so the two signals
can no longer tie.

**Infra built during this investigation** (all in `lightningfish_core/`,
offline after the first fetch): `EventCache`/`CachingAdapter`
(`event_cache.py`) cache enriched seeds + ground truth by
`adapter.cache_key()`, wired into both the backtest and calibration CLIs, so
iterating on a diagnosis no longer re-spends GitHub API budget. Built on top:
an offline per-archetype breakdown CLI and a population-mix sweep
(`sweep_population`), both usable on any cached repo with zero further network
calls.

### HN domain investigation: a real core bug found, but not the root cause

The third domain (Hacker News reception/engagement, see
[specs/2026-08-09-hn-sentiment-domain-design.md](specs/2026-08-09-hn-sentiment-domain-design.md))
showed the same shape of problem as coding at first: on a real, class-balanced
n=30 sample, the sim scored **worse than chance** — 47% (points) and 39%
(comments) against a majority-class floor of 50%/57%, while the naive
karma+URL baseline hit 70%. The sim predicted "viral" on 29 of 30 stories.

**A real, independent core bug was found and fixed along the way.**
`TierRouter.route()` selected T2 "reactor" agents via `eligible_t2[:max_t2]` —
a plain list slice, not a random or representative sample. Since
`build_*_personas()` constructs agents archetype-by-archetype from a fixed
config list, whichever archetype is declared **first** (CasualLurkerVoter in
HN, ValueInvestor in finance, SecurityReviewer in coding) silently claimed
every T2 slot, every round, for the whole run — the only tier that reads the
crowd feed and gets a real LLM re-evaluation. Confirmed by a regression test
(`test_t2_selection_is_not_biased_by_construction_order`) and fixed to
`random.sample`. This affects all three domains, not just HN.

**Re-running the HN backtest with the fix showed the bug was real but not
causal here**: per-archetype magnitudes changed substantially (e.g.
EarlyAdopterHypeBeast, previously starved of T2 access, swung from ~±0.1 to
±0.5+ once it got a fair share), but the aggregate sign pattern was
unchanged — because EarlyAdopterHypeBeast and ShowHNFounder are *also*
high-herding "hype" archetypes, giving them fair access just added more
voices amplifying the same bias rather than counteracting it.

**Root cause, found via a three-layer synthetic probe** (isolating the raw
model, a persona-alone call, and the full simulation on two maximally
unambiguous synthetic stories — a benchmarked/reputable-author post vs. a
spam bit.ly/karma=1 post):

1. The **raw single-LLM-call baseline** (no persona) scored the obvious spam
   post at **+0.25 (still "viral")** — a genuine positivity bias in the raw
   model's response to the prediction framing, even on egregiously bad content.
2. **Persona-conditioned calls correctly override it**: GreybeardCynic alone
   scored the same spam post at **−0.92**, ContrarianSkeptic at **−0.85**.
3. **The full simulation correctly discriminates**: GOOD → **+0.19**, BAD →
   **−0.25**, with even EarlyAdopterHypeBeast swinging to **−0.60** on the bad
   post. This is the same clean sign-correct result the coding domain's
   synthetic probe produced (+0.26/−0.26) — the dynamics, tier-routing, and
   personas all work correctly given unambiguous content.

**Conclusion, parallel to coding's:** the mechanism is not broken — it
demonstrably discriminates when the seed carries a real signal. Real HN
stories that flopped (`points=1–4`) evidently don't look like the synthetic
BAD example; a flopped story's title/text/URL/author-karma doesn't carry the
kind of unambiguous negative signal a spam post does. HN reception, like PR
merging, is apparently driven substantially by factors outside the static
submission content (timing, luck, who sees it early, the ranking algorithm) —
not a defect in this simulator. Improving on this would need either richer
seed content or accepting a real ceiling on how predictable HN reception is
from submission content alone.

### Signal-ceiling check: does richer static metadata beat the naive baseline?

Before investing in new seed enrichment (e.g. pulling early comments), a fair
question is whether the *existing* seed fields already contain more signal
than the current naive baseline extracts. Tested offline against the 36
cached, class-balanced real HN events (no network/LLM calls — a session
scratch script, not committed): several single-feature and combined
heuristics built from fields already present in the seed (author karma at
several thresholds, `has_url`, known-good domain allowlist, tag, title
length, title-has-digit, self-post presence, log-scaled karma).

Result: **author karma alone (> 500) scores 69% — identical to the current
naive baseline** (karma + `has_url`, 0.6/0.4 weighted), meaning `has_url`
contributes nothing measurable. Every other single feature is at or below the
50% majority-class floor. Every richer *combination* tested scored **worse**
than karma alone (64%, 58%, 50%) — adding uninformative features (url,
domain, tag, title shape) dilutes rather than helps. Conclusion: there is no
under-exploited signal in the current static seed fields; author identity is
carrying essentially all of the predictive power available from submission
metadata. This is evidence for a real ceiling, not proof (n=36), but the
pattern — one feature clearly above chance, everything else clustered at or
below chance, combinations strictly worse — is not noise-shaped.

This ceiling is independently corroborated: a separate ML+LLM Hacker News
predictor (144K stories, LightGBM + embeddings + Claude-generated comments,
unaffiliated project) reports the same "~60-70% accuracy ceiling" from a
completely different modeling approach. Academic work on Reddit meme virality
similarly finds author reputation/network features dominate *early*
predictability, with content signal only reemerging as the post ages and
picks up its own engagement trail — consistent with the seed-only ceiling
found here, and consistent with early comments (post-submission, dynamic)
being the one untested lever with a plausible shot at moving past it, as
opposed to further static-content enrichment.

### Early comments: the dynamic signal is real, and it relocates the question

The ceiling check above justified spending effort on early community reaction
rather than more static-content parsing. That experiment
([early_comments.py](lightningfish_hn/early_comments.py),
`run_backtest hn-early`) re-seeds the **same 36 stories** — read from the
submission-only cache, so the comparison is paired and not a different sample —
with every comment posted in the story's first 2 hours.

Point-in-time safety is enforced, not assumed: the window is re-checked locally
per comment rather than trusting the server-side filter, a window larger than
25% of the settlement period raises, and tests assert the target values never
reach the seed. The task framing does change — it becomes "given the submission
*and* its first 2h of reaction, predict reception at 24h" — which is strictly
easier than submission-only, so these numbers are **not comparable** to the
69%/47% above. The baseline ladder gains a matching rung
(`naive_early`) so the simulation must beat *counting* the comments, not merely
notice they exist.

**Result on the points axis (n=36, offline, no LLM):**

| Predictor | Accuracy |
|---|---|
| majority class | 50% |
| karma (submission-only ceiling) | 69% |
| **early-comment count, first 2h** | **86%** |

The structure matters more than the headline:

- **All 13 stories with ≥2 early comments went viral — 13/13.** Perfect
  precision; no flop in the sample drew more than one early comment.
- **All 5 errors are viral stories with *zero* early comments**, one of which
  reached 220 points. The baseline's only failure mode is false negatives on
  slow burners.

So the cheap count baseline is saturated where comments exist and **blind on the
23 zero-comment stories** (18 flop, 5 viral), where it must guess "flop" and
scores 78%. That subgroup is the only place left where submission content is the
sole available signal, and it is therefore the sharp test for the simulation:
can multi-agent reading of the *content* beat guessing the majority inside the
blind subgroup? Answering it needs the sim run, which is compute-bound (see
below) and not yet done.

**Honesty about novelty:** "early engagement predicts later engagement" is not a
new finding and should not be presented as one — it is close to tautological, and
the 86% mostly reflects that. The non-obvious parts are the *shape* (perfect
precision, errors exclusively on zero-comment virals) and the blind-subgroup
question, which is not answered by the count baseline at all.

**Compute note.** The sim run is blocked on hardware, not code. Ollama on this
host runs CPU-only (`size_vram: 0`) alongside an unrelated RL training job; a
trivial 23-token completion measured **27 seconds**, putting a 36-event run at
6–10 hours. A first attempt also exposed a real bug — `LocalProvider` built its
OpenAI client with no timeout, inheriting the SDK's 600s × 2 retries, so one
wedged request stalled a run indefinitely at event 12/36. Now bounded and
degrading through the existing parse-failure path
([llm_provider.py](lightningfish_core/llm_provider.py)).

### Prior art and where this project sits

A literature/prior-art check (2026-08) found active research in LLM-based
social simulation, but it clusters around a few shapes this project doesn't:
opinion-dynamics/dissemination models validated by trajectory-shape matching
against real corpora rather than held-out settled-outcome backtests (OpinioNet,
DualMind, POSIM); large recommendation-driven "world models" with real user
pools (SocioVerse); and content-engagement classifiers that compare LLMs
against fine-tuned BERT baselines rather than against a multi-agent simulation
(the "action-guided response generation" COVID-tweet study) — that study found
user/history features dominate over content for engagement prediction, the
same shape of result as the karma-ceiling finding above.

A 2025 review ("Validation is the central challenge for generative social
simulation") names exactly the gap this project has been closing: rigorous
backtesting against real settled outcomes, compared against content-free and
single-LLM-call baselines with a significance test, is uncommon in this space
— most published work validates by replicating aggregate statistics or
trajectory shapes, not by beating baselines on held-out prediction.

What looks genuinely distinctive here, based on this check (not exhaustive —
no formal lit review was done): (1) one adapter architecture spanning three
unrelated domains (finance, code review, HN) under a single engine, rather
than a bespoke model per platform; (2) point-in-time safety as an explicit,
tested architectural guarantee (ground-truth fields never enter the seed) —
most backtests in this space don't state this guarantee explicitly; (3) the
three-rung baseline ladder (naive heuristic → single-LLM-call → multi-agent
sim) with a binomial significance test on the sim's edge over the best
baseline, which forces an honest answer to "is the multi-agent machinery
adding anything" rather than reporting simulation accuracy in isolation. The
signal-ceiling check above — verifying no unexploited signal exists in current
features before greenlighting new data collection — is the same discipline
applied one level down, to the seed-enrichment decision rather than the model.

No formal comparative evaluation was done against any of the cited systems;
this is a directional read from public descriptions, not a benchmark.

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

