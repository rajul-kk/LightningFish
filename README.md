# Lightningfish

Multi-agent opinion simulation engine with a live streaming web interface. Paste a stock ticker/SEC filing or GitHub PR URL, configure a population of calibrated agent archetypes, and watch them form consensus round by round.

Built from scratch, inspired by [OASIS](https://github.com/camel-ai/oasis) and MiroFish.

---

## Architecture

```
lightningfish_core/       Domain-agnostic engine (models, SimulationEngine, TierRouter, registry)
lightningfish_finance/    7 investor archetypes + SEC EDGAR seed enricher + Reddit ground truth
lightningfish_coding/     6 reviewer archetypes + CIBot + GitHub PR seed enricher
lightningfish_service/    FastAPI service (runs locally or on Modal)
lightningfish_web/        Next.js 15 frontend (deploys to Vercel)
```

Three-tier simulation each round: **T1 originators** (~10%, highest influence) have the LLM write a structured post; **T2 reactors** (~20%, undecided) have the LLM re-evaluate after reading their feed; **T3 drifters** (the rest) update through deterministic herding math. Only ~30% of agents call the LLM per round, keeping cost low while preserving social dynamics.

**For the full mechanics — opinion-update formulas, metrics, validation, and calibration — see [ARCHITECTURE.md](ARCHITECTURE.md).**

---

## Running locally

### 1. Python service

**Install dependencies**

```bash
pip install fastapi uvicorn anthropic psycopg2-binary praw yfinance \
            sec-edgar-downloader requests scipy
```

**Set environment variables** — copy `.env.example` to `.env` and fill in values:

```
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://user:pass@host/db    # Neon free tier works
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=lightningfish/0.1
GITHUB_TOKEN=ghp_...
SEC_EDGAR_USER_AGENT=YourName yourname@example.com
```

Minimum required for simulations: `ANTHROPIC_API_KEY` + `DATABASE_URL`.  
Reddit/GitHub/SEC keys are only needed when those enrichers run.

**Create the database schema** (once)

```bash
python -m lightningfish_service.migrate
python -m lightningfish_service.migrate_v2   # adds model + agent_config columns
```

**Start the service**

```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-... && set DATABASE_URL=postgresql://... && uvicorn lightningfish_service.main:app --reload --port 8000

# macOS / Linux
source .env && uvicorn lightningfish_service.main:app --reload --port 8000
```

Service runs at `http://localhost:8000`. Interactive API docs at `http://localhost:8000/docs`.

---

### 2. Next.js frontend

**Install dependencies**

```bash
cd lightningfish_web
npm install
```

**Set environment variables** — copy `.env.local.example` to `.env.local`:

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up

PYTHON_SERVICE_URL=http://localhost:8000
NEXT_PUBLIC_PYTHON_SERVICE_URL=http://localhost:8000
```

Clerk keys come from [clerk.com](https://clerk.com) — free tier is fine.

> **Skip Clerk for quick testing** — comment out the body of `middleware.ts` and set `user_id: "dev"` in the simulate form. The Python service accepts any user_id string.

**Start the frontend**

```bash
npm run dev
```

App runs at `http://localhost:3000`.

---

## Deployment

### Python service → Modal

```bash
pip install modal
modal setup                          # authenticate once

# Create secret with all env vars
modal secret create lightningfish-secrets \
  ANTHROPIC_API_KEY=... \
  DATABASE_URL=... \
  REDDIT_CLIENT_ID=... \
  REDDIT_CLIENT_SECRET=... \
  REDDIT_USER_AGENT=... \
  GITHUB_TOKEN=... \
  SEC_EDGAR_USER_AGENT=... \
  ALLOWED_ORIGINS=https://your-app.vercel.app

modal deploy lightningfish_service/modal_app.py
```

Modal gives you a URL like `https://yourname--lightningfish-service-fastapi-app.modal.run`.

### Next.js frontend → Vercel

```bash
cd lightningfish_web
npx vercel --prod
```

Set environment variables in the Vercel dashboard:
- All `CLERK_*` and `NEXT_PUBLIC_CLERK_*` keys
- `PYTHON_SERVICE_URL` and `NEXT_PUBLIC_PYTHON_SERVICE_URL` pointing to your Modal URL

---

## Running backtests

Backtests pull real data and score the simulation's predicted direction against
actual outcomes, alongside a naive baseline, a single-LLM-call baseline, and a
majority-class reference, with a binomial significance test. See
[ARCHITECTURE.md §4](ARCHITECTURE.md) for methodology.

```bash
# Coding — class-balanced closed PRs from a public repo (tokenless works; a
# GITHUB_TOKEN raises the rate limit from 60 to 5000 req/hr)
python -m tests.integration.run_backtest coding pallets flask 20

# Finance — (ticker, date, headline) events scored against the price move
python -m tests.integration.run_backtest finance

# Hacker News — class-balanced settled stories, scored on both points and
# num_comments (tokenless works; free 10,000 req/hr, no GITHUB_TOKEN needed)
python -m tests.integration.run_backtest hn 20

# Calibrate engine params against backtest accuracy
python -m tests.integration.run_calibration pallets flask 20
```

Cheap local runs: prefix with `LIGHTNINGFISH_MODEL=ollama:qwen2.5:7b` (llama3.2
3B is too weak — drops the structured format) and shrink the sim with
`LIGHTNINGFISH_N_AGENTS` / `LIGHTNINGFISH_N_ROUNDS`. Watch the `low_confidence`
flag — a run dominated by parse failures isn't trustworthy regardless of model.

Ground truth (and, for coding, the pulled PR list) is cached to
`.cache/lightningfish/` so repeated runs against the same events don't re-spend
API rate limit — set `LIGHTNINGFISH_NO_CACHE=1` to force a fresh pull. Once a
repo is cached, two offline diagnostics need no further network calls:

```bash
# Per-archetype opinion breakdown on each cached PR
python -m tests.integration.run_archetype_breakdown pallets flask

# Does a different archetype population mix change accuracy?
python -m tests.integration.run_population_sweep pallets flask
```

---

## Tests

```bash
python -m pytest -q          # 157 tests, ~7s
```

---

## Agent archetypes

### Finance

| Archetype | Default % | Character |
|---|---|---|
| RetailFOMO | 35% | Herding, high recency bias |
| MomentumTrader | 18% | Trend follower, reactive |
| ValueInvestor | 12% | Anchored to fundamentals |
| PassiveLurker | 12% | Low influence, slow drift |
| InstitutionalAnalyst | 10% | High influence, balanced |
| MacroTourist | 8% | Top-down macro lens |
| ShortSeller | 5% | Contrarian; digs in when consensus rises |

### Code review

| Archetype | Default % | Character |
|---|---|---|
| JuniorContributor | 40% | Deferential, follows senior signals |
| StyleMaintainability | 20% | Readability and consistency focused |
| SecurityReviewer | 10% | Blocks on security issues, high conviction |
| PerformanceReviewer | 10% | Runtime and memory impact |
| CIBot | 12% | Deterministic — CI pass rate only, no LLM |
| DomainExpertMaintainer | 8% | Highest influence, domain ownership |

All proportions are configurable in the simulation form.

---

## Models

| Model | Input | Output | Use when |
|---|---|---|---|
| Haiku 4.5 | $0.80/M | $4/M | Fast iteration, cost control |
| Sonnet 4.6 | $3/M | $15/M | Default — balanced |
| Opus 4.8 | $15/M | $75/M | Highest reasoning quality |
| Ollama (local) | $0 | $0 | Free local testing via `ollama:<model>` |

Typical cost per simulation (300 agents, 10 rounds, Sonnet): ~$0.05.

Select a model with `LIGHTNINGFISH_MODEL` (CLIs) or the `model` argument
(`SimulationEngine`). `ollama:llama3.2` routes to a local Ollama server at no
cost — good for plumbing checks, but small models drop the structured output
format often and produce muted signals (see the `parse_success_rate` /
`low_confidence` fields).
