"""Route tests for POST /chat/{simulation_id}."""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

_SIM_ID = str(uuid.uuid4())

_COMPLETE_SIM = {
    "id": _SIM_ID,
    "user_id": "u1",
    "domain_id": "finance",
    "status": "complete",
    "seed_json": json.dumps({}),
    "result_json": json.dumps({
        "trajectory": [0.1, 0.4],
        "seed_summary": "AAPL earnings beat",
        "domain_id": "finance",
    }),
    "model": "claude-sonnet-4-6",
    "base_url": None,
    "agent_config_json": None,
    "created_at": __import__("datetime").datetime(2025, 1, 1),
}

_PAYLOAD = {"archetype": "value_investor", "message": "Why did you buy?"}


def test_chat_sim_not_found(client: TestClient) -> None:
    with patch("lightningfish_service.routes.chat.get_simulation", return_value=None):
        r = client.post(f"/chat/{_SIM_ID}", json=_PAYLOAD)
    assert r.status_code == 404


def test_chat_sim_not_complete(client: TestClient) -> None:
    pending = {**_COMPLETE_SIM, "status": "running"}
    with patch("lightningfish_service.routes.chat.get_simulation", return_value=pending):
        r = client.post(f"/chat/{_SIM_ID}", json=_PAYLOAD)
    assert r.status_code == 409


def test_chat_anthropic_response(client: TestClient) -> None:
    mock_content = MagicMock()
    mock_content.text = "I bought because of strong fundamentals."
    mock_resp = MagicMock()
    mock_resp.content = [mock_content]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_resp

    with (
        patch("lightningfish_service.routes.chat.get_simulation", return_value=_COMPLETE_SIM),
        patch("lightningfish_service.routes.chat.Anthropic", return_value=mock_client),
    ):
        r = client.post(f"/chat/{_SIM_ID}", json=_PAYLOAD)

    assert r.status_code == 200
    assert r.json()["reply"] == "I bought because of strong fundamentals."


def test_chat_local_model_routes_to_openai(client: TestClient) -> None:
    local_sim = {**_COMPLETE_SIM, "model": "ollama:llama3.2", "base_url": "http://localhost:11434/v1"}

    mock_choice = MagicMock()
    mock_choice.message.content = "Local model reply."
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_openai_client = MagicMock()
    mock_openai_client.chat.completions.create.return_value = mock_resp

    with (
        patch("lightningfish_service.routes.chat.get_simulation", return_value=local_sim),
        patch("lightningfish_service.routes.chat._openai.OpenAI", return_value=mock_openai_client),
    ):
        r = client.post(f"/chat/{_SIM_ID}", json=_PAYLOAD)

    assert r.status_code == 200
    assert r.json()["reply"] == "Local model reply."
    # Verify Anthropic was NOT called
    mock_openai_client.chat.completions.create.assert_called_once()
