"""Unit tests for the pure Ollama mapping layer (M1.4).

No I/O and no httpx client here — only data translation and error classification.
"""

from __future__ import annotations

import httpx
import pytest

from aiplatform.domain.llm.errors import (
    LLMAuthenticationError,
    LLMModelError,
    LLMProtocolError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransportError,
)
from aiplatform.domain.llm.messages import ChatMessage
from aiplatform.domain.llm.requests import CompletionRequest, GenerationParams
from aiplatform.domain.llm.responses import FinishReason
from aiplatform.infrastructure.llm.ollama import mapping

# --- build_chat_request -----------------------------------------------------


def test_build_request_maps_messages_and_stream_flag() -> None:
    request = CompletionRequest(
        messages=(ChatMessage.system("sys"), ChatMessage.user("hi")),
    )
    body = mapping.build_chat_request(request, model="llama3")
    assert body["model"] == "llama3"
    assert body["stream"] is True
    assert body["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    assert "options" not in body  # nothing set -> no options key


def test_build_request_forwards_only_set_options() -> None:
    request = CompletionRequest(
        messages=(ChatMessage.user("hi"),),
        params=GenerationParams(temperature=0.5, max_tokens=64, stop=("X",), seed=7),
    )
    options = mapping.build_chat_request(request, model="m")["options"]
    assert options == {"temperature": 0.5, "num_predict": 64, "stop": ["X"], "seed": 7}
    assert "top_p" not in options


def test_build_request_can_disable_stream() -> None:
    request = CompletionRequest(messages=(ChatMessage.user("hi"),))
    assert mapping.build_chat_request(request, model="m", stream=False)["stream"] is False


# --- parse_chunk ------------------------------------------------------------


def test_parse_non_final_chunk() -> None:
    chunk = mapping.parse_chunk({"message": {"role": "assistant", "content": "Hi"}, "done": False})
    assert chunk.delta == "Hi"
    assert chunk.is_final is False


def test_parse_final_chunk_carries_reason_and_usage() -> None:
    chunk = mapping.parse_chunk(
        {
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 5,
            "eval_count": 9,
        }
    )
    assert chunk.is_final is True
    assert chunk.finish_reason is FinishReason.STOP
    assert chunk.usage is not None
    assert chunk.usage.prompt_tokens == 5
    assert chunk.usage.completion_tokens == 9


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("stop", FinishReason.STOP),
        ("length", FinishReason.LENGTH),
        (None, FinishReason.STOP),
        ("unknown-reason", FinishReason.STOP),
    ],
)
def test_map_finish_reason(reason: str | None, expected: FinishReason) -> None:
    assert mapping.map_finish_reason(reason) is expected


def test_parse_chunk_rejects_non_string_content() -> None:
    with pytest.raises(LLMProtocolError):
        mapping.parse_chunk({"message": {"content": 123}, "done": False})


def test_parse_chunk_rejects_non_object_message() -> None:
    with pytest.raises(LLMProtocolError):
        mapping.parse_chunk({"message": "oops", "done": False})


# --- error_from_response ----------------------------------------------------


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, LLMAuthenticationError),
        (403, LLMAuthenticationError),
        (404, LLMModelError),
        (400, LLMModelError),
        (408, LLMTimeoutError),
        (429, LLMRateLimitError),
        (500, LLMTransportError),
        (503, LLMTransportError),
        (418, LLMProtocolError),
    ],
)
def test_error_from_response_classifies_status(status: int, error_type: type) -> None:
    error = mapping.error_from_response(status, body='{"error": "boom"}')
    assert isinstance(error, error_type)
    assert error.message == "boom"


def test_error_from_response_rate_limit_carries_retry_after() -> None:
    error = mapping.error_from_response(429, body=None, retry_after=3.0)
    assert isinstance(error, LLMRateLimitError)
    assert error.retry_after == 3.0


def test_error_from_response_falls_back_to_generic_message() -> None:
    assert "HTTP 500" in mapping.error_from_response(500).message


# --- map_transport_error ----------------------------------------------------


@pytest.mark.parametrize(
    ("exc", "error_type"),
    [
        (httpx.ConnectTimeout("t"), LLMTimeoutError),
        (httpx.ReadTimeout("t"), LLMTimeoutError),
        (httpx.ConnectError("refused"), LLMTransportError),
        (httpx.ReadError("reset"), LLMTransportError),
        (httpx.RemoteProtocolError("bad"), LLMProtocolError),
    ],
)
def test_map_transport_error(exc: httpx.HTTPError, error_type: type) -> None:
    error = mapping.map_transport_error(exc)
    assert isinstance(error, error_type)
    assert error.cause is exc


@pytest.mark.parametrize(
    ("value", "expected"), [("5", 5.0), ("2.5", 2.5), (None, None), ("soon", None)]
)
def test_parse_retry_after(value: str | None, expected: float | None) -> None:
    assert mapping.parse_retry_after(value) == expected
