"""
Lightningfish FastAPI service.

Local dev: uvicorn lightningfish_service.main:app --reload --port 8000
Modal:      modal serve lightningfish_service.modal_app
"""
from __future__ import annotations
import sys
import os

# Ensure project root is on sys.path when running in Modal's container
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Trigger domain registration
import lightningfish_finance  # noqa: F401
import lightningfish_coding   # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import enrich, simulate, chat, backtest, keys, local

app = FastAPI(title="Lightningfish Service", version="0.1.0")

_allowed_origins = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(enrich.router, prefix="/enrich", tags=["enrich"])
app.include_router(simulate.router, prefix="/simulate", tags=["simulate"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
app.include_router(keys.router, prefix="/keys", tags=["keys"])
app.include_router(local.router, prefix="/local", tags=["local"])


@app.get("/health", tags=["meta"])
def health():
    from lightningfish_core.registry import registry
    return {"status": "ok", "domains": list(registry.all().keys())}
