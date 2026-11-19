from typing import Any

import requests


class BackendClientError(RuntimeError):
    """A user-safe backend communication error."""


def normalize_backend_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if not normalized.startswith(("http://", "https://")):
        raise ValueError("Backend URL must start with http:// or https://.")
    return normalized


class BackendClient:
    def __init__(
        self,
        base_url: str,
        api_token: str,
        timeout: float = 10,
        chat_timeout: float = 210,
    ) -> None:
        self.base_url = normalize_backend_url(base_url)
        self.api_token = api_token
        self.timeout = timeout
        self.chat_timeout = chat_timeout

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}"}

    def health(self) -> dict[str, Any]:
        return self._get("/health", authenticated=False)

    def model(self) -> str:
        result = self._get("/models")
        return str(result["model"])

    def chat(self, messages: list[dict[str, str]]) -> dict[str, str]:
        try:
            response = requests.post(
                f"{self.base_url}/chat",
                json={"messages": messages},
                headers=self.headers,
                timeout=self.chat_timeout,
            )
            self._raise_for_status(response)
            return response.json()
        except requests.Timeout as error:
            raise BackendClientError(
                "The assistant took too long to respond. Please try again."
            ) from error
        except requests.ConnectionError as error:
            raise BackendClientError(
                "Cannot reach the AI backend. Check the URL and network connection."
            ) from error
        except requests.RequestException as error:
            raise BackendClientError(
                "The AI backend request failed. Please try again."
            ) from error
        except (ValueError, KeyError) as error:
            raise BackendClientError(
                "The AI backend returned an invalid response."
            ) from error

    def _get(
        self, path: str, authenticated: bool = True
    ) -> dict[str, Any]:
        try:
            response = requests.get(
                f"{self.base_url}{path}",
                headers=self.headers if authenticated else {},
                timeout=self.timeout,
            )
            self._raise_for_status(response)
            return response.json()
        except requests.Timeout as error:
            raise BackendClientError(
                "The AI backend did not respond in time."
            ) from error
        except requests.ConnectionError as error:
            raise BackendClientError(
                "Cannot reach the AI backend. Check the URL and network connection."
            ) from error
        except requests.RequestException as error:
            raise BackendClientError(
                "The AI backend request failed. Please try again."
            ) from error
        except (ValueError, KeyError) as error:
            raise BackendClientError(
                "The AI backend returned an invalid response."
            ) from error

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        if response.ok:
            return
        try:
            detail = response.json().get("detail", "")
        except ValueError:
            detail = ""
        if response.status_code == 401:
            message = "The backend rejected the API token. Check API_AUTH_TOKEN."
        elif response.status_code == 503 and "authentication" in str(detail).lower():
            message = "Backend API authentication is not configured."
        elif detail:
            message = str(detail)
        else:
            message = f"Backend returned HTTP {response.status_code}."
        raise BackendClientError(message)
