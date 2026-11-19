import json
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from frontend.api_client import BackendClient, normalize_backend_url
from src.ai_service import (
    AIService,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
)


def test_service_uses_environment_configuration(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.local:11434/")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "45")

    service = AIService()

    assert service.base_url == "http://ollama.local:11434"
    assert service.model == "qwen2.5:3b"
    assert service.timeout == 45


def test_service_sends_history_and_returns_clean_response():
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        {"message": {"content": "  Hello there. \n"}}
    ).encode()

    with patch("src.ai_service.urlopen", return_value=response) as urlopen:
        answer = AIService().get_response(
            [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Again"},
            ]
        )

    request = urlopen.call_args.args[0]
    payload = json.loads(request.data)
    assert answer == "Hello there."
    assert payload["model"] == "qwen2.5:3b"
    assert [message["role"] for message in payload["messages"]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]


def test_service_reports_connection_failure():
    with patch("src.ai_service.urlopen", side_effect=URLError("connection refused")):
        with pytest.raises(OllamaConnectionError):
            AIService().get_response([{"role": "user", "content": "Hi"}])


def test_service_reports_timeout():
    with patch("src.ai_service.urlopen", side_effect=TimeoutError):
        with pytest.raises(OllamaTimeoutError):
            AIService().get_response([{"role": "user", "content": "Hi"}])


def test_service_reports_missing_model():
    error_body = BytesIO(b'{"error":"model not found"}')
    error = HTTPError(
        "http://localhost:11434/api/chat", 404, "Not Found", {}, error_body
    )
    with patch("src.ai_service.urlopen", side_effect=error):
        with pytest.raises(OllamaModelNotFoundError):
            AIService().get_response([{"role": "user", "content": "Hi"}])


def test_frontend_normalizes_backend_url_and_sends_token():
    response = MagicMock()
    response.ok = True
    response.json.return_value = {"model": "qwen2.5:3b"}
    with patch("frontend.api_client.requests.get", return_value=response) as get:
        client = BackendClient(" http://localhost:8000/ ", "test-token")
        assert client.model() == "qwen2.5:3b"

    assert get.call_args.args[0] == "http://localhost:8000/models"
    assert get.call_args.kwargs["headers"] == {
        "Authorization": "Bearer test-token"
    }


def test_frontend_uses_longer_timeout_for_model_generation():
    response = MagicMock()
    response.ok = True
    response.json.return_value = {"model": "qwen2.5:3b", "response": "Done"}
    messages = [{"role": "user", "content": "Hi"}]
    with patch("frontend.api_client.requests.post", return_value=response) as post:
        client = BackendClient(
            "http://localhost:8000",
            "test-token",
            timeout=5,
            chat_timeout=195,
        )
        client.chat(messages)

    assert post.call_args.kwargs["timeout"] == 195


def test_frontend_rejects_backend_url_without_http_scheme():
    with pytest.raises(ValueError, match="http:// or https://"):
        normalize_backend_url("localhost:8000")