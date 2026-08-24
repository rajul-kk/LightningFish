# Lightningfish

Lightningfish simulates how a population of differently-minded people would argue about something (a stock ticker, a GitHub PR, a Hacker News link) using calibrated AI personas that read, react, and try to persuade each other round by round.

**This is a deliberation simulator, not a forecaster.** Every domain has been backtested against real settled outcomes wherever that's possible, and the results are reported honestly, including every place the simulation loses to a naive heuristic. See [METHODOLOGY.md](METHODOLOGY.md) for the validation protocol and a results summary per domain. What the engine is actually good for: watching a structured, multi-perspective argument unfold, where a skeptic pushes back, how fast consensus forms (or doesn't), and what the strongest case on each side sounds like.

Built from scratch, inspired by [OASIS](https://github.com/camel-ai/oasis) and MiroFish.

---

## Architecture

```
lightningfish_core/       Domain-agnostic engine (models, SimulationEngine, TierRouter, registry)
lightningfish_finance/    7 investor archetypes + SEC EDGAR seed enricher + Reddit ground truth
lightningfish_coding/     6 reviewer archetypes + CIBot + GitHub PR seed enricher
lightningfish_hn/         6 HN archetypes + Algolia seed enricher + points/comments ground truth
lightningfish_service/    FastAPI service (runs locally or on Modal)
lightningfish_web/        Next.js 15 frontend (deploys to Vercel)
```

Three-tier simulation each round: **T1 originators** (~10%, highest influence) have the LLM write a structured post; **T2 reactors** (~20%, undecided) have the LLM re-evaluate after reading their feed; **T3 drifters** (the rest) update through deterministic herding math. Only ~30% of agents call the LLM per round, keeping cost low while preserving social dynamics.

---

## Running locally

### 1. Python service

**Install dependencies**

```bash
pip install fastapi uvicorn anthropic psycopg2-binary praw yfinance \
            sec-edgar-downloader requests scipy
```

**Set environment variables**: copy `.env.example` to `.env` and fill in values:

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

**Set environment variables**: copy `.env.local.example` to `.env.local`:

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up

PYTHON_SERVICE_URL=http://localhost:8000
NEXT_PUBLIC_PYTHON_SERVICE_URL=http://localhost:8000
```

Clerk keys come from [clerk.com](https://clerk.com); free tier is fine.

> **Skip Clerk for quick testing**: comment out the body of `middleware.ts` and set `user_id: "dev"` in the simulate form. The Python service accepts any user_id string.

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
[METHODOLOGY.md](METHODOLOGY.md) for the validation protocol and why the
single-LLM-call rung is the one that matters.

```bash
# Coding: class-balanced closed PRs from a public repo (tokenless works; a
# GITHUB_TOKEN raises the rate limit from 60 to 5000 req/hr)
python -m tests.integration.run_backtest coding pallets flask 20

# Finance: (ticker, date, headline) events scored against the price move
python -m tests.integration.run_backtest finance

# Hacker News: class-balanced settled stories, scored on both points and
# num_comments (tokenless works; free 10,000 req/hr, no GITHUB_TOKEN needed)
python -m tests.integration.run_backtest hn 20

# Hacker News + first 2h of community reaction, on the SAME stories as the
# run above (paired). Adds an early-engagement rung to the baseline ladder.
python -m tests.integration.run_backtest hn-early

# Calibrate engine params against backtest accuracy
python -m tests.integration.run_calibration pallets flask 20
```

**No GPU?** Two Kaggle notebooks run these on a free T4: the model sits in VRAM
instead of thrashing a CPU box, turning hours into minutes. Upload via Kaggle →
Create → Notebook → File → Import Notebook.

| Notebook | Runs |
|---|---|
| [`kaggle_backtest.ipynb`](kaggle_backtest.ipynb) | the reception backtests (submission-only → paired early-comments → blind subgroup), plus a large-n scaling section |
| [`kaggle_controversy.ipynb`](kaggle_controversy.ipynb) | the controversy axis: scores whether the simulated crowd *splits*, the one output a single model call doesn't produce |

Cheap local runs: prefix with `LIGHTNINGFISH_MODEL=ollama:qwen2.5:7b` (llama3.2
3B is too weak, it drops the structured format) and shrink the sim with
`LIGHTNINGFISH_N_AGENTS` / `LIGHTNINGFISH_N_ROUNDS`. Watch the `low_confidence`
flag: a run dominated by parse failures isn't trustworthy regardless of model.

Ground truth (and, for coding, the pulled PR list) is cached to
`.cache/lightningfish/` so repeated runs against the same events don't re-spend
API rate limit; set `LIGHTNINGFISH_NO_CACHE=1` to force a fresh pull. Once a
repo is cached, two offline diagnostics need no further network calls:

```bash
# Per-archetype opinion breakdown on each cached event
python -m tests.integration.run_archetype_breakdown coding pallets flask
python -m tests.integration.run_archetype_breakdown hn

# Does a different archetype population mix change accuracy?
python -m tests.integration.run_population_sweep coding pallets flask
python -m tests.integration.run_population_sweep hn
```

---

## Tests

```bash
python -m pytest -q          # 202 tests, ~20s
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
| CIBot | 12% | Deterministic, CI pass rate only, no LLM |
| DomainExpertMaintainer | 8% | Highest influence, domain ownership |

All proportions are configurable in the simulation form.

### Hacker News

| Archetype | Default % | Character |
|---|---|---|
| CasualLurkerVoter | 30% | Low-conviction upvoter, moderate herding |
| EarlyAdopterHypeBeast | 18% | Low resistance, high recency bias, amplifies |
| ContrarianSkeptic | 15% | High resistance, contrarian, anti-herds |
| DomainExpertPedant | 15% | High resistance and influence, technical focus |
| GreybeardCynic | 12% | Highest resistance, strongly contrarian, anti-herds |
| ShowHNFounder | 10% | Low resistance, high recency bias, amplifies |

---

## Models

| Model | Input | Output | Use when |
|---|---|---|---|
| Haiku 4.5 | $1/M | $5/M | Fast iteration, cost control |
| Sonnet 5 | $3/M | $15/M | Default, balanced |
| Opus 5 | $5/M | $25/M | Highest reasoning quality |
| Ollama (local) | $0 | $0 | Free local testing via `ollama:<model>` |

Typical cost per simulation (300 agents, 10 rounds, Sonnet): ~$0.05.

Select a model with `LIGHTNINGFISH_MODEL` (CLIs) or the `model` argument
(`SimulationEngine`). `ollama:llama3.2` routes to a local Ollama server at no
cost, good for plumbing checks, but small models drop the structured output
format often and produce muted signals (see the `parse_success_rate` /
`low_confidence` fields).
