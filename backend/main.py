import hmac
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.ai_service import (
    AIService,
    OllamaConnectionError,
    OllamaError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="AI Assistance API", version="1.0.0")
ai_service = AIService()


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message content cannot be blank.")
        return value


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=1, max_length=100)

    @field_validator("messages")
    @classmethod
    def conversation_must_end_with_user(
        cls, messages: list[ChatMessage]
    ) -> list[ChatMessage]:
        if messages[-1].role != "user":
            raise ValueError("The latest conversation message must be from the user.")
        return messages


class ChatResponse(BaseModel):
    model: str
    response: str


def require_api_token(authorization: str | None = Header(default=None)) -> None:
    expected_token = os.getenv("API_AUTH_TOKEN", "")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured on the backend.",
        )

    scheme, separator, supplied_token = (authorization or "").partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not hmac.compare_digest(supplied_token, expected_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only; it does not expose model details or probe Ollama."""
    return {"status": "ok"}


@app.get("/models", dependencies=[Depends(require_api_token)])
def models() -> dict[str, str]:
    return {"model": ai_service.model}


@app.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_api_token)],
)
def chat(request: ChatRequest) -> ChatResponse:
    messages = [message.model_dump() for message in request.messages]
    try:
        answer = ai_service.get_response(messages)
    except OllamaModelNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except OllamaConnectionError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except OllamaTimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except OllamaError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return ChatResponse(model=ai_service.model, response=answer)
