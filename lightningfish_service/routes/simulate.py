from __future__ import annotations
import json
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from lightningfish_core.registry import registry
from lightningfish_core.engine import SimulationEngine
from ..db import (
    create_simulation, get_simulation, get_simulations_by_user,
    update_simulation_status, update_simulation_result, insert_round_event,
)
from ..serializers import seed_from_dict, seed_to_dict, round_event_to_dict, result_to_dict

router = APIRouter()


class SimulateRequest(BaseModel):
    domain_id: str
    user_id: str
    raw_input: dict
    n_agents: int = 500
    n_rounds: int = 12
    model: str = "claude-sonnet-4-6"
    agent_config: dict[str, float] | None = None
    base_url: str | None = None


@router.get("")
def list_simulations(user_id: str, limit: int = 50):
    """Return a user's simulation history."""
    rows = get_simulations_by_user(user_id, limit)
    for row in rows:
        if isinstance(row.get("seed_json"), str):
            row["seed_json"] = json.loads(row["seed_json"])
        if isinstance(row.get("result_json"), str):
            row["result_json"] = json.loads(row["result_json"])
        if hasattr(row.get("created_at"), "isoformat"):
            row["created_at"] = row["created_at"].isoformat()
        if row.get("cost_usd") is not None:
            row["cost_usd"] = float(row["cost_usd"])
        row["id"] = str(row["id"])
    return rows


@router.post("")
def create(req: SimulateRequest):
    """Enrich the seed, store the simulation record, return simulation_id."""
    adapter = registry.get(req.domain_id)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"Unknown domain: {req.domain_id}")

    seed = adapter.enrich_seed(req.raw_input)
    seed_dict = seed_to_dict(seed)
    sim_id = str(uuid.uuid4())
    create_simulation(
        sim_id, req.user_id, req.domain_id, seed_dict,
        req.n_agents, req.n_rounds, req.model, req.agent_config, req.base_url,
    )
    return {"simulation_id": sim_id}


@router.get("/{simulation_id}/result")
def get_result(simulation_id: str):
    """Return the full simulation record including result JSON."""
    sim = get_simulation(simulation_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    result_json = sim.get("result_json")
    if isinstance(result_json, str):
        result_json = json.loads(result_json)
    seed_json = sim.get("seed_json")
    if isinstance(seed_json, str):
        seed_json = json.loads(seed_json)
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


@router.get("/{simulation_id}")
def stream(simulation_id: str):
    """Stream simulation rounds as SSE events. Final event has type='complete'."""
    sim = get_simulation(simulation_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if sim["status"] == "complete":
        raise HTTPException(status_code=409, detail="Simulation already complete")

    domain_id = sim["domain_id"]
    adapter = registry.get(domain_id)
    if adapter is None:
        raise HTTPException(status_code=500, detail=f"Domain adapter missing: {domain_id}")

    seed_dict = sim["seed_json"]
    if isinstance(seed_dict, str):
        seed_dict = json.loads(seed_dict)

    seed = seed_from_dict(seed_dict)
    n_agents: int = sim.get("n_agents") or 500
    n_rounds: int = sim.get("n_rounds") or 12
    model: str = sim.get("model") or "claude-sonnet-4-6"
    agent_config_raw = sim.get("agent_config_json")
    if isinstance(agent_config_raw, str):
        agent_config_raw = json.loads(agent_config_raw)
    agent_config: dict[str, float] | None = agent_config_raw
    base_url: str | None = sim.get("base_url")

    def generate():
        update_simulation_status(simulation_id, "running")
        engine = SimulationEngine(adapter, model=model, base_url=base_url)
        agents = adapter.build_personas(n_agents, archetype_config=agent_config)
        gen = engine.run_streaming(seed, agents, n_rounds)
        try:
            while True:
                event = next(gen)
                event_dict = round_event_to_dict(event)
                insert_round_event(simulation_id, event.round_number, event_dict)
                yield f"data: {json.dumps(event_dict)}\n\n"
        except StopIteration as exc:
            result = exc.value
            result_dict = result_to_dict(result)
            update_simulation_result(simulation_id, result_dict, result.total_cost_usd)
            yield f"data: {json.dumps({'type': 'complete', 'simulation_id': simulation_id, 'total_cost_usd': result.total_cost_usd})}\n\n"
        except Exception as exc:
            update_simulation_status(simulation_id, "failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
