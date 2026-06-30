"""Unit tests for the correlation-id ASGI middleware (M1.6)."""

from __future__ import annotations

from typing import Any

from aiplatform.infrastructure.logging.context import get_correlation_id
from aiplatform.interface.http.middleware import CorrelationIdMiddleware


async def _drive(scope: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the middleware against a minimal ASGI harness, capturing what is sent."""
    sent: list[dict[str, Any]] = []
    seen: dict[str, Any] = {}

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    # A downstream app that records the contextvar value seen during the request.
    async def downstream(s: Any, r: Any, sd: Any) -> None:
        seen["correlation_id"] = get_correlation_id()
        await sd({"type": "http.response.start", "status": 200, "headers": []})
        await sd({"type": "http.response.body", "body": b""})

    await CorrelationIdMiddleware(downstream)(scope, receive, send)
    return sent, seen


def _start_headers(sent: list[dict[str, Any]]) -> list[tuple[bytes, bytes]]:
    start = next(m for m in sent if m["type"] == "http.response.start")
    return start["headers"]


async def test_uses_inbound_correlation_id() -> None:
    sent, seen = await _drive({"type": "http", "headers": [(b"x-correlation-id", b"req-9")]})
    assert seen["correlation_id"] == "req-9"
    assert (b"x-correlation-id", b"req-9") in _start_headers(sent)


async def test_falls_back_to_x_request_id() -> None:
    _, seen = await _drive({"type": "http", "headers": [(b"x-request-id", b"req-7")]})
    assert seen["correlation_id"] == "req-7"


async def test_generates_id_when_absent() -> None:
    sent, seen = await _drive({"type": "http", "headers": []})
    generated = seen["correlation_id"]
    assert generated  # a fresh id was created
    assert (b"x-correlation-id", generated.encode("latin-1")) in _start_headers(sent)


async def test_context_is_cleared_after_request() -> None:
    await _drive({"type": "http", "headers": [(b"x-correlation-id", b"req-1")]})
    assert get_correlation_id() is None  # scope unwound after the request
