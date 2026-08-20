from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "finance" in body["domains"]
    assert "coding" in body["domains"]
    # Regression: main.py only registers a domain if it's explicitly imported
    # (the entry-point auto-discovery path exists but is never called) - the
    # hn import was missing here for a while, silently making the domain the
    # frontend fully supports unreachable on a real running service.
    assert "hn" in body["domains"]
    assert "anthropic_configured" in body
