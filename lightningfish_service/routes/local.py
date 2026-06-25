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
