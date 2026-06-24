# Lightningfish — Design Spec
**Date:** 2026-06-24  
**Status:** Approved

---

## 1. What It Is

Lightningfish is a hosted web product that runs multi-agent opinion simulations and streams the results live to the user. A non-technical user pastes a stock filing URL or a GitHub PR link, picks a domain, and watches a population of agent personas form consensus in real time — round by round — then receives a calibrated report with ground-truth comparison.

The simulation engine is domain-agnostic. Finance and code review are two domain plugins shipped with the product. Any third party can publish a new domain by implementing a single abstract class and registering it via a Python entry point.

The system is built from scratch, inspired by MiroFish's five-step workflow (enrich → populate → simulate → analyze → report) and built on top of OASIS (camel-oasis) as the multi-agent simulation core.

---

## 2. Architecture

### 2.1 System Diagram

```
Browser
  └── Next.js App (Vercel)
        ├── /simulate/[domain]      Seed input
        ├── /simulate/[id]/live     SSE round viewer
        ├── /report/[id]            Report + agent chat
        ├── /history                Past simulations
        ├── /backtest/[domain]      Batch backtest UI
        └── /dev/keys               API key management

Next.js API Routes
  ├── POST /api/simulate            Creates job, calls Python service /enrich
  ├── GET  /api/stream/[id]         SSE proxy → Python service /simulate
  ├── POST /api/chat/[id]           Proxies to Python service /chat
  └── POST /api/backtest/[domain]   Proxies to Python service /backtest

Python Simulation Service (Modal)
  ├── POST /enrich                  Domain adapter enriches raw input → EnrichedSeed
  ├── GET  /simulate                Runs OASIS rounds, streams RoundEvent via SSE
  ├── POST /chat                    Post-simulation agent chat (persona-in-role LLM call)
  └── POST /backtest                Batch runner, returns BacktestResult[]

Storage
  ├── Neon Postgres                 simulations, round_events, api_keys
  ├── Upstash Redis                 In-flight simulation state, rate limiting
  └── Vercel Blob                   PDF reports, JSON exports
```

### 2.2 Five-Step Workflow (per simulation)

1. **Enrich** — raw user input → `EnrichedSeed` via domain adapter (+ optional enricher plugins)
2. **Populate** — persona factory samples N agents from domain archetypes by proportion
3. **Simulate** — OASIS rounds; tier router sends ~5-10% to LLM, rest are rule-based; each round streams a `RoundEvent`
4. **Analyze** — domain adapter scores simulated trajectory against ground truth → `BacktestResult`
5. **Report** — unified JSON/PDF report persisted to Postgres + Blob; agent chat available

### 2.3 Infrastructure

| Layer | Service | Rationale |
|---|---|---|
| Frontend + API routes | Vercel (Next.js 15) | Native Next.js deployment, SSE proxy, edge caching |
| Python simulation service | Modal | Long-running Python, scale-to-zero, streaming-first, no idle cost |
| Database | Neon (Postgres) | Serverless Postgres, Vercel-native integration |
| Cache + job state | Upstash Redis | In-flight simulation tracking, per-user rate limits |
| File storage | Vercel Blob | PDF reports, JSON exports |
| Auth + API keys | Clerk | User auth and API key management in one, Next.js SDK |
| LLM inference | Anthropic (claude-sonnet-4-6) | Tier 1 agent inference |
| Scraping (optional) | Firecrawl | News/web context enrichment for any domain |

### 2.4 Postgres Schema

```sql
simulations  (id uuid pk, user_id, domain_id, status, seed_json, result_json, created_at, cost_usd)
round_events (id uuid pk, simulation_id fk, round_number int, event_json)
api_keys     (id uuid pk, user_id, key_hash, name, created_at, last_used_at, budget_usd)
```

---

## 3. Core Abstractions (`lightningfish_core/`)

### 3.1 `DomainAdapter` ABC

The single interface any new domain must implement. Lives in `lightningfish_core/adapter.py`.

```python
class DomainAdapter(ABC):
    domain_id: str          # "finance", "coding", "legal", ...
    display_name: str       # shown in the UI domain picker
    opinion_labels: tuple   # e.g. ("bearish", "bullish"), ("block", "approve")

    @abstractmethod
    def enrich_seed(self, raw_input: dict) -> EnrichedSeed: ...

    @abstractmethod
    def build_personas(self, n_agents: int) -> list[AgentPersona]: ...

    @abstractmethod
    def agent_system_prompt(self, seed: EnrichedSeed, persona: AgentPersona) -> str: ...

    @abstractmethod
    def get_ground_truth(self, seed: EnrichedSeed) -> GroundTruthRecord | None: ...

    @abstractmethod
    def score(self, result: SimulationResult, truth: GroundTruthRecord) -> BacktestResult: ...
```

### 3.2 `EnricherPlugin` ABC

Optional enrichment step any domain adapter can compose. Lives in `lightningfish_core/enricher.py`.

```python
class EnricherPlugin(ABC):
    @abstractmethod
    def enrich(self, seed: EnrichedSeed) -> EnrichedSeed: ...
```

Shipped implementations:
- `FirecrawlEnricher` — fetches and summarises web URLs into `seed.scraped_context`
- `RedditSentimentEnricher` — pulls Reddit post sentiment for a ticker/topic window
- `YtdlpTranscriptEnricher` — downloads audio, transcribes via Whisper, appends to context

### 3.3 Plugin Registry

Auto-discovery via Python entry points. No manual registration needed.

```toml
# In any domain package's pyproject.toml:
[project.entry-points."lightningfish.domains"]
finance = "lightningfish_finance:adapter"
```

On service startup, `lightningfish_core/registry.py` calls `importlib.metadata.entry_points()` and loads all registered adapters.

### 3.4 Dataclasses (`lightningfish_core/models.py`)

```python
@dataclass
class EnrichedSeed:
    domain_id: str
    raw_input: dict
    summary: str                        # 2-3 sentence LLM summary shown in UI
    entities: list[str]                 # key named entities
    event_type: str                     # domain-defined classification
    metadata: dict                      # domain-specific extras
    scraped_context: list[ScrapedDocument]

@dataclass
class AgentPersona:
    unique_id: str
    archetype: str
    opinion_resistance: float           # 0-1, Kahneman-Tversky anchoring
    recency_bias: float                 # 0-1
    contrarian_tendency: float          # 0-1
    influence_weight: float             # 0-1
    proportion: float                   # population share
    current_opinion: float              # -1 to +1
    metadata: dict                      # domain extras

@dataclass
class RoundEvent:                       # streamed as SSE each round
    round_number: int
    opinion_distribution: list[float]
    mean_opinion: float
    stddev_opinion: float
    tier1_calls: int
    active_agent_ids: list[str]
    estimated_cost_usd: float

@dataclass
class SimulationResult:
    seed: EnrichedSeed
    trajectory: list[float]             # mean_opinion per round
    round_events: list[RoundEvent]
    final_distribution: list[float]
    total_tier1_calls: int
    total_cost_usd: float

@dataclass
class BacktestResult:
    direction_match: bool
    magnitude_correlation: float
    domain_metric: dict                 # domain-specific fields
    total_tier1_calls: int
    estimated_cost_usd: float
```

### 3.5 `TierRouter` (`lightningfish_core/tier_router.py`)

```python
class TierRouter:
    def route(
        self,
        agents: list[AgentPersona],
        active_threshold: float = 0.65
    ) -> dict[str, list]:
        # RuleBasedAgent instances are always routed to followers regardless of influence_weight
        # active = non-rule-based agents where influence_weight > threshold (~5-10% of population)
        # followers = remainder, rule-based update only
        # enforces hard cap: tier1_calls / total_agents <= 0.10 after filtering RuleBasedAgents
```

Follower update formula:
```
new_opinion = (
    agent.opinion_resistance * agent.current_opinion
    + (1 - agent.opinion_resistance) * 0.6 * neighbour_pull
    + (1 - agent.opinion_resistance) * 0.4 * recency_pull
)
```

### 3.6 `ResistanceUpdater` (`lightningfish_core/resistance.py`)

Generic resistance math. Domain-specific overrides (e.g. short-seller inverse rule) are passed as a callable hook, not hardcoded here.

```python
def compute_effective_resistance(
    agent: AgentPersona,
    social_signal: float,
    override_fn: Callable[[AgentPersona, float], float] | None = None
) -> float:
    if override_fn:
        return override_fn(agent, social_signal)
    return agent.opinion_resistance
```

### 3.7 `RuleBasedAgent` (`lightningfish_core/rule_agent.py`)

For deterministic agents (e.g. CIBot) that must bypass the LLM tier entirely.

```python
class RuleBasedAgent(AgentPersona):
    def compute_opinion(self, seed: EnrichedSeed) -> float:
        raise NotImplementedError
    # TierRouter always routes these to tier 2 regardless of influence_weight
```

### 3.8 `BacktestHarness` (`lightningfish_core/backtest_base.py`)

```python
class BacktestHarness(ABC):
    adapter: DomainAdapter

    def run(
        self,
        seed_event: EnrichedSeed,
        n_agents: int,
        n_rounds: int
    ) -> BacktestResult:
        # 1. adapter.build_personas(n_agents)
        # 2. engine.run_simulation(personas, seed_event, n_rounds)
        # 3. adapter.get_ground_truth(seed_event)
        # 4. adapter.score(result, ground_truth)
        # 5. return BacktestResult
        # get_ground_truth is NOT re-declared here — delegated to adapter entirely

    @abstractmethod
    def get_seed_events(self) -> list[EnrichedSeed]: ...
    # Only method BacktestHarness adds beyond the adapter — the seed source for batch runs
```

---

## 4. Finance Domain (`lightningfish_finance/`)

### 4.1 Personas (`personas.py`)

Parameters from Kahneman-Tversky prospect theory and behavioural finance literature.

| Archetype | resistance | recency | contrarian | influence | proportion |
|---|---|---|---|---|---|
| ValueInvestor | 0.85 | 0.10 | 0.70 | 0.60 | 0.12 |
| MomentumTrader | 0.20 | 0.90 | 0.05 | 0.40 | 0.18 |
| RetailFOMO | 0.15 | 0.95 | 0.02 | 0.20 | 0.35 |
| ShortSeller | 0.90 | 0.30 | 0.95 | 0.70 | 0.05 |
| InstitutionalAnalyst | 0.60 | 0.40 | 0.30 | 0.90 | 0.10 |
| MacroTourist | 0.40 | 0.60 | 0.20 | 0.30 | 0.08 |
| PassiveLurker | 0.50 | 0.50 | 0.10 | 0.05 | 0.12 |

**ShortSeller inverse resistance rule** (passed as `override_fn` to `ResistanceUpdater`):
```python
# When social_signal opposes current_opinion and |social_signal| > 0.6:
effective_resistance *= 1.3
```

### 4.2 Seed Enricher (`seed_enricher.py`)

- Input: ticker symbol + 8-K filing text (via `sec-edgar-downloader`)
- Event type classification: keyword-match first (earnings_miss/beat, ceo_change, regulatory, m_and_a, macro), LLM fallback for ambiguous cases
- Financial context: sector, market cap tier, recent EPS trend via `yfinance`
- Optional: `FirecrawlEnricher` for related news articles

### 4.3 Ground Truth (`ground_truth.py`)

StockTwits public sentiment stream is no longer reliably available. Replacement sources:

- **Reddit Finance sentiment**: `r/wallstreetbets`, `r/investing` post/comment sentiment via Reddit API, window `[filing_date, filing_date + 72h]`
- **Price series**: `yfinance` OHLCV for same window
- **Options flow**: Unusual Whales API (optional, enriches ground truth signal)

```python
@dataclass
class GroundTruthRecord:
    sentiment_series: list[float]       # Reddit sentiment, hourly buckets
    price_series: list[float]           # yfinance close prices
    price_change_pct: float             # filing_date → filing_date+72h
```

### 4.4 Scoring (`config.py`)

```python
def score(result, truth) -> BacktestResult:
    direction_match = sign(result.trajectory[-1]) == sign(truth.sentiment_series[-1])
    magnitude_correlation = pearsonr(result.trajectory, truth.sentiment_series)
    price_direction_match = sign(result.trajectory[-1]) == sign(truth.price_change_pct)
    return BacktestResult(
        direction_match=direction_match,
        magnitude_correlation=magnitude_correlation,
        domain_metric={
            "price_direction_match": price_direction_match,
            "price_change_pct": truth.price_change_pct,
        },
        ...
    )
```

---

## 5. Coding Domain (`lightningfish_coding/`)

### 5.1 Personas (`personas.py`)

Parameters are first-pass estimates pending validation against real PR dataset. Unlike finance, these are not literature-grounded — flag prominently in calibration reports.

| Archetype | resistance | recency | contrarian | influence | proportion |
|---|---|---|---|---|---|
| SecurityReviewer | 0.80 | 0.20 | 0.60 | 0.75 | 0.10 |
| PerformanceReviewer | 0.70 | 0.30 | 0.40 | 0.55 | 0.10 |
| StyleMaintainability | 0.40 | 0.50 | 0.20 | 0.35 | 0.20 |
| DomainExpertMaintainer | 0.85 | 0.15 | 0.50 | 0.90 | 0.08 |
| JuniorContributor | 0.20 | 0.80 | 0.05 | 0.15 | 0.40 |
| CIBot | — | — | — | 0.50 | 0.12 |

**CIBot** is a `RuleBasedAgent`. Its opinion is `test_pass_rate` mapped to `[-1, 1]`. It never calls the LLM and is always routed to tier 2 by `TierRouter`.

### 5.2 Seed Enricher (`seed_enricher.py`)

- Input: GitHub PR URL
- Enrichment via GitHub REST API:
  - `diff_size_tier`: xs/s/m/l/xl by lines changed
  - `languages_touched`: parsed from file extensions
  - `is_test_included`: checks for test file patterns in changed files
  - `author_pr_history`: count of prior merged PRs by this author
  - `linked_issue`: fetches linked issue text if referenced in PR body

### 5.3 Ground Truth (`ground_truth.py`)

```python
@dataclass
class GroundTruthRecord:
    comment_count: int
    approval_sequence: list[str]        # COMMENTED / APPROVED / CHANGES_REQUESTED
    merged: bool
```

Fetched via GitHub REST API: `GET /repos/{owner}/{repo}/pulls/{pull_number}/reviews`

### 5.4 Scoring (`config.py`)

```python
def score(result, truth) -> BacktestResult:
    simulated_consensus = "approve" if result.trajectory[-1] > 0 else "reject"
    outcome_match = (simulated_consensus == "approve") == truth.merged
    # comment_volume_correlation: active_agent_count vs truth.comment_count
    # both should scale with diff complexity if personas are calibrated
    return BacktestResult(
        direction_match=outcome_match,
        domain_metric={
            "outcome_match": outcome_match,
            "simulated_consensus": simulated_consensus,
            "actual_merged": truth.merged,
            # ratio of active_agent_count to truth.comment_count, normalised by n_agents
            # expected to be > 0.5 and < 2.0 for well-calibrated personas
            "comment_volume_ratio": len(result.round_events[-1].active_agent_ids) / max(truth.comment_count, 1),
        },
        ...
    )
```

---

## 6. Frontend (`lightningfish_web/`)

### 6.1 Tech Stack

- Next.js 15 App Router, TypeScript
- Tailwind CSS + shadcn/ui (neutral palette)
- Recharts for opinion distribution histogram and trajectory line chart
- SSE via browser `EventSource` API
- Clerk for auth and API key management
- Vercel Blob for PDF/JSON export

### 6.2 Pages

| Route | Purpose |
|---|---|
| `/` | Landing, domain selector |
| `/simulate/[domain]` | Seed input form, run button, simulation parameters (n_agents: 100-1000, n_rounds: 6-20, preset: fast/balanced/thorough) |
| `/simulate/[id]/live` | Live round viewer (SSE) |
| `/report/[id]` | Full report, agent chat, export |
| `/history` | Past simulations, comparison |
| `/backtest/[domain]` | Batch backtest runner |
| `/dev/keys` | API key management |

Simulation parameters exposed in UI: `n_agents` (default 500), `n_rounds` (default 12), and a preset selector (fast = 100 agents / 6 rounds, balanced = 500 / 12, thorough = 1000 / 20). Cost estimate updates live as parameters change before the user submits.

### 6.3 Live Round Viewer

Each `RoundEvent` SSE message updates:
- Opinion distribution histogram (Bearish / Neutral / Bullish bands)
- Mean opinion and diversity (stddev) readout
- Tier 1 agent list for current round with excerpt of their reasoning
- Running cost meter
- Diversity warning if `stddev < 0.25` (herd collapse risk)

---

## 7. Done Criteria

These are automated checks run in CI and reported in the calibration report for both domains.

1. `lightningfish_core/` passes grep audit: zero occurrences of finance- or coding-specific strings
2. `tier1_calls / total_agents <= 0.10` enforced per round in both domains
3. Backtest dataset: >= 30 seed events per domain
4. Finance: `direction_accuracy > 0.55` on held-out 10 events (beat-random threshold, reported honestly)
5. Coding: `outcome_accuracy > 0.55` on held-out 10 events
6. `stddev(final_opinions) > 0.25` at simulation end in both domains
7. Side-by-side calibration report: both domains, same format, includes written hypothesis on accuracy differential

---

## 8. Project Structure

```
lightningfish/
  lightningfish_core/
    adapter.py          DomainAdapter ABC
    enricher.py         EnricherPlugin ABC
    registry.py         Entry-point auto-discovery
    models.py           All shared dataclasses
    engine.py           OASIS wrapper, round runner
    tier_router.py      Two-tier active/follower split
    resistance.py       Resistance update math + override hook
    rule_agent.py       RuleBasedAgent base class
    backtest_base.py    BacktestHarness ABC

  lightningfish_finance/
    __init__.py         Registers FinanceDomainAdapter
    personas.py         7 investor archetypes
    seed_enricher.py    8-K filing -> EnrichedSeed
    ground_truth.py     Reddit + yfinance ground truth
    config.py           FinanceDomainAdapter implementation
    run_backtest.py     CLI backtest runner

  lightningfish_coding/
    __init__.py         Registers CodingDomainAdapter
    personas.py         6 reviewer archetypes + CIBot
    seed_enricher.py    PR diff -> EnrichedSeed
    ground_truth.py     GitHub REST API ground truth
    config.py           CodingDomainAdapter implementation
    run_backtest.py     CLI backtest runner

  lightningfish_web/
    app/                Next.js App Router pages
    components/         Shared UI components
    lib/                API client, SSE utilities

  lightningfish_service/
    main.py             FastAPI app (Modal deployment)
    routes/             /enrich, /simulate, /chat, /backtest

  docs/
    superpowers/specs/  Design specs
  
  pyproject.toml        Entry-point declarations for both domains
```

---

## 9. Dependencies

```
# Python simulation service
camel-oasis
anthropic
fastapi
pydantic-settings
structlog
scipy
networkx
yfinance
sec-edgar-downloader
requests
firecrawl-py
yt-dlp
modal

# Web
next@15
@clerk/nextjs
tailwindcss
shadcn/ui
recharts
```

---

## 10. What Is Explicitly Out of Scope

- Any domain-specific logic in `lightningfish_core/`
- StockTwits (API unavailable — replaced with Reddit Finance)
- Real-time financial data feeds or trading integration
- Self-hosted LLM inference
- Mobile app
