from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend import main


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "test-token")
    service = Mock()
    service.model = "qwen2.5:3b"
    service.get_response.return_value = "A helpful answer."
    monkeypatch.setattr(main, "ai_service", service)
    return TestClient(main.app), service


def test_health_is_public_liveness_endpoint(api_client):
    client, _ = api_client

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer incorrect-token"}],
)
def test_protected_models_endpoint_rejects_missing_or_wrong_token(
    api_client, headers
):
    client, _ = api_client

    response = client.get("/models", headers=headers)

    assert response.status_code == 401


def test_models_endpoint_returns_configured_model(api_client):
    client, _ = api_client

    response = client.get(
        "/models", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    assert response.json() == {"model": "qwen2.5:3b"}


def test_chat_passes_conversation_history_to_ai_service(api_client):
    client, service = api_client
    messages = [
        {"role": "user", "content": "Explain APIs"},
        {"role": "assistant", "content": "An API is an interface."},
        {"role": "user", "content": "Give an example"},
    ]

    response = client.post(
        "/chat",
        headers={"Authorization": "Bearer test-token"},
        json={"messages": messages},
    )

    assert response.status_code == 200
    assert response.json() == {
        "model": "qwen2.5:3b",
        "response": "A helpful answer.",
    }
    service.get_response.assert_called_once_with(messages)


@pytest.mark.parametrize(
    "payload",
    [
        {"messages": []},
        {"messages": [{"role": "system", "content": "not allowed"}]},
        {"messages": [{"role": "user", "content": "  "}]},
        {"messages": [{"role": "assistant", "content": "not the latest user"}]},
        {"messages": [{"role": "user", "content": "Hi", "extra": "no"}]},
    ],
)
def test_chat_rejects_invalid_requests(api_client, payload):
    client, service = api_client

    response = client.post(
        "/chat",
        headers={"Authorization": "Bearer test-token"},
        json=payload,
    )

    assert response.status_code == 422
    service.get_response.assert_not_called()


def test_chat_maps_ollama_connection_failure(api_client):
    client, service = api_client
    service.get_response.side_effect = main.OllamaConnectionError(
        "Cannot connect to Ollama."
    )

    response = client.post(
        "/chat",
        headers={"Authorization": "Bearer test-token"},
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Cannot connect to Ollama."


def test_protected_endpoint_fails_closed_without_configured_token(
    api_client, monkeypatch
):
    client, _ = api_client
    monkeypatch.delenv("API_AUTH_TOKEN")

    response = client.get(
        "/models", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 503
