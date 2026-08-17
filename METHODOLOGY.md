# The Baseline Ladder

**A validation protocol for generative social simulations.**

Multi-agent LLM simulations are usually validated by showing they *reproduce*
something — an opinion trajectory's shape, an aggregate distribution, a known
social phenomenon like echo chambers or the friendship paradox. Reproduction is
necessary but weak evidence: a simulation can match the shape of real dynamics
while carrying no predictive information about any particular case, and a 2025
review of the field ("Validation is the central challenge for generative social
simulation") identifies this as the discipline's central unsolved problem.

This document specifies the protocol Lightningfish uses instead: score the
simulation against **real settled outcomes** on held-out events, and require it
to beat a ladder of progressively stronger references. The ladder is the point.
A single accuracy number is close to meaningless; what matters is which rung it
clears.

---

## The four rungs

| # | Reference | What it controls for | Implementation |
|---|---|---|---|
| 0 | **Majority class** | Degenerate data. Always predicting the common outcome. | `BacktestReport.majority_class_accuracy` |
| 1 | **Naive heuristic** | Metadata signal. A content-free rule over structural fields — no model, no content. | `DomainAdapter.naive_prediction` |
| 2 | **Single LLM call** | The language model itself. One prompt, one answer, no agents, no rounds. | `backtest.llm_baseline` |
| 3 | **The simulation** | — | `run_backtest` / `score_precomputed` |

**Rung 2 is the one that matters and the one that is almost never reported.**
Beating a naive heuristic shows the model knows something. Only beating a single
LLM call shows the *multi-agent machinery* — the personas, the rounds, the
herding, the tier routing — is contributing anything at all. A simulation that
matches its own single-call baseline is an expensive wrapper around one prompt,
whatever its trajectories look like.

The verdict is all-or-nothing: `beats_baselines` must be true for every entry
**and** the accuracy must exceed the majority class. Clearing three rungs and
failing the fourth is a failure.

---

## Significance

Raw accuracy on small event sets is mostly noise. Every report carries a
one-sided binomial test of the simulation's correct count against the *best*
rung, not against chance:

```python
binomtest(sim_correct, n, p=best_reference_accuracy, alternative="greater")
```

Reported as `p_value_vs_best`. A simulation at 75% against a 70% best reference
on n=36 is not a result — it is four coin flips of separation. The null is
deliberately harsh: beating chance is uninteresting when a two-line heuristic
already beats chance.

---

## The six rules that make the comparison honest

Most of the ways this protocol can be quietly rigged were found by rigging it
accidentally, in this repo, and then finding the bug.

### 1. Point-in-time safety

No field derived from the outcome may enter the seed. This is an architectural
guarantee, not a review convention — the seed enricher is a separate module from
the ground-truth fetcher, and tests assert the target values never appear in the
seed text or metadata.

*Found the hard way:* the finance domain's seeds originally carried headline
text written after the price move. It read as a fair backtest and was not one.

### 2. Baselines see exactly what the simulation sees

When the seed is enriched, every baseline is re-derived over the enriched seed.
Enriching only the simulation's input and comparing against a baseline built on
the old, poorer input manufactures an edge out of nothing.

*Applied:* adding early comments to the HN seeds required adding an
early-engagement rung to the ladder in the same change. The simulation now has to
beat a baseline that counts the comments in order to show it is *reading* them.

### 3. Thresholds are chosen a priori, never tuned on the test set

Class thresholds, gap zones, and baseline cutoffs are fixed before scoring and
documented as first-pass estimates. A baseline cutoff fitted to the evaluation
set is not a baseline; a simulation tuned against the same set is not validated.

*Applied:* `EARLY_COMMENT_THRESHOLD = 2` was picked from HN's shape, not from a
sweep, and is commented in the source to say so.

### 4. Class-balanced sampling

"The N most recent settled events" degenerates. Real event streams are wildly
imbalanced, and an imbalanced sample makes the majority-class rung trivially
high while making a biased simulation look accurate.

*Found the hard way:* the coding domain's first PR sample came back ~100% one
class. Sampling now pulls each class against its own threshold explicitly.

### 5. Ambiguous outcomes are skipped, not guessed

Between the high and low thresholds sits a gap zone that scores as *no
direction* and is excluded (`truth_direction` returns 0). Forcing a call on a
genuinely ambiguous outcome adds noise to every rung and rewards whichever one
happens to be biased toward the more common side.

### 6. Ground truth is measured once and reused

If the outcome metric keeps moving, "the ground truth" is a function of *when
you asked*. Measure once, store the measurement with a timestamp, and have
every later run read that stored value.

*Found the hard way:* HN points accrue indefinitely and the API serves only
current totals, so a second run re-measured and disagreed with the first on
6 of 22 events — one flipping class outright when a 4-point story reached 108
four days later. Two runs claimed to be paired were not. Records now carry
`measured_at_i` / `age_at_measurement_s`, and `copy_ground_truth_from` imports
the original measurements rather than re-fetching.

---

## Diagnosing a failure

A simulation that fails the ladder has failed for one of four reasons, and they
are distinguishable:

1. **Structured-output collapse.** Check `mean_parse_success_rate` and
   `low_confidence_events` first. Below 0.8 the run reflects format failures,
   not dynamics, and nothing else in the report means anything.
2. **Population mix.** Re-score the same cached events under different archetype
   proportions (`run_population_sweep`). If accuracy moves, the default mix was
   outvoting its dissenters.
3. **Mechanism bug.** Run a synthetic probe: two maximally unambiguous events,
   one clearly positive and one clearly negative, through all three layers
   (raw call, single persona, full simulation). Correct discrimination on
   synthetic extremes plus failure on real data localizes the problem to the
   data, not the engine.
4. **No signal in the seed.** What remains after the first three. Confirm it
   with a **ceiling check**: measure how much accuracy every available seed
   field can produce on its own before concluding the simulation is at fault —
   and before spending effort enriching.

The ceiling check is the same discipline applied one level down. Before
collecting new data, verify the existing features are actually exhausted.

---

## Worked results

Applied to three domains. The protocol's value is visible in that most of these
are negative, and were reported as negative:

| Domain | Majority | Naive | Sim | Verdict |
|---|---|---|---|---|
| Coding (PR merge) | — | ties/beats sim | at or below naive | **fails** — seed lacks the signal |
| HN points, submission-only | 50% | 69% | 47% | **fails** — worse than chance |
| HN comments, submission-only | 57% | 71% | 39% | **fails** |
| HN points, +2h early comments | 50% | 69% karma / **86% early-count** | — | baseline jumped, see below |
| HN points, blind subgroup (n=22) | 73% | 55% karma / 73% early-count | **32%** (single_llm 27%) | **fails** — loses to a constant guess by 41 pts |

The last row is where the protocol earns its keep. Enriching the seed with early
comments raised the *baseline* from 69% to 86% — so a simulation scored only
against the old baseline would have looked dramatically improved while actually
being outperformed by a one-line comment count. Rule 2 is what catches that.

It also relocates the real question. The count baseline is perfect where
comments exist (13/13) and blind on the 23 stories that drew none, where it
guesses "flop" and scores 78%. A headline accuracy number would hide both facts;
the subgroup where the cheap baseline is blind is the only place the simulation
can demonstrate anything.

The ceiling check on the HN submission-only seeds found that author karma alone
scores 69%, no combination of the remaining static fields beats it, and several
richer combinations score *worse*. That result is what justified spending effort
on early comments rather than on more static-content parsing — and it is the
kind of decision the protocol exists to inform.

---

## Applying this to another simulator

The protocol is not specific to this engine. To run it against any generative
social simulation:

1. Pick a domain with **objective, dated, settled outcomes** — not human ratings.
2. Build a seed enricher that provably cannot see the outcome, and test that.
3. Write the content-free heuristic first. It is the honest floor and it is
   frequently much stronger than expected.
4. Add the single-call baseline. This is the rung that decides whether the
   multi-agent design is earning anything.
5. Sample class-balanced, define a gap zone, and fix all thresholds before
   scoring.
6. Report all four rungs and the p-value. Report negatives.

The harness in `lightningfish_core/backtest.py` is domain-agnostic — it needs
only a `DomainAdapter` — and is reusable as-is.

---

## Honest limits of this document

This is a protocol writeup, not a peer-reviewed contribution, and no formal
comparative evaluation was run against the systems it contrasts with. The
event counts here (n≈30–40 per domain) are small enough that individual
accuracy figures carry wide confidence intervals; they are adequate to
demonstrate the protocol and to support negative conclusions, and not adequate
to support a positive claim of general predictive skill. The rung-2 argument —
that a multi-agent simulation must beat its own single-call baseline to justify
itself — is the part expected to hold up independently of anything specific to
this codebase.

See [ARCHITECTURE.md](ARCHITECTURE.md) §4 for the harness internals and §10 for
the full findings log.
