from __future__ import annotations

import ipaddress
import urllib.parse

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

_DEFAULT_BASE_URL = "http://localhost:11434/v1"

# Cloud metadata services that must never be reachable via this endpoint
_BLOCKED_HOSTS = {
    "169.254.169.254",   # AWS / Azure / GCP metadata
    "metadata.google.internal",
    "100.100.100.200",   # Alibaba metadata
}


def _is_safe_url(url: str) -> bool:
    """Allow only localhost and RFC-1918 private addresses."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname or ""
        if host in _BLOCKED_HOSTS:
            return False
        # Always allow localhost names
        if host in ("localhost", "127.0.0.1", "::1"):
            return True
        # Resolve numeric IPs — allow private/loopback ranges only
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback
    except ValueError:
        # Non-numeric hostname (e.g. "myserver.local") — block by default;
        # users should use an IP or localhost
        return False


@router.get("/status")
def local_status(base_url: str = _DEFAULT_BASE_URL) -> dict:
    """
    Probe an OpenAI-compatible local inference server.
    For Ollama, also queries /api/ps to detect GPU vs CPU usage.
    Returns: {available, gpu, models}
    """
    if not _is_safe_url(base_url):
        raise HTTPException(
            status_code=400,
            detail="base_url must point to localhost or a private network address.",
        )

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
