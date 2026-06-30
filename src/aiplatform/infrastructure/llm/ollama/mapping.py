"""Pure translation between the domain and the Ollama HTTP API.

This module is the **mapping layer** (ADR-0002): it converts domain value
objects to Ollama request payloads, Ollama stream lines to domain
``CompletionChunk``s, and every transport/HTTP failure to an ``LLMError``
subtype. It performs **no I/O** — it only transforms data and classifies errors,
which keeps it exhaustively unit-testable and keeps vendor payload shapes out of
the adapter's control flow.

It depends only on the domain (requests/responses/errors) plus ``httpx`` for the
transport-exception *types* it classifies.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

from aiplatform.domain.llm.errors import (
    LLMAuthenticationError,
    LLMError,
    LLMModelError,
    LLMProtocolError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransportError,
)
from aiplatform.domain.llm.requests import CompletionRequest
from aiplatform.domain.llm.responses import CompletionChunk, FinishReason, TokenUsage

#: Ollama chat endpoint path (joined onto the configured base URL).
CHAT_PATH = "/api/chat"

# Ollama's ``done_reason`` -> domain ``FinishReason``.
_FINISH_REASONS: dict[str, FinishReason] = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
}


def build_chat_request(
    request: CompletionRequest, *, model: str, stream: bool = True
) -> dict[str, Any]:
    """Translate a domain request into an Ollama ``/api/chat`` payload.

    Only generation parameters that were explicitly set are forwarded, so the
    provider applies its own defaults for the rest (mirroring the domain's
    "``None`` means provider default" convention).

    Args:
        request: The domain completion request.
        model: The resolved model name to generate with.
        stream: Whether to request a streamed response.

    Returns:
        A JSON-serialisable Ollama request body.
    """
    options: dict[str, Any] = {}
    params = request.params
    if params.temperature is not None:
        options["temperature"] = params.temperature
    if params.top_p is not None:
        options["top_p"] = params.top_p
    if params.max_tokens is not None:
        options["num_predict"] = params.max_tokens
    if params.seed is not None:
        options["seed"] = params.seed
    if params.stop:
        options["stop"] = list(params.stop)

    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
        "stream": stream,
    }
    if options:
        body["options"] = options
    return body


def map_finish_reason(reason: str | None) -> FinishReason:
    """Map an Ollama ``done_reason`` to a domain ``FinishReason`` (default STOP)."""
    if reason is None:
        return FinishReason.STOP
    return _FINISH_REASONS.get(reason, FinishReason.STOP)


def parse_chunk(payload: Mapping[str, Any]) -> CompletionChunk:
    """Translate one decoded Ollama stream object into a ``CompletionChunk``.

    Args:
        payload: A single decoded NDJSON object from the stream.

    Returns:
        A non-final chunk, or the terminal chunk when ``done`` is true.

    Raises:
        LLMProtocolError: If the object's shape is not what the contract expects.
    """
    content = _extract_content(payload)
    if not bool(payload.get("done", False)):
        return CompletionChunk(delta=content)
    return CompletionChunk(
        delta=content,
        is_final=True,
        finish_reason=map_finish_reason(payload.get("done_reason")),
        usage=_parse_usage(payload),
    )


def error_from_response(
    status_code: int, *, body: str | None = None, retry_after: float | None = None
) -> LLMError:
    """Classify an HTTP error response into an ``LLMError`` subtype.

    Args:
        status_code: The HTTP status code (>= 400).
        body: The response body, used to extract a provider error message.
        retry_after: Parsed ``Retry-After`` value in seconds, if present.

    Returns:
        The matching domain error.
    """
    message = _extract_error_message(body) or f"Ollama returned HTTP {status_code}"
    if status_code in (401, 403):
        return LLMAuthenticationError(message)
    if status_code == 404:
        # Ollama returns 404 for an unknown model.
        return LLMModelError(message)
    if status_code == 408:
        return LLMTimeoutError(message)
    if status_code == 429:
        return LLMRateLimitError(message, retry_after=retry_after)
    if status_code == 400:
        # Ollama's 400s are predominantly invalid-model / bad-option requests.
        return LLMModelError(message)
    if 500 <= status_code < 600:
        return LLMTransportError(message)
    return LLMProtocolError(message)


def map_transport_error(exc: httpx.HTTPError) -> LLMError:
    """Classify a raised ``httpx`` transport error into an ``LLMError`` subtype.

    Order matters: timeouts and protocol errors are checked before the broad
    transport category they both inherit from.

    Args:
        exc: The httpx exception raised during a request or stream.

    Returns:
        The matching domain error, preserving ``exc`` as the cause.
    """
    if isinstance(exc, httpx.TimeoutException):
        return LLMTimeoutError(str(exc) or "Ollama request timed out", cause=exc)
    if isinstance(exc, httpx.ProtocolError):
        return LLMProtocolError(str(exc) or "Ollama protocol error", cause=exc)
    if isinstance(exc, httpx.TransportError):
        return LLMTransportError(str(exc) or "could not reach Ollama", cause=exc)
    return LLMTransportError(str(exc) or "Ollama transport failure", cause=exc)


def parse_retry_after(value: str | None) -> float | None:
    """Parse a numeric ``Retry-After`` header value into seconds, if possible."""
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _extract_content(payload: Mapping[str, Any]) -> str:
    """Extract the assistant content string from a stream object."""
    message = payload.get("message")
    if message is None:
        return ""
    if not isinstance(message, Mapping):
        raise LLMProtocolError("Ollama chunk 'message' is not an object")
    content = message.get("content", "")
    if not isinstance(content, str):
        raise LLMProtocolError("Ollama chunk content is not a string")
    return content


def _parse_usage(payload: Mapping[str, Any]) -> TokenUsage:
    """Build ``TokenUsage`` from an Ollama terminal object's eval counts."""
    prompt = payload.get("prompt_eval_count") or 0
    completion = payload.get("eval_count") or 0
    try:
        return TokenUsage(prompt_tokens=int(prompt), completion_tokens=int(completion))
    except (TypeError, ValueError) as exc:
        raise LLMProtocolError("Ollama usage counts are not integers", cause=exc) from exc


def _extract_error_message(body: str | None) -> str | None:
    """Pull the ``error`` field from an Ollama error body, falling back to raw."""
    if not body:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body.strip() or None
    if isinstance(data, dict) and isinstance(data.get("error"), str):
        return data["error"]
    return body.strip() or None
