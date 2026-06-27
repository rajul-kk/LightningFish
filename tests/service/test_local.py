"""Route tests for GET /local/status and the _is_safe_url guard."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from lightningfish_service.routes.local import _is_safe_url

# ---------------------------------------------------------------------------
# Unit tests for _is_safe_url — no HTTP involved
# ---------------------------------------------------------------------------

def test_safe_url_localhost() -> None:
    assert _is_safe_url("http://localhost:11434/v1") is True


def test_safe_url_127() -> None:
    assert _is_safe_url("http://127.0.0.1:11434/v1") is True


def test_safe_url_private_rfc1918() -> None:
    assert _is_safe_url("http://192.168.1.10:11434/v1") is True
    assert _is_safe_url("http://10.0.0.5:11434/v1") is True


def test_unsafe_url_aws_metadata() -> None:
    assert _is_safe_url("http://169.254.169.254/latest/meta-data") is False


def test_unsafe_url_gcp_metadata() -> None:
    assert _is_safe_url("http://metadata.google.internal/computeMetadata/v1") is False


def test_unsafe_url_public_ip() -> None:
    assert _is_safe_url("http://8.8.8.8/v1") is False


def test_unsafe_url_bad_scheme() -> None:
    assert _is_safe_url("ftp://localhost/v1") is False


def test_unsafe_url_external_hostname() -> None:
    # Non-numeric hostname that isn't localhost → blocked
    assert _is_safe_url("http://myserver.example.com/v1") is False


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

def test_local_status_unsafe_url_rejected(client: TestClient) -> None:
    r = client.get("/local/status", params={"base_url": "http://169.254.169.254"})
    assert r.status_code == 400
    assert "private network" in r.json()["detail"]


def test_local_status_server_unavailable(client: TestClient) -> None:
    with patch("lightningfish_service.routes.local.httpx.get", side_effect=Exception("connection refused")):
        r = client.get("/local/status", params={"base_url": "http://localhost:11434/v1"})
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["models"] == []


def test_local_status_available_no_gpu(client: TestClient) -> None:
    models_resp = MagicMock(status_code=200)
    models_resp.json.return_value = {"data": [{"id": "llama3.2"}, {"id": "mistral"}]}

    ps_resp = MagicMock(status_code=200)
    # Empty running list → no model loaded → gpu stays None (unknown, not probed)
    ps_resp.json.return_value = {"models": []}

    def mock_get(url: str, **kwargs):
        if "/api/ps" in url:
            return ps_resp
        return models_resp

    with patch("lightningfish_service.routes.local.httpx.get", side_effect=mock_get):
        r = client.get("/local/status", params={"base_url": "http://localhost:11434/v1"})

    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["gpu"] is None  # no model loaded, can't tell if GPU is in use
    assert "llama3.2" in body["models"]


def test_local_status_available_with_gpu(client: TestClient) -> None:
    models_resp = MagicMock(status_code=200)
    models_resp.json.return_value = {"data": [{"id": "llama3.2"}]}

    ps_resp = MagicMock(status_code=200)
    ps_resp.json.return_value = {"models": [{"name": "llama3.2", "size_vram": 4_000_000_000}]}

    def mock_get(url: str, **kwargs):
        if "/api/ps" in url:
            return ps_resp
        return models_resp

    with patch("lightningfish_service.routes.local.httpx.get", side_effect=mock_get):
        r = client.get("/local/status", params={"base_url": "http://localhost:11434/v1"})

    assert r.status_code == 200
    assert r.json()["gpu"] is True
