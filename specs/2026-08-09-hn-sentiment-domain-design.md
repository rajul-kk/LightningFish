# Hacker News Sentiment-Propagation Domain — Design

**Status:** approved, not yet implemented.
**Scope:** core `DomainAdapter` + backtest/calibration/cache CLI integration only. No web UI, no live/streaming demo.

## Purpose

A third Lightningfish domain modeling how a population reacts to a submitted
Hacker News story — a general-purpose sentiment-propagation testbed distinct
from finance (market opinion) and coding (PR review), using content that
anyone can relate to without domain expertise.

## Why Hacker News

Evaluated against Reddit, Twitter/X, and political polling APIs (see chat
research prior to this spec). HN's Algolia Search API (`hn.algolia.com/api/v1`)
won on every axis that mattered after this session's backtest work:

- **Free, unauthenticated, 10,000 req/hour** — vs. Reddit's now-paid API
  ($0.24/1K calls, $12K/yr minimum) and 403'd unauthenticated endpoints, and
  vs. no meaningful free historical access for Twitter/Instagram/LinkedIn.
- **Point-in-time-safe by construction**: a story's `title`/`story_text`/`url`/
  `author`/`created_at` never change; `points`/`num_comments` are separately
  queryable outcomes — the same clean shape as price data, without finance's
  "current headlines leak into historical seeds" problem this session fixed.
- **Continuous stream of events** (not one-outcome-per-race like polling data),
  supporting a real backtest sample size.
- **Numeric, not just binary, outcome** — `points` and `num_comments` are
  richer than approve/block or up/down.

## Hard constraint: no ground-truth leakage into the seed

`enrich_hn_seed()` MUST NOT read or store `points`/`num_comments`. Seed content
is limited to submission-time-invariant fields only. Ground truth is fetched
by a separate, later call (`get_hn_ground_truth`), exactly mirroring the
existing seed/ground-truth separation in `lightningfish_coding`. A test must
assert the enriched seed's summary and metadata never contain these fields.

## Module layout

New package `lightningfish_hn/`, matching the shape of
`lightningfish_finance`/`lightningfish_coding`:

```
lightningfish_hn/
  personas.py         # archetype configs + build_hn_personas()
  seed_enricher.py     # fetch a story by id, build EnrichedSeed (no outcome fields)
  ground_truth.py      # fetch a story's current points/num_comments (>=24h old only)
  backtest_events.py    # class-balanced historical story puller
  config.py            # HNDomainAdapter(DomainAdapter)
```

## Archetypes

Six archetypes, sized so no single one dominates the population the way
JuniorContributor (40%) did in coding — deliberately leaving room for genuine
contest between camps:

| Archetype | Share | Character | Key parameters |
|---|---|---|---|
| CasualLurkerVoter | 30% | Silent-majority upvoter, low engagement | low influence, moderate herding |
| EarlyAdopterHypeBeast | 18% | Jumps on shiny new things fast | low resistance, high recency_bias, high herding |
| ContrarianSkeptic | 15% | The "well, actually" pushback commenter | high resistance, negative herding, high contrarian_tendency |
| DomainExpertPedant | 15% | Technical authority, comments carry weight | high influence_weight, high resistance |
| GreybeardCynic | 12% | "This was solved in 1987," reflexively dismissive | very high resistance, negative herding, low recency — persistent dissenting pole (this domain's ShortSeller/ValueInvestor equivalent) |
| ShowHNFounder | 10% | Emotionally invested submitter-adjacent booster | low resistance, high recency_bias |

No rule-based archetype (no `CIBot` equivalent) — unlike coding's CI pass/fail,
there is no clean deterministic signal available for HN submissions.

Exact numeric parameters (`opinion_resistance`, `recency_bias`,
`contrarian_tendency`, `influence_weight`, `herding_coefficient`) are
first-pass estimates set during implementation, following the same pattern and
caveat as `lightningfish_coding/personas.py` ("NOT grounded in published
literature, treat calibration results as provisional").

## Seed enrichment

`enrich_hn_seed(story_id)` builds an `EnrichedSeed` from:
- `title`, `story_text` (full text for Ask/Show HN; empty for link posts), `url`
- `url`'s domain (e.g. `github.com`, `arxiv.org`) as a mild credibility signal
- `author` username, `created_at`, tag (`show_hn`/`ask_hn`/plain story)
- `author_karma`, fetched once via `/users/<username>` — safe to include
  (describes the author's *general* reputation, not this story's own outcome)

## Naive baseline

Mirrors the asymmetric-weight fix applied to the coding baseline this session
(equal weights can tie to exactly 0 when signals disagree):

```
score = (0.6 if author_karma > _KARMA_REFERENCE else -0.6) + (0.4 if has_external_url else -0.4)
```

`naive_prediction(seed)` only receives a single seed (no access to the current
pull's population), so the comparison must be against a **fixed constant**
(`_KARMA_REFERENCE`, a rough HN-wide reference value picked during
implementation), not a "median of this batch" — the latter isn't computable
from the method's signature.

Comments-direction baseline: presence of a question mark / `ask_hn` tag as a
discussion-bait heuristic, same asymmetric-weight principle.

## Ground truth & balanced sampling

`get_hn_ground_truth(story_id)` only serves stories **≥24 hours old** (per
design review — HN front-page dynamics mostly resolve within a day; this
keeps a large pool of eligible historical stories while ensuring settled
totals).

`pull_hn_events(limit: int = 20)` does a **class-balanced pull**, not a naive
"N most recent stories" sample — the fix that resolved the coding domain's
degenerate "100% of recent closed PRs were unmerged" sampling bug. Same
`limit` default and meaning as `pull_pr_events` (half-and-half split, so
`limit=20` yields ~10 per class). Default split:

- Points-direction: half `points >= 40`, half `points < 15` (15–39 is a
  deliberate gap zone, excluded, to keep classes cleanly separated)
- Comments-direction: same balanced-pull logic against `num_comments`

Both thresholds are named constants, easily adjusted once real data is seen.

## Backtest integration: two scorings of one simulation

Both "points" and "comments" predictions reuse the existing `run_backtest`
machinery unchanged — `sign(trajectory[-1])` as the prediction — scored
against two different ground truths via two thin wrapper adapters (same
`CachingAdapter`-style pattern as the calibration CLI):

- **Points backtest**: `truth_direction()` reads `points`; naive baseline is
  the karma/url heuristic.
- **Comments backtest**: a wrapper overriding `truth_direction()` to read
  `num_comments`; its own naive baseline (question-mark/`ask_hn` heuristic).

The comments-direction wrapper is a small adapter subclass living in
`lightningfish_hn/config.py` (e.g. `HNCommentsAdapter(HNDomainAdapter)`,
overriding only `truth_direction`/`naive_prediction`) — not a core-level
abstraction, following the same "thin wrapper adapter" pattern already used
for `CachingAdapter`.

Each event is simulated **once** (simulation is the expensive step; ground
truth fetch is cheap) and the single resulting trajectory is scored twice.

**Documented v1 simplification, not a hidden gap:** this assumes positive
simulated reception also predicts high engagement, which will not always hold
(a controversial post can draw heavy comments despite negative sentiment). If
the points backtest validates but comments doesn't (or vice versa), that is
itself a useful finding — and would be the evidence-based trigger for a real
second engine dimension (rejected for v1 as premature — see Alternatives).

## Alternatives considered

- **Extend the engine to a true second opinion dimension** (multi-dimensional
  `current_opinion`, touching `models.py`, `engine.py`, every tier update and
  metric). Rejected for v1: a significant, risky rearchitecture to validate
  against an unproven domain, before evidence justifies it.
- **Single target only (points), drop comments.** Rejected: throws away a
  genuinely interesting engagement/controversy signal HN's data supports well,
  and the user wants both.
- **Naive "N most recent settled stories" sampling** (mirroring the original,
  buggy coding sampler). Rejected: this session found that pattern degenerates
  on real data (flask's recent closed PRs were ~100% one class); balanced
  sampling is required from the start.

## Testing plan

Mirrors `lightningfish_coding`'s existing test suite shape:

- `test_seed_enricher.py` — mocked Algolia responses; **must assert the
  enriched seed's summary and metadata never contain `points`/`num_comments`**
- `test_personas.py` — archetype presence, proportions, jitter
- `test_backtest_events.py` — balanced pull returns both classes, respects the
  ≥24h ground-truth-eligibility window
- `test_ground_truth.py` — direction mapping for points and comments
- Extend the existing domain-string-ban test (`test_done_criteria.py`) —
  `lightningfish_core` must stay free of `"hn"`-domain-specific strings, same
  as it already enforces for finance/coding

## Non-goals for v1

- No web UI / frontend registration
- No live/streaming demo
- No new calibration-grid defaults (reuses existing `grid_search`/
  `sweep_population` as-is)
- No comment-thread-content enrichment (the API's `children` ids are available
  but unused this round — a natural future extension, not required now)
