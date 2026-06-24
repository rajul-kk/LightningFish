from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from lightningfish_core.registry import registry
from ..serializers import seed_to_dict

router = APIRouter()


class EnrichRequest(BaseModel):
    domain_id: str
    raw_input: dict


@router.post("")
def enrich(req: EnrichRequest):
    adapter = registry.get(req.domain_id)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"Unknown domain: {req.domain_id}")
    seed = adapter.enrich_seed(req.raw_input)
    return seed_to_dict(seed)
