from __future__ import annotations

import os

from fastapi import Header, HTTPException

_SECRET = os.environ.get("SERVICE_SECRET", "")


def require_service_secret(x_service_secret: str = Header(default="")) -> None:
    """FastAPI dependency: reject requests that don't carry the shared service secret.

    In dev (SERVICE_SECRET unset) the check is skipped so local uvicorn still works.
    """
    if not _SECRET:
        return
    if x_service_secret != _SECRET:
        raise HTTPException(status_code=401, detail="Missing or invalid service secret")
