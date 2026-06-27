from __future__ import annotations
from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "finance" in body["domains"]
    assert "coding" in body["domains"]
