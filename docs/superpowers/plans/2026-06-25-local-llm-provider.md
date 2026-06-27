# Local LLM Provider (GPU/CPU) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local LLM inference (Ollama / any OpenAI-compatible server) as an alternative to Anthropic's cloud API, with GPU/CPU status detection and a frontend toggle.

**Architecture:** A new `LLMProvider` protocol in `lightningfish_core/llm_provider.py` wraps both the Anthropic SDK and an `openai`-compatible HTTP client. `SimulationEngine` and the chat route pick the right provider based on the model string prefix (`ollama:*` → local, otherwise → Anthropic). A new `/local/status` endpoint probes Ollama for availability and GPU usage. The frontend adds a collapsible "Run on your own GPU / CPU" section to the simulate page with endpoint, model quick-picks, and a GPU/CPU badge.

**Tech Stack:** `openai>=1.0` (OpenAI-compatible client targeting Ollama), `anthropic>=0.50` (unchanged), `httpx>=0.27` (already available via FastAPI), Next.js `fetch` for the status probe.

## Global Constraints

- Python 3.10: `from __future__ import annotations` at the top of every new `.py` file
- No new DB column without a matching migration file
- `base_url` for local provider defaults to `http://localhost:11434/v1`
- Local models report `total_cost_usd = 0.0` — zero API cost
- `openai>=1.0` package convention: `openai.OpenAI(base_url=..., api_key="local")`
- Add `"openai>=1.0"` to Modal image `pip_install` list in `lightningfish_service/modal_app.py`
- All tests pass: `pytest -x` must be green after every task

---

### Task 1: `LLMProvider` abstraction — `AnthropicProvider` + `LocalProvider` + factory

**Files:**
- Create: `lightningfish_core/llm_provider.py`
- Test: `tests/core/test_llm_provider.py`

**Interfaces:**
- Produces:
  - `LLMProvider` Protocol with `get_opinion(system: str, user_msg: str, model: str) -> tuple[float, float]`
  - `AnthropicProvider(client: Anthropic)` — wraps `client.messages.create()`
  - `LocalProvider(base_url: str)` — wraps `openai.OpenAI(base_url=...).chat.completions.create()`
  - `make_provider(model: str, base_url: str | None = None) -> LLMProvider` — factory used by the engine and routes

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_llm_provider.py`:

```python
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch


def _mock_anthropic_client(text: str = "0.4", input_tokens: int = 100, output_tokens: int = 5):
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    client.messages.create.return_value = response
    return client


def _mock_openai_client(text: str = "0.3"):
    client = MagicMock()
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(content=text))]
    client.chat.completions.create.return_value = completion
    return client


def test_anthropic_provider_returns_opinion_and_positive_cost():
    from lightningfish_core.llm_provider import AnthropicProvider
    client = _mock_anthropic_client("0.6")
    provider = AnthropicProvider(client)
    opinion, cost = provider.get_opinion("sys", "user", "claude-sonnet-4-6")
    assert opinion == pytest.approx(0.6)
    assert cost > 0.0


def test_anthropic_provider_clamps_out_of_range():
    from lightningfish_core.llm_provider import AnthropicProvider
    client = _mock_anthropic_client("5.0")
    provider = AnthropicProvider(client)
    opinion, _ = provider.get_opinion("sys", "user", "claude-sonnet-4-6")
    assert opinion == pytest.approx(1.0)


def test_anthropic_provider_handles_bad_text():
    from lightningfish_core.llm_provider import AnthropicProvider
    client = _mock_anthropic_client("not_a_number")
    provider = AnthropicProvider(client)
    opinion, _ = provider.get_opinion("sys", "user", "claude-sonnet-4-6")
    assert opinion == pytest.approx(0.0)


def test_local_provider_returns_zero_cost():
    from lightningfish_core.llm_provider import LocalProvider
    with patch("lightningfish_core.llm_provider.openai.OpenAI") as mock_cls:
        mock_cls.return_value = _mock_openai_client("0.3")
        provider = LocalProvider("http://localhost:11434/v1")
    opinion, cost = provider.get_opinion("sys", "user", "ollama:llama3.2")
    assert opinion == pytest.approx(0.3)
    assert cost == pytest.approx(0.0)


def test_local_provider_strips_ollama_prefix():
    from lightningfish_core.llm_provider import LocalProvider
    with patch("lightningfish_core.llm_provider.openai.OpenAI") as mock_cls:
        mock_instance = _mock_openai_client("0.1")
        mock_cls.return_value = mock_instance
        provider = LocalProvider("http://localhost:11434/v1")
    provider.get_opinion("sys", "user", "ollama:mistral")
    call_kwargs = mock_instance.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "mistral"


def test_make_provider_returns_anthropic_for_claude_model():
    from lightningfish_core.llm_provider import AnthropicProvider, make_provider
    with patch("lightningfish_core.llm_provider.Anthropic"):
        p = make_provider("claude-sonnet-4-6")
    assert isinstance(p, AnthropicProvider)


def test_make_provider_returns_local_for_ollama_prefix():
    from lightningfish_core.llm_provider import LocalProvider, make_provider
    with patch("lightningfish_core.llm_provider.openai.OpenAI"):
        p = make_provider("ollama:llama3.2")
    assert isinstance(p, LocalProvider)


def test_make_provider_returns_local_when_base_url_provided():
    from lightningfish_core.llm_provider import LocalProvider, make_provider
    with patch("lightningfish_core.llm_provider.openai.OpenAI"):
        p = make_provider("claude-sonnet-4-6", base_url="http://192.168.1.10:11434/v1")
    assert isinstance(p, LocalProvider)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_llm_provider.py -v`
Expected: `ModuleNotFoundError: No module named 'lightningfish_core.llm_provider'`

- [ ] **Step 3: Create `lightningfish_core/llm_provider.py`**

```python
from __future__ import annotations
from typing import Protocol, runtime_checkable
from anthropic import Anthropic
import openai

_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (0.8e-6,  4e-6),
    "claude-sonnet-4-6":         (3e-6,   15e-6),
    "claude-opus-4-8":           (15e-6,  75e-6),
}
_DEFAULT_COSTS = (3e-6, 15e-6)
_LOCAL_BASE_URL = "http://localhost:11434/v1"


@runtime_checkable
class LLMProvider(Protocol):
    def get_opinion(self, system: str, user_msg: str, model: str) -> tuple[float, float]:
        """Return (opinion in [-1, 1], cost_usd >= 0)."""
        ...


class AnthropicProvider:
    def __init__(self, client: Anthropic) -> None:
        self._client = client

    def get_opinion(self, system: str, user_msg: str, model: str) -> tuple[float, float]:
        response = self._client.messages.create(
            model=model,
            max_tokens=16,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = response.content[0].text.strip()
        try:
            opinion = max(-1.0, min(1.0, float(text)))
        except ValueError:
            opinion = 0.0
        in_cost, out_cost = _MODEL_COSTS.get(model, _DEFAULT_COSTS)
        cost = response.usage.input_tokens * in_cost + response.usage.output_tokens * out_cost
        return opinion, cost


class LocalProvider:
    """OpenAI-compatible local inference — Ollama, llama.cpp, vLLM, etc."""

    def __init__(self, base_url: str = _LOCAL_BASE_URL) -> None:
        self._client = openai.OpenAI(base_url=base_url, api_key="local")

    def get_opinion(self, system: str, user_msg: str, model: str) -> tuple[float, float]:
        # Ollama expects bare model names, not the "ollama:" prefix
        bare_model = model.split(":", 1)[-1] if ":" in model else model
        response = self._client.chat.completions.create(
            model=bare_model,
            max_tokens=16,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        try:
            opinion = max(-1.0, min(1.0, float(text)))
        except ValueError:
            opinion = 0.0
        return opinion, 0.0  # local inference: zero API cost


def make_provider(model: str, base_url: str | None = None) -> LLMProvider:
    """Return AnthropicProvider for Claude models, LocalProvider otherwise."""
    if model.startswith("ollama:") or base_url is not None:
        return LocalProvider(base_url=base_url or _LOCAL_BASE_URL)
    return AnthropicProvider(Anthropic())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_llm_provider.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add lightningfish_core/llm_provider.py tests/core/test_llm_provider.py
git commit -m "feat: add LLMProvider abstraction with Anthropic + Local (Ollama) implementations"
```

---

### Task 2: Wire `SimulationEngine` to `LLMProvider`

**Files:**
- Modify: `lightningfish_core/engine.py`
- Modify: `tests/core/test_engine.py`

**Interfaces:**
- Consumes: `make_provider(model, base_url) -> LLMProvider` from Task 1
- Produces: `SimulationEngine(adapter, model="claude-sonnet-4-6", base_url=None)` — same public API, no regressions

- [ ] **Step 1: Write failing test for local model in engine**

Add to `tests/core/test_engine.py`:

```python
def test_engine_uses_local_provider_for_ollama_model():
    """Engine with ollama: model should use LocalProvider — no Anthropic calls, zero cost."""
    agents = [_persona(0.9 if i < 2 else 0.3) for i in range(20)]
    with patch("lightningfish_core.llm_provider.openai.OpenAI") as mock_cls:
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="0.3"))]
        mock_cls.return_value.chat.completions.create.return_value = mock_completion
        engine = SimulationEngine(
            StubAdapter(), model="ollama:llama3.2", base_url="http://localhost:11434/v1"
        )
        result = engine.run(_seed(), agents, n_rounds=2)
    assert result.total_cost_usd == pytest.approx(0.0)
    assert len(result.trajectory) == 2
```

Also add `import pytest` to the existing imports in `tests/core/test_engine.py` if not already present.

- [ ] **Step 2: Run to confirm test fails**

Run: `pytest tests/core/test_engine.py::test_engine_uses_local_provider_for_ollama_model -v`
Expected: FAIL — `SimulationEngine.__init__()` got unexpected keyword argument `base_url`

- [ ] **Step 3: Rewrite `lightningfish_core/engine.py`**

Replace the entire file content:

```python
from __future__ import annotations
import statistics
from .models import AgentPersona, EnrichedSeed, RoundEvent, SimulationResult
from .adapter import DomainAdapter
from .tier_router import TierRouter
from .resistance import compute_effective_resistance
from .rule_agent import RuleBasedAgent
from .llm_provider import LLMProvider, make_provider

_USER_MSG = (
    "Output your current opinion as a single float between -1.0 and 1.0. "
    "Output ONLY the number, nothing else."
)


class SimulationEngine:
    def __init__(
        self,
        adapter: DomainAdapter,
        model: str = "claude-sonnet-4-6",
        base_url: str | None = None,
    ) -> None:
        self.adapter = adapter
        self.model = model
        self.provider: LLMProvider = make_provider(model, base_url)
        self.router = TierRouter()

    def run_streaming(
        self,
        seed: EnrichedSeed,
        agents: list[AgentPersona],
        n_rounds: int,
    ):
        """
        Generator yielding RoundEvent per round.
        Returns SimulationResult as StopIteration.value when exhausted.
        """
        trajectory: list[float] = []
        round_events: list[RoundEvent] = []
        total_tier1_calls = 0
        total_cost_usd = 0.0

        for round_num in range(1, n_rounds + 1):
            tiers = self.router.route(agents)
            active = tiers["active"]
            followers = tiers["followers"]

            round_cost = 0.0
            for agent in active:
                opinion, cost = self._llm_opinion(seed, agent)
                agent.current_opinion = opinion
                round_cost += cost

            total_tier1_calls += len(active)
            total_cost_usd += round_cost

            neighbour_pull = (
                statistics.mean(a.current_opinion for a in active) if active else 0.0
            )
            recency_pull = trajectory[-1] if trajectory else 0.0

            for agent in followers:
                if isinstance(agent, RuleBasedAgent):
                    agent.current_opinion = agent.compute_opinion(seed)
                else:
                    effective_r = compute_effective_resistance(
                        agent,
                        social_signal=neighbour_pull,
                        override_fn=agent.metadata.get("resistance_override_fn"),
                    )
                    raw = (
                        agent.current_opinion * effective_r
                        + neighbour_pull * (1 - effective_r) * 0.6
                        + recency_pull * (1 - effective_r) * 0.4
                    )
                    agent.current_opinion = max(-1.0, min(1.0, raw))

            opinions = [a.current_opinion for a in agents]
            mean_op = statistics.mean(opinions)
            stddev_op = statistics.stdev(opinions) if len(opinions) > 1 else 0.0
            trajectory.append(mean_op)

            event = RoundEvent(
                round_number=round_num,
                opinion_distribution=opinions,
                mean_opinion=mean_op,
                stddev_opinion=stddev_op,
                tier1_calls=len(active),
                active_agent_ids=[a.unique_id for a in active],
                estimated_cost_usd=round_cost,
            )
            round_events.append(event)
            yield event

        return SimulationResult(
            seed=seed,
            trajectory=trajectory,
            round_events=round_events,
            final_distribution=[a.current_opinion for a in agents],
            total_tier1_calls=total_tier1_calls,
            total_cost_usd=total_cost_usd,
        )

    def run(
        self,
        seed: EnrichedSeed,
        agents: list[AgentPersona],
        n_rounds: int,
    ) -> SimulationResult:
        gen = self.run_streaming(seed, agents, n_rounds)
        try:
            while True:
                next(gen)
        except StopIteration as e:
            return e.value

    def _llm_opinion(self, seed: EnrichedSeed, agent: AgentPersona) -> tuple[float, float]:
        system = self.adapter.agent_system_prompt(seed, agent)
        return self.provider.get_opinion(system, _USER_MSG, self.model)
```

- [ ] **Step 4: Update patch targets in existing engine tests**

The existing tests patch `lightningfish_core.engine.Anthropic`, but Anthropic is now only imported in `llm_provider.py`. Update every `patch("lightningfish_core.engine.Anthropic")` to `patch("lightningfish_core.llm_provider.Anthropic")`.

There are four such occurrences in `tests/core/test_engine.py`:
- `test_engine_returns_simulation_result`
- `test_tier1_calls_capped`
- `test_opinions_clamped`
- `test_backtest_harness_raises_when_no_ground_truth`

Each looks like:
```python
# Before:
with patch("lightningfish_core.engine.Anthropic") as mock_cls:
    mock_cls.return_value = _mock_anthropic()

# After:
with patch("lightningfish_core.llm_provider.Anthropic") as mock_cls:
    mock_cls.return_value = _mock_anthropic()
```

- [ ] **Step 5: Run all engine tests**

Run: `pytest tests/core/test_engine.py -v`
Expected: All 5 tests PASS (4 original + 1 new)

- [ ] **Step 6: Run full test suite**

Run: `pytest -x`
Expected: All 54+ tests PASS

- [ ] **Step 7: Commit**

```bash
git add lightningfish_core/engine.py tests/core/test_engine.py
git commit -m "refactor: engine delegates LLM calls to LLMProvider; adds base_url param"
```

---

### Task 3: Service — DB column + route plumbing for `base_url`

**Files:**
- Create: `lightningfish_service/migrate_v3.py`
- Modify: `lightningfish_service/db.py`
- Modify: `lightningfish_service/routes/simulate.py`
- Modify: `lightningfish_service/routes/chat.py`
- Modify: `lightningfish_service/modal_app.py`

**Interfaces:**
- Consumes: `SimulationEngine(adapter, model, base_url)` from Task 2; `make_provider(model, base_url)` from Task 1
- Produces: `POST /simulate` accepts `base_url: str | None`; `GET /simulate/{id}` streams with local provider when `base_url` is set; `POST /chat/{id}` uses the sim's stored model and base_url

- [ ] **Step 1: Create `lightningfish_service/migrate_v3.py`**

```python
from __future__ import annotations
"""Add base_url column to simulations for local LLM support."""
import os
import psycopg2


_SQL = """
ALTER TABLE simulations ADD COLUMN IF NOT EXISTS base_url TEXT;
"""


def migrate() -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(_SQL)
        conn.commit()
    finally:
        conn.close()
    print("migrate_v3: base_url column added")


if __name__ == "__main__":
    migrate()
```

- [ ] **Step 2: Update `create_simulation` in `lightningfish_service/db.py`**

Replace the `create_simulation` function (lines 27–49) with:

```python
def create_simulation(
    sim_id: str,
    user_id: str,
    domain_id: str,
    seed_json: dict,
    n_agents: int,
    n_rounds: int,
    model: str = "claude-sonnet-4-6",
    agent_config: dict | None = None,
    base_url: str | None = None,
) -> None:
    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO simulations
              (id, user_id, domain_id, status, seed_json, n_agents, n_rounds,
               model, agent_config_json, base_url)
            VALUES (%s, %s, %s, 'pending', %s, %s, %s, %s, %s, %s)
            """,
            (
                sim_id, user_id, domain_id, json.dumps(seed_json),
                n_agents, n_rounds, model,
                json.dumps(agent_config) if agent_config is not None else None,
                base_url,
            ),
        )
```

- [ ] **Step 3: Update `lightningfish_service/routes/simulate.py` — three changes**

**3a** — Add `base_url` field to `SimulateRequest`:
```python
class SimulateRequest(BaseModel):
    domain_id: str
    user_id: str
    raw_input: dict
    n_agents: int = 500
    n_rounds: int = 12
    model: str = "claude-sonnet-4-6"
    agent_config: dict[str, float] | None = None
    base_url: str | None = None
```

**3b** — Pass `base_url` in the `create()` handler where `create_simulation` is called:
```python
create_simulation(
    sim_id, req.user_id, req.domain_id, seed_dict,
    req.n_agents, req.n_rounds, req.model, req.agent_config, req.base_url,
)
```

**3c** — In `get_result()`, add `base_url` to the returned dict:
```python
return {
    "id": str(sim["id"]),
    "domain_id": sim["domain_id"],
    "status": sim["status"],
    "result_json": result_json,
    "cost_usd": float(sim.get("cost_usd") or 0),
    "n_agents": sim.get("n_agents"),
    "n_rounds": sim.get("n_rounds"),
    "model": sim.get("model") or "claude-sonnet-4-6",
    "base_url": sim.get("base_url"),
    "agent_config": (
        json.loads(sim["agent_config_json"])
        if isinstance(sim.get("agent_config_json"), str)
        else sim.get("agent_config_json")
    ),
    "seed_json": seed_json,
    "created_at": sim["created_at"].isoformat() if hasattr(sim["created_at"], "isoformat") else str(sim["created_at"]),
}
```

**3d** — In `stream()`, extract `base_url` and pass to engine. After the existing `agent_config` lines add:
```python
base_url: str | None = sim.get("base_url")
```
Then change the engine instantiation from:
```python
engine = SimulationEngine(adapter, model=model)
```
to:
```python
engine = SimulationEngine(adapter, model=model, base_url=base_url)
```

- [ ] **Step 4: Rewrite `lightningfish_service/routes/chat.py` to use provider factory**

Replace the entire file:

```python
from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from anthropic import Anthropic
import openai as _openai
from lightningfish_core.registry import registry
from ..db import get_simulation

router = APIRouter()


class ChatRequest(BaseModel):
    archetype: str
    message: str


@router.post("/{simulation_id}")
def chat(simulation_id: str, req: ChatRequest):
    """Answer a user question as a specific agent persona post-simulation."""
    sim = get_simulation(simulation_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if sim["status"] != "complete":
        raise HTTPException(status_code=409, detail="Simulation not yet complete")

    result_json = sim["result_json"]
    if isinstance(result_json, str):
        result_json = json.loads(result_json)

    trajectory: list[float] = result_json.get("trajectory", [])
    final_opinion = trajectory[-1] if trajectory else 0.0
    domain_id: str = result_json.get("domain_id", sim["domain_id"])
    seed_summary: str = result_json.get("seed_summary", "the event")
    model: str = sim.get("model") or "claude-sonnet-4-6"
    base_url: str | None = sim.get("base_url")

    adapter = registry.get(domain_id)
    negative_label, positive_label = adapter.opinion_labels if adapter else ("negative", "positive")
    opinion_description = (
        f"{abs(final_opinion):.2f} toward {positive_label}"
        if final_opinion >= 0
        else f"{abs(final_opinion):.2f} toward {negative_label}"
    )

    system = (
        f"You are a {req.archetype} who just participated in a multi-agent simulation "
        f"about: {seed_summary}. "
        f"Your final opinion score was {opinion_description} (scale: -1.0 to 1.0). "
        f"Answer the user's question while staying in character as this persona. "
        f"Be specific and opinionated. Keep your answer under 150 words."
    )

    if base_url is not None or model.startswith("ollama:"):
        bare = model.split(":", 1)[-1] if ":" in model else model
        client = _openai.OpenAI(
            base_url=base_url or "http://localhost:11434/v1", api_key="local"
        )
        resp = client.chat.completions.create(
            model=bare,
            max_tokens=256,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": req.message},
            ],
        )
        reply = (resp.choices[0].message.content or "").strip()
    else:
        client = Anthropic()
        resp = client.messages.create(
            model=model,
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": req.message}],
        )
        reply = resp.content[0].text.strip()

    return {"reply": reply}
```

- [ ] **Step 5: Add `openai>=1.0` to Modal image in `lightningfish_service/modal_app.py`**

In the `.pip_install(...)` call, add `"openai>=1.0"` after `"anthropic>=0.50"`:

```python
image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(
        "fastapi>=0.115",
        "uvicorn>=0.29",
        "anthropic>=0.50",
        "openai>=1.0",
        "psycopg2-binary>=2.9",
        "pydantic>=2.7",
        "scipy>=1.12",
        "yfinance>=0.2",
        "praw>=7.7",
        "requests>=2.31",
        "sec-edgar-downloader>=5.0",
        "PyGithub>=2.0",
    )
    .add_local_dir(".", remote_path="/app", ignore=["__pycache__", "*.pyc", ".git"])
)
```

- [ ] **Step 6: Run full test suite**

Run: `pytest -x`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add lightningfish_service/migrate_v3.py lightningfish_service/db.py \
  lightningfish_service/routes/simulate.py lightningfish_service/routes/chat.py \
  lightningfish_service/modal_app.py
git commit -m "feat: persist base_url through DB + service routes for local LLM"
```

---

### Task 4: `/local/status` probe endpoint (GPU/CPU detection)

**Files:**
- Create: `lightningfish_service/routes/local.py`
- Modify: `lightningfish_service/main.py`

**Interfaces:**
- Produces: `GET /local/status?base_url=<url>` → `{"available": bool, "gpu": bool | null, "models": list[str]}`

- [ ] **Step 1: Create `lightningfish_service/routes/local.py`**

```python
from __future__ import annotations
import httpx
from fastapi import APIRouter

router = APIRouter()

_DEFAULT_BASE_URL = "http://localhost:11434/v1"


@router.get("/status")
def local_status(base_url: str = _DEFAULT_BASE_URL) -> dict:
    """
    Probe an OpenAI-compatible local inference server.
    For Ollama, also queries /api/ps to detect GPU vs CPU usage.
    Returns: {available, gpu, models}
    """
    try:
        r = httpx.get(f"{base_url}/models", timeout=3.0)
        if r.status_code != 200:
            return {"available": False, "gpu": None, "models": []}
    except Exception:
        return {"available": False, "gpu": None, "models": []}

    data = r.json()
    models = [m["id"] for m in data.get("data", [])]

    # Ollama-specific GPU probe: /api/ps lives at the server root, not under /v1
    gpu: bool | None = None
    ollama_root = base_url.rstrip("/").removesuffix("/v1")
    try:
        ps = httpx.get(f"{ollama_root}/api/ps", timeout=3.0)
        if ps.status_code == 200:
            running = ps.json().get("models", [])
            if running:
                gpu = any(m.get("size_vram", 0) > 0 for m in running)
    except Exception:
        pass  # not Ollama or older version without /api/ps

    return {"available": True, "gpu": gpu, "models": models}
```

- [ ] **Step 2: Mount in `lightningfish_service/main.py`**

Add the import with the other route imports:
```python
from .routes import enrich, simulate, chat, backtest, keys, local
```

Add the router registration after the existing `include_router` calls:
```python
app.include_router(local.router, prefix="/local", tags=["local"])
```

- [ ] **Step 3: Smoke-test manually**

Start the service: `uvicorn lightningfish_service.main:app --reload --port 8000`

With no Ollama running:
```
curl http://localhost:8000/local/status
# Expected: {"available":false,"gpu":null,"models":[]}
```

With Ollama running (`ollama serve` + `ollama pull llama3.2`):
```
curl "http://localhost:8000/local/status?base_url=http%3A%2F%2Flocalhost%3A11434%2Fv1"
# Expected: {"available":true,"gpu":false,"models":["llama3.2:latest"]}
```

- [ ] **Step 4: Run full test suite**

Run: `pytest -x`
Expected: All tests PASS (no unit test for this route — it requires a live server)

- [ ] **Step 5: Commit**

```bash
git add lightningfish_service/routes/local.py lightningfish_service/main.py
git commit -m "feat: add /local/status endpoint to probe Ollama GPU/CPU availability"
```

---

### Task 5: Frontend — local model picker + GPU/CPU badge

**Files:**
- Modify: `lightningfish_web/lib/types.ts`
- Modify: `lightningfish_web/lib/api.ts`
- Modify: `lightningfish_web/app/simulate/[domain]/page.tsx`

**Interfaces:**
- Consumes: `GET /local/status?base_url=<url>` from Task 4
- Produces: `createSimulation` payload gains optional `base_url`; simulate page shows GPU/CPU badge

- [ ] **Step 1: Add local model types to `lightningfish_web/lib/types.ts`**

Add after the `MODELS` array (after line 79):

```typescript
export interface LocalStatus {
  available: boolean;
  gpu: boolean | null;
  models: string[];
}

export const LOCAL_POPULAR_MODELS = [
  "llama3.2",
  "llama3.1:8b",
  "mistral",
  "phi3",
  "gemma2:2b",
  "qwen2.5:7b",
] as const;

export const LOCAL_DEFAULT_BASE_URL = "http://localhost:11434/v1";
```

- [ ] **Step 2: Add `base_url` to `createSimulation` in `lightningfish_web/lib/api.ts`**

Replace the `createSimulation` function:

```typescript
export async function createSimulation(payload: {
  domain_id: string;
  user_id: string;
  raw_input: Record<string, unknown>;
  n_agents: number;
  n_rounds: number;
  model: string;
  agent_config: Record<string, number> | null;
  base_url?: string | null;
}): Promise<{ simulation_id: string }> {
  const res = await fetch(`${PY}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return json(res);
}
```

Also add a `probeLocalServer` helper at the end of the file:

```typescript
export async function probeLocalServer(baseUrl: string): Promise<{
  available: boolean;
  gpu: boolean | null;
  models: string[];
}> {
  const res = await fetch(
    `${PY}/local/status?base_url=${encodeURIComponent(baseUrl)}`
  );
  return json(res);
}
```

- [ ] **Step 3: Update `lightningfish_web/app/simulate/[domain]/page.tsx` — state, logic, and JSX**

**3a** — Add new imports at the top:

```typescript
import {
  DOMAINS,
  MODELS,
  FINANCE_ARCHETYPES,
  CODING_ARCHETYPES,
  type ArchetypeMeta,
  type ModelOption,
  type LocalStatus,
  LOCAL_POPULAR_MODELS,
  LOCAL_DEFAULT_BASE_URL,
} from "@/lib/types";
import { createSimulation, probeLocalServer } from "@/lib/api";
```

**3b** — Add new state variables inside `SimulatePage`, after the existing `useState` declarations:

```typescript
const [useLocalModel, setUseLocalModel] = useState(false);
const [localBaseUrl, setLocalBaseUrl] = useState(LOCAL_DEFAULT_BASE_URL);
const [localModelName, setLocalModelName] = useState("llama3.2");
const [localStatus, setLocalStatus] = useState<LocalStatus | null>(null);
const [probingLocal, setProbingLocal] = useState(false);
```

**3c** — Add `probeLocal` function inside `SimulatePage`, after the existing helper functions:

```typescript
async function probeLocal() {
  setProbingLocal(true);
  setLocalStatus(null);
  try {
    const status = await probeLocalServer(localBaseUrl);
    setLocalStatus(status);
  } catch {
    setLocalStatus({ available: false, gpu: null, models: [] });
  }
  setProbingLocal(false);
}
```

**3d** — Update `handleSubmit` to pass `base_url` and use the local model string when applicable:

```typescript
async function handleSubmit(e: React.FormEvent) {
  e.preventDefault();
  setError(null);
  setLoading(true);
  try {
    const agent_config = normalizedConfig(archetypes, enabled, customProps);
    const { simulation_id } = await createSimulation({
      domain_id: domain,
      user_id: user?.id ?? "anonymous",
      raw_input: buildRawInput(),
      n_agents: nAgents,
      n_rounds: nRounds,
      model: useLocalModel ? `ollama:${localModelName}` : model.id,
      agent_config,
      base_url: useLocalModel ? localBaseUrl : null,
    });
    router.push(`/simulate/${simulation_id}/live`);
  } catch (err) {
    setError(err instanceof Error ? err.message : "Request failed");
    setLoading(false);
  }
}
```

**3e** — Add the local model section JSX after the closing `</div>` of the Model picker section and before the Advanced agent mix section:

```tsx
{/* Local / Self-hosted */}
<div>
  <label className="block text-sm font-medium mb-2">
    Run on your own GPU / CPU
  </label>
  <div className="border border-neutral-200 rounded-xl overflow-hidden">
    <div className="flex items-center gap-3 px-4 py-3">
      <input
        type="checkbox"
        id="use-local"
        checked={useLocalModel}
        onChange={(e) => {
          setUseLocalModel(e.target.checked);
          setLocalStatus(null);
        }}
        className="accent-neutral-800"
      />
      <label
        htmlFor="use-local"
        className="text-sm text-neutral-700 flex-1 cursor-pointer"
      >
        Use local inference server (Ollama)
      </label>
      {useLocalModel && localStatus && (
        <span
          className={`text-xs px-2 py-0.5 rounded-full border ${
            !localStatus.available
              ? "bg-red-50 border-red-200 text-red-600"
              : localStatus.gpu
              ? "bg-emerald-50 border-emerald-200 text-emerald-700"
              : "bg-neutral-100 border-neutral-200 text-neutral-600"
          }`}
        >
          {!localStatus.available
            ? "offline"
            : localStatus.gpu
            ? "GPU"
            : "CPU"}
        </span>
      )}
    </div>

    {useLocalModel && (
      <div className="border-t border-neutral-100 px-4 py-3 space-y-3">
        <div>
          <label className="block text-xs text-neutral-500 mb-1">
            Endpoint
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={localBaseUrl}
              onChange={(e) => {
                setLocalBaseUrl(e.target.value);
                setLocalStatus(null);
              }}
              className="flex-1 border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-neutral-400"
              placeholder="http://localhost:11434/v1"
            />
            <button
              type="button"
              onClick={probeLocal}
              disabled={probingLocal}
              className="text-xs px-3 py-2 border border-neutral-200 rounded-lg hover:border-neutral-400 transition-colors disabled:opacity-50 whitespace-nowrap"
            >
              {probingLocal ? "..." : "Test"}
            </button>
          </div>
          {localStatus && !localStatus.available && (
            <p className="text-xs text-red-500 mt-1">
              Could not reach server. Is Ollama running?
            </p>
          )}
        </div>

        <div>
          <label className="block text-xs text-neutral-500 mb-1">
            Model
          </label>
          <div className="flex gap-1.5 flex-wrap mb-2">
            {LOCAL_POPULAR_MODELS.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setLocalModelName(m)}
                className={`text-xs px-2 py-1 rounded border transition-colors ${
                  localModelName === m
                    ? "border-neutral-800 bg-neutral-50"
                    : "border-neutral-200 hover:border-neutral-400"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <input
            type="text"
            value={localModelName}
            onChange={(e) => setLocalModelName(e.target.value)}
            className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-neutral-400"
            placeholder="Custom model name"
          />
        </div>

        {localStatus?.models.length ? (
          <p className="text-xs text-neutral-400">
            Loaded: {localStatus.models.join(", ")}
          </p>
        ) : null}

        <p className="text-xs text-neutral-400">
          Zero API cost. Install Ollama at{" "}
          <a
            href="https://ollama.com"
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-neutral-700"
          >
            ollama.com
          </a>
          {", then run "}
          <code className="bg-neutral-100 px-1 rounded">
            ollama pull llama3.2
          </code>
          .
        </p>
      </div>
    )}
  </div>
</div>
```

- [ ] **Step 4: TypeScript check**

Run: `cd lightningfish_web && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 5: Run full test suite**

Run from repo root: `pytest -x`
Expected: All Python tests PASS

- [ ] **Step 6: Commit**

```bash
git add lightningfish_web/lib/types.ts lightningfish_web/lib/api.ts \
  lightningfish_web/app/simulate/[domain]/page.tsx
git commit -m "feat: local model picker with Ollama endpoint, GPU/CPU status badge"
```

---

## Self-Review

**Spec coverage:**
- Local LLM via OpenAI-compatible API — Task 1 (`LocalProvider`) + Task 2 (engine) + Task 3 (routes)
- GPU detection — Task 4 (`/local/status` probes Ollama `/api/ps`, returns `gpu: bool | null`)
- CPU fallback badge — Task 5 (shows "CPU" when `gpu === false`)
- Zero cost for local models — Task 1 (`LocalProvider.get_opinion` always returns `0.0`)
- `openai` package in Modal image — Task 3 step 5
- DB migration for `base_url` — Task 3 step 1
- Chat route uses local model — Task 3 step 4
- Frontend toggle + endpoint config — Task 5

**Placeholder scan:** None found. All steps contain exact code.

**Type consistency:**
- `base_url: str | None` flows identically through `make_provider` → `SimulationEngine.__init__` → `create_simulation` → `SimulateRequest` → `createSimulation` (TS)
- `LocalStatus` interface matches the `/local/status` JSON response shape exactly
- `ollama:${localModelName}` on the frontend → `LocalProvider` strips prefix via `model.split(":", 1)[-1]` — consistent
- `LOCAL_POPULAR_MODELS` is `as const` tuple — safe to iterate with `.map()`
