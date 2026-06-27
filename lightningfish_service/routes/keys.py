from __future__ import annotations

import hashlib
import secrets
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from ..db import create_api_key, delete_api_key, list_api_keys

router = APIRouter()


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class CreateKeyRequest(BaseModel):
    user_id: str
    name: str


@router.get("")
def list_keys(user_id: str):
    rows = list_api_keys(user_id)
    for r in rows:
        r["id"] = str(r["id"])
        if hasattr(r.get("created_at"), "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
        if r.get("last_used_at") and hasattr(r["last_used_at"], "isoformat"):
            r["last_used_at"] = r["last_used_at"].isoformat()
    return rows


@router.post("")
def create_key(req: CreateKeyRequest):
    raw = f"lf_{secrets.token_urlsafe(32)}"
    key_id = str(uuid.uuid4())
    create_api_key(key_id, req.user_id, _hash(raw), req.name)
    return {"id": key_id, "key": raw, "name": req.name}


@router.delete("/{key_id}")
def delete_key(key_id: str, user_id: str):
    delete_api_key(key_id, user_id)
    return {"deleted": key_id}
