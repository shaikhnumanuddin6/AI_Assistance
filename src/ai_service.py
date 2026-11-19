import json
import os
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = (
    "You are a professional AI assistant who helps with programming, "
    "technology, learning, problem-solving, and general questions. "
    "Give accurate, clear, and well-structured answers. Explain difficult "
    "topics in simple language. When providing code, use correct syntax and "
    "explain important parts. Do not invent facts; state uncertainty clearly. "
    "Be friendly, patient, and concise."
)


class OllamaError(RuntimeError):
    """Base error for Ollama request and response failures."""


class OllamaConnectionError(OllamaError):
    """Ollama could not be reached."""


class OllamaTimeoutError(OllamaError):
    """Ollama did not respond before the configured timeout."""


class OllamaModelNotFoundError(OllamaError):
    """The configured model is not installed in Ollama."""


class OllamaResponseError(OllamaError):
    """Ollama returned an unusable response."""


class AIService:
    def __init__(self) -> None:
        self.base_url = os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        ).rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
        if self.timeout <= 0:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS must be greater than zero.")

    def get_response(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *messages,
            ],
            "stream": False,
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            if error.code == 404 or "not found" in body.lower():
                raise OllamaModelNotFoundError(
                    f"Ollama model '{self.model}' was not found. "
                    "Install it with `ollama pull` or update OLLAMA_MODEL."
                ) from error
            raise OllamaResponseError(
                f"Ollama returned HTTP error {error.code}."
            ) from error
        except (socket.timeout, TimeoutError) as error:
            raise OllamaTimeoutError(
                "Ollama did not respond before the request timed out."
            ) from error
        except URLError as error:
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                raise OllamaTimeoutError(
                    "Ollama did not respond before the request timed out."
                ) from error
            raise OllamaConnectionError(
                "Cannot connect to Ollama. Make sure it is running."
            ) from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise OllamaResponseError(
                "Ollama returned an invalid response."
            ) from error

        try:
            answer = result["message"]["content"]
        except (KeyError, TypeError) as error:
            raise OllamaResponseError(
                "Ollama returned an incomplete response."
            ) from error

        if not isinstance(answer, str) or not answer.strip():
            raise OllamaResponseError("Ollama returned an empty response.")
        return answer.strip()
