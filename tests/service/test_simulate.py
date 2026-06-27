"""
Route tests for POST/GET /simulate.

The DB layer is patched at the point of import inside the route module so no
real database connection is required.
"""
from __future__ import annotations
import json
import uuid
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIM_ID = str(uuid.uuid4())

_SEED_DICT = {
    "domain_id": "finance",
    "raw_input": {"ticker": "AAPL"},
    "summary": "AAPL earnings beat",
    "entities": ["AAPL"],
    "event_type": "earnings_beat",
    "metadata": {},
    "scraped_context": [],
}

_COMPLETE_SIM = {
    "id": _SIM_ID,
    "user_id": "u1",
    "domain_id": "finance",
    "status": "complete",
    "seed_json": json.dumps(_SEED_DICT),
    "result_json": json.dumps({
        "trajectory": [0.1, 0.3, 0.4],
        "final_distribution": [0.1, 0.2, 0.3, 0.2, 0.2],
        "total_tier1_calls": 30,
        "total_cost_usd": 0.05,
        "seed_summary": "AAPL earnings beat",
        "domain_id": "finance",
        "event_type": "earnings_beat",
    }),
    "cost_usd": 0.05,
    "n_agents": 50,
    "n_rounds": 3,
    "model": "claude-sonnet-4-6",
    "base_url": None,
    "agent_config_json": None,
    "created_at": __import__("datetime").datetime(2025, 1, 1),
}

_PENDING_SIM = {**_COMPLETE_SIM, "status": "pending", "result_json": None}


# ---------------------------------------------------------------------------
# POST /simulate — validation
# ---------------------------------------------------------------------------

def test_create_unknown_domain(client: TestClient) -> None:
    r = client.post("/simulate", json={
        "domain_id": "does_not_exist",
        "user_id": "u1",
        "raw_input": {},
    })
    assert r.status_code == 404
    assert "Unknown domain" in r.json()["detail"]


def test_create_n_agents_too_low(client: TestClient) -> None:
    r = client.post("/simulate", json={
        "domain_id": "finance",
        "user_id": "u1",
        "raw_input": {"ticker": "AAPL"},
        "n_agents": 5,
    })
    assert r.status_code == 422


def test_create_n_agents_too_high(client: TestClient) -> None:
    r = client.post("/simulate", json={
        "domain_id": "finance",
        "user_id": "u1",
        "raw_input": {"ticker": "AAPL"},
        "n_agents": 9999,
    })
    assert r.status_code == 422


def test_create_n_rounds_too_low(client: TestClient) -> None:
    r = client.post("/simulate", json={
        "domain_id": "finance",
        "user_id": "u1",
        "raw_input": {"ticker": "AAPL"},
        "n_rounds": 1,
    })
    assert r.status_code == 422


def test_create_n_rounds_too_high(client: TestClient) -> None:
    r = client.post("/simulate", json={
        "domain_id": "finance",
        "user_id": "u1",
        "raw_input": {"ticker": "AAPL"},
        "n_rounds": 99,
    })
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /simulate — happy path (DB + seed enrichment mocked)
# ---------------------------------------------------------------------------

def test_create_returns_simulation_id(client: TestClient) -> None:
    mock_adapter = MagicMock()
    mock_adapter.enrich_seed.return_value = MagicMock(
        domain_id="finance", raw_input={}, summary="test", entities=[],
        event_type="test", metadata={}, scraped_context=[],
    )

    with (
        patch("lightningfish_service.routes.simulate.registry") as mock_reg,
        patch("lightningfish_service.routes.simulate.create_simulation") as mock_create,
        patch("lightningfish_service.routes.simulate.seed_to_dict", return_value=_SEED_DICT),
    ):
        mock_reg.get.return_value = mock_adapter
        r = client.post("/simulate", json={
            "domain_id": "finance",
            "user_id": "u1",
            "raw_input": {"ticker": "AAPL"},
        })

    assert r.status_code == 200
    body = r.json()
    assert "simulation_id" in body
    assert mock_create.called


# ---------------------------------------------------------------------------
# GET /simulate/{id}/result
# ---------------------------------------------------------------------------

def test_get_result_not_found(client: TestClient) -> None:
    with patch("lightningfish_service.routes.simulate.get_simulation", return_value=None):
        r = client.get(f"/simulate/{_SIM_ID}/result")
    assert r.status_code == 404


def test_get_result_complete(client: TestClient) -> None:
    with patch("lightningfish_service.routes.simulate.get_simulation", return_value=_COMPLETE_SIM):
        r = client.get(f"/simulate/{_SIM_ID}/result")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "complete"
    assert body["domain_id"] == "finance"
    assert isinstance(body["result_json"]["trajectory"], list)


# ---------------------------------------------------------------------------
# GET /simulate/{id} — stream error cases
# ---------------------------------------------------------------------------

def test_stream_not_found(client: TestClient) -> None:
    with patch("lightningfish_service.routes.simulate.get_simulation", return_value=None):
        r = client.get(f"/simulate/{_SIM_ID}")
    assert r.status_code == 404


def test_stream_already_complete(client: TestClient) -> None:
    with patch("lightningfish_service.routes.simulate.get_simulation", return_value=_COMPLETE_SIM):
        r = client.get(f"/simulate/{_SIM_ID}")
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# GET /simulate — list
# ---------------------------------------------------------------------------

def test_list_simulations(client: TestClient) -> None:
    mock_rows = [{
        **_COMPLETE_SIM,
        "id": _SIM_ID,
        "seed_json": _SEED_DICT,
        "result_json": None,
    }]
    with patch("lightningfish_service.routes.simulate.get_simulations_by_user", return_value=mock_rows):
        r = client.get("/simulate", params={"user_id": "u1"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
