"""
Lightningfish FastAPI service.

Local dev: uvicorn lightningfish_service.main:app --reload --port 8000
Modal:      modal serve lightningfish_service.modal_app
"""
from __future__ import annotations

import logging
import os
import sys

# Ensure project root is on sys.path when running in Modal's container
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Trigger domain registration
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import lightningfish_coding  # noqa: F401
import lightningfish_finance  # noqa: F401
import lightningfish_hn  # noqa: F401

from .limiter import limiter
from .routes import backtest, chat, enrich, keys, local, simulate

app = FastAPI(title="Lightningfish Service", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

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
    return {
        "status": "ok",
        "domains": [a.domain_id for a in registry.all()],
        # A key being *set* doesn't mean it's valid, but its absence is a
        # reliable "hosted models will fail" signal the frontend can act on
        # before the user spends a click finding out the hard way.
        "anthropic_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }
