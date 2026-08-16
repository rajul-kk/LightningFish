# Lightningfish — Architecture Pipeline

> **Snapshot from Plan 1** (finance + coding domains only, predates the HN
> domain and later engine fixes). For the current, maintained technical
> reference see [ARCHITECTURE.md](ARCHITECTURE.md). Kept here as a pipeline
> diagram of the Modal/Next.js deployment shape, not a source of truth for
> current domain/engine mechanics.

---

## Repository layout

```
lightningfish/
│
├── lightningfish_core/          # Domain-agnostic engine — zero external knowledge
│   ├── models.py                # Shared dataclasses (EnrichedSeed, AgentPersona, RoundEvent, …)
│   ├── adapter.py               # DomainAdapter ABC — the plugin contract
│   ├── enricher.py              # EnricherPlugin ABC — composable data fetchers
│   ├── registry.py              # DomainRegistry — auto-discovers plugins via entry points
│   ├── engine.py                # SimulationEngine — orchestrates rounds, calls LLM, updates followers
│   ├── tier_router.py           # TierRouter — splits agents into active (LLM) / follower (formula)
│   ├── resistance.py            # compute_effective_resistance() — Kahneman-Tversky anchoring math
│   ├── rule_agent.py            # RuleBasedAgent — deterministic agent base (always tier-2)
│   └── backtest_base.py         # BacktestHarness ABC — calibration loop skeleton
│
├── lightningfish_finance/       # Finance domain plugin
│   ├── __init__.py              # Registers FinanceDomainAdapter on import
│   ├── config.py                # FinanceDomainAdapter — wires together all finance modules
│   ├── personas.py              # 7 investor archetypes + short_seller_resistance override
│   ├── seed_enricher.py         # yfinance + event-type classifier → EnrichedSeed
│   ├── ground_truth.py          # Reddit (praw) sentiment + yfinance price series
│   └── run_backtest.py          # FinanceBacktestHarness — SEC EDGAR 8-K batch runner
│
├── lightningfish_coding/        # Code review domain plugin
│   ├── __init__.py              # Registers CodingDomainAdapter on import
│   ├── config.py                # CodingDomainAdapter — wires together all coding modules
│   ├── personas.py              # 6 reviewer archetypes + CIBot (RuleBasedAgent subclass)
│   ├── seed_enricher.py         # GitHub REST API → EnrichedSeed (diff size, languages, CI)
│   ├── ground_truth.py          # GitHub check-runs API → CI pass rate + merge outcome
│   └── run_backtest.py          # CodingBacktestHarness — public-repo PR batch runner
│
├── lightningfish_service/       # FastAPI HTTP service (runs on Modal)
│   ├── main.py                  # App factory — imports plugins, mounts routers, sets CORS
│   ├── modal_app.py             # Modal deployment wrapper (scale-to-zero, 10 min timeout)
│   ├── db.py                    # Postgres helpers via psycopg2 (Neon)
│   ├── serializers.py           # Dataclass ↔ dict — excludes non-serialisable callables
│   ├── migrate.py               # Schema v1 — simulations, round_events, api_keys tables
│   ├── migrate_v2.py            # Schema v2 — adds model + agent_config_json columns
│   └── routes/
│       ├── enrich.py            # POST /enrich
│       ├── simulate.py          # GET /simulate (list) · POST /simulate · GET /simulate/{id}
│       │                        # GET /simulate/{id}/result
│       ├── chat.py              # POST /chat/{id}
│       ├── backtest.py          # POST /backtest/{domain}
│       └── keys.py              # GET/POST/DELETE /keys
│
├── lightningfish_web/           # Next.js 15 App Router (deploys to Vercel)
│   ├── middleware.ts            # Clerk auth — protects all routes except /
│   ├── app/
│   │   ├── page.tsx             # Landing — domain selector cards
│   │   ├── simulate/
│   │   │   ├── [domain]/page    # Seed form + model picker + agent mix
│   │   │   └── [id]/live/page  # SSE live viewer → auto-redirects to report
│   │   ├── report/[id]/page     # Full report: chart + stats + agent interview
│   │   ├── history/page         # Simulation history table
│   │   └── dev/keys/page        # API key management
│   ├── components/
│   │   ├── OpinionChart         # Recharts line chart — trajectory over rounds
│   │   ├── DistributionBar      # Bearish / neutral / bullish horizontal bar
│   │   ├── RoundFeed            # Live per-round activity list
│   │   ├── AgentChat            # Post-simulation persona interview
│   │   └── CostMeter            # Running cost + round progress bar
│   └── lib/
│       ├── types.ts             # Shared TS types + DOMAINS / MODELS / ARCHETYPES constants
│       ├── api.ts               # Typed fetch wrappers to the Python service
│       └── use-sse.ts           # useSimulationStream hook — EventSource → state
│
└── tests/
    ├── core/                    # Engine, models, adapter, registry, resistance, tier_router
    ├── finance/                 # Personas, seed enricher, scoring
    └── coding/                  # Personas (incl. CIBot), seed enricher, scoring
```

---

## End-to-end request pipeline

```
Browser
  │
  │  1. POST /simulate
  │     { domain_id, raw_input, n_agents, n_rounds, model, agent_config }
  │
  ▼
Next.js (Vercel)
  │  Clerk middleware validates session token
  │
  ▼
FastAPI (Modal)  ──── routes/simulate.py::create()
  │
  ├── DomainRegistry.get(domain_id)
  │     └── returns FinanceDomainAdapter  or  CodingDomainAdapter
  │
  ├── adapter.enrich_seed(raw_input)
  │     Finance path:
  │       ├── yfinance → sector, market_cap_tier
  │       ├── classify_event_type(text) → earnings_beat / ceo_change / …
  │       └── returns EnrichedSeed
  │     Coding path:
  │       ├── GitHub REST → PR metadata, file list, CI checks
  │       ├── classify_diff_size(total_lines) → xs/s/m/l/xl
  │       └── returns EnrichedSeed
  │
  ├── db.create_simulation(id, seed_json, model, agent_config, …)
  │     → Neon Postgres: INSERT INTO simulations
  │
  └── returns { simulation_id }

  │
  │  2. GET /simulate/{id}   (SSE stream)
  │
  ▼
FastAPI  ──── routes/simulate.py::stream()
  │
  ├── db.get_simulation(id)  → loads seed_json, model, agent_config
  │
  ├── adapter.build_personas(n_agents, archetype_config)
  │     └── normalises proportions → list[AgentPersona]
  │
  ├── SimulationEngine(adapter, model=model)
  │
  └── engine.run_streaming(seed, agents, n_rounds)
        │
        │  ┌─────────────────────── round loop ────────────────────────┐
        │  │                                                            │
        │  │  TierRouter.route(agents)                                  │
        │  │    ├── active   (≤10% of pop, influence_weight > 0.65,    │
        │  │    │             non-RuleBasedAgent)  → call LLM           │
        │  │    └── followers (everyone else)      → formula update     │
        │  │                                                            │
        │  │  For each active agent:                                    │
        │  │    Anthropic.messages.create(model, system_prompt, …)      │
        │  │    → float opinion in [-1.0, 1.0]                          │
        │  │    cost += tokens × per-model rate                         │
        │  │                                                            │
        │  │  For each follower:                                        │
        │  │    if RuleBasedAgent (CIBot):                              │
        │  │      opinion = (ci_pass_rate × 2.0) − 1.0                 │
        │  │    else:                                                    │
        │  │      r = compute_effective_resistance(agent, signal)       │
        │  │        └── ShortSellers: r × 1.3 when signal opposes       │
        │  │      opinion = opinion×r + neighbour_pull×(1−r)×0.6        │
        │  │                         + recency_pull ×(1−r)×0.4         │
        │  │      clamp to [−1.0, 1.0]                                  │
        │  │                                                            │
        │  │  yield RoundEvent { mean, stddev, distribution, cost, … }  │
        │  │                                                            │
        │  └────────────────────────────────────────────────────────────┘
        │
        │  (StopIteration carries SimulationResult)
        │
        ├── db.insert_round_event(round)   ← every round
        ├── db.update_simulation_result()  ← on complete
        │
        └── SSE stream:  data: { round_number, mean_opinion, … }\n\n
                         data: { round_number, mean_opinion, … }\n\n
                         …
                         data: { type: "complete", total_cost_usd }\n\n

  │
  │  Browser receives SSE
  │
  ▼
useSimulationStream hook (use-sse.ts)
  │
  ├── each RoundEvent  → setState({ rounds: [...prev, event] })
  │     └── OpinionChart re-renders with new trajectory point
  │         DistributionBar re-renders with new histogram
  │         RoundFeed prepends new round card
  │         CostMeter updates progress bar
  │
  └── type === "complete"  → router.push(/report/{id})
```

---

## Domain plugin system

```
pyproject.toml
  [project.entry-points."lightningfish.domains"]
  finance = "lightningfish_finance:adapter"
  coding  = "lightningfish_coding:adapter"
        │
        │  importlib.metadata.entry_points(group="lightningfish.domains")
        ▼
DomainRegistry                         (lightningfish_core/registry.py)
  ├── register(adapter)  ← also called in __init__.py on import
  ├── get(domain_id)     → DomainAdapter | None
  └── all()              → dict[str, DomainAdapter]

DomainAdapter ABC                      (lightningfish_core/adapter.py)
  ├── enrich_seed(raw_input) → EnrichedSeed
  ├── build_personas(n, archetype_config) → list[AgentPersona]
  ├── agent_system_prompt(seed, persona) → str
  ├── get_ground_truth(seed) → GroundTruthRecord | None
  └── score(result, truth) → BacktestResult

       ├── FinanceDomainAdapter          (lightningfish_finance/config.py)
       │     opinion_labels = ("bearish", "bullish")
       │
       └── CodingDomainAdapter           (lightningfish_coding/config.py)
             opinion_labels = ("block", "approve")

  Third-party domains ship a package that:
    1. Subclasses DomainAdapter
    2. Declares an entry point in their pyproject.toml
    3. Self-registers via registry.register() in __init__.py
```

---

## Agent tiers

```
Population (n agents)
  │
  TierRouter.route()
  │
  ├── Tier 1 — Active  (≤ 10% hard cap, influence_weight > 0.65)
  │     │
  │     │  Each calls LLM with persona-specific system prompt
  │     │  Output: float opinion [-1.0, 1.0]
  │     │
  │     ├── ValueInvestor        resistance=0.85  contrarian=0.70
  │     ├── ShortSeller          resistance=0.90  contrarian=0.95  ← inverse resistance rule
  │     └── InstitutionalAnalyst resistance=0.60  influence=0.90
  │
  └── Tier 2 — Followers  (remaining ~90%)
        │
        ├── RuleBasedAgents  (always tier-2, no LLM)
        │     └── CIBot: opinion = (ci_pass_rate × 2.0) − 1.0
        │
        └── Standard followers  (formula update)
              opinion = opinion × r
                      + neighbour_pull × (1−r) × 0.6
                      + recency_pull   × (1−r) × 0.4

              where r = compute_effective_resistance(agent, social_signal)
                          └── ShortSeller override: r × 1.3 when |signal| > 0.6
                                                    and signal opposes opinion

              ├── RetailFOMO       resistance=0.15  recency=0.95   (herding, fast)
              ├── MomentumTrader   resistance=0.20  recency=0.90   (trend follower)
              ├── MacroTourist     resistance=0.40  recency=0.60
              ├── PassiveLurker    resistance=0.50  recency=0.50   (slow drift)
              └── (+ any archetype not selected as tier-1 this round)
```

---

## Data models

```
EnrichedSeed
  ├── domain_id        "finance" | "coding"
  ├── raw_input        original user submission
  ├── summary          human-readable event description
  ├── entities         list of named entities (ticker, repo, …)
  ├── event_type       classifier output (earnings_beat, m_and_a, …)
  ├── metadata         domain-specific bag (ticker, ci_pass_rate, diff_size_tier, …)
  └── scraped_context  list[ScrapedDocument]
                         └── { url, title, content, source }

AgentPersona
  ├── unique_id
  ├── archetype        "ValueInvestor" | "CIBot" | …
  ├── opinion_resistance   float [0,1]  — anchoring strength
  ├── recency_bias         float [0,1]  — weight on latest signal
  ├── contrarian_tendency  float [0,1]  — push against consensus
  ├── influence_weight     float [0,1]  — tier-1 eligibility threshold
  ├── current_opinion      float [-1,1] — mutated each round
  └── metadata             dict         — callables (resistance_override_fn), extras

RoundEvent
  ├── round_number
  ├── opinion_distribution   list[float]  — all n agent opinions
  ├── mean_opinion
  ├── stddev_opinion
  ├── tier1_calls
  ├── active_agent_ids
  └── estimated_cost_usd

SimulationResult
  ├── seed               EnrichedSeed
  ├── trajectory         list[float]  — mean opinion per round
  ├── round_events       list[RoundEvent]
  ├── final_distribution list[float]
  ├── total_tier1_calls
  └── total_cost_usd
```

---

## Database schema (Neon Postgres)

```
simulations
  ├── id                UUID  PK
  ├── user_id           TEXT            (Clerk user ID)
  ├── domain_id         TEXT
  ├── status            TEXT            pending | running | complete | failed
  ├── seed_json         JSONB
  ├── result_json       JSONB
  ├── n_agents          INT
  ├── n_rounds          INT
  ├── model             TEXT            default 'claude-sonnet-4-6'
  ├── agent_config_json JSONB           null = use domain defaults
  ├── cost_usd          DECIMAL(10,6)
  └── created_at        TIMESTAMPTZ

round_events
  ├── id                UUID  PK
  ├── simulation_id     UUID  FK → simulations(id)  ON DELETE CASCADE
  ├── round_number      INT
  └── event_json        JSONB

api_keys
  ├── id                UUID  PK
  ├── user_id           TEXT
  ├── key_hash          TEXT  UNIQUE    SHA-256 of raw key
  ├── name              TEXT
  ├── budget_usd        DECIMAL(10,4)
  ├── created_at        TIMESTAMPTZ
  └── last_used_at      TIMESTAMPTZ
```

---

## Backtest calibration loop

```
BacktestHarness.run_batch()          (lightningfish_core/backtest_base.py)
  │
  ├── get_seed_events()              implemented by domain harness
  │     Finance: SEC EDGAR 8-K filings for 30 tickers
  │     Coding:  closed PRs from flask, requests, fastapi, django, …
  │
  └── for each seed:
        ├── adapter.build_personas(N_AGENTS, archetype_config=None)
        ├── engine.run(seed, agents, N_ROUNDS)  → SimulationResult
        ├── adapter.get_ground_truth(seed)      → GroundTruthRecord
        └── adapter.score(result, truth)        → BacktestResult
              │
              Finance metrics:
              │   direction_match      sign(trajectory[-1]) == sign(reddit_sentiment[-1])
              │   magnitude_corr       pearsonr(trajectory, sentiment)
              │   price_direction      sign(trajectory[-1]) == sign(price_change_pct)
              │
              Coding metrics:
                  direction_match      (trajectory[-1]>0) == merged
                  magnitude_corr       active_agents / comment_count  (volume proxy)
```

---

## Infrastructure topology

```
User browser
    │  HTTPS
    ▼
Vercel  (Next.js 15)
    ├── Static pages:  /  /history  /dev/keys
    ├── Server pages:  /report/[id]  /history  (fetch from Python service at render time)
    ├── Client pages:  /simulate/[domain]  /simulate/[id]/live  (EventSource SSE)
    └── Clerk middleware on all routes except /
    │
    │  HTTPS (REST + SSE)
    ▼
Modal  (FastAPI, scale-to-zero, 10 min timeout)
    ├── POST   /enrich
    ├── GET    /simulate              list by user_id
    ├── POST   /simulate              create + enrich
    ├── GET    /simulate/{id}         SSE stream
    ├── GET    /simulate/{id}/result  full record
    ├── POST   /chat/{id}             persona interview
    ├── POST   /backtest/{domain}     calibration run
    └── GET/POST/DELETE /keys
    │
    ├── Neon Postgres   (simulations, round_events, api_keys)
    └── Anthropic API   (claude-haiku / sonnet / opus — tier-1 LLM calls)
```
