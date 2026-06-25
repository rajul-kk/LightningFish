from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from fastapi import Request
from anthropic import Anthropic
import openai as _openai
from lightningfish_core.registry import registry
from ..db import get_simulation
from ..limiter import limiter

router = APIRouter()


class ChatRequest(BaseModel):
    archetype: str
    message: str


@router.post("/{simulation_id}")
@limiter.limit("20/minute")
def chat(request: Request, simulation_id: str, req: ChatRequest):
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
