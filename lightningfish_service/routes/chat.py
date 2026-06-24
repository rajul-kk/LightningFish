from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from anthropic import Anthropic
from lightningfish_core.registry import registry
from ..db import get_simulation

router = APIRouter()

_client = Anthropic()
_MODEL = "claude-sonnet-4-6"


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

    response = _client.messages.create(
        model=_MODEL,
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": req.message}],
    )
    return {"reply": response.content[0].text.strip()}
