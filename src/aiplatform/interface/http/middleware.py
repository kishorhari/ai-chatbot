"""Correlation-id ASGI middleware.

Establishes a correlation id at the HTTP request boundary: it reads an inbound
``X-Correlation-ID`` / ``X-Request-ID`` header (or generates one), binds it for
the duration of the request, and echoes it on the response.

Implemented as a **pure ASGI** middleware rather than a Starlette
``BaseHTTPMiddleware`` on purpose: pure ASGI runs the downstream app in the same
task, so the ``contextvar`` set here is reliably visible to the route handler and
to every log record emitted while handling the request (avoiding the known
``BaseHTTPMiddleware`` context-propagation pitfall).
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from aiplatform.infrastructure.logging.context import correlation_id_scope

# Inbound headers checked, in order of preference (lower-case, as ASGI delivers).
_REQUEST_HEADERS: tuple[bytes, ...] = (b"x-correlation-id", b"x-request-id")
_RESPONSE_HEADER = b"x-correlation-id"


class CorrelationIdMiddleware:
    """Bind a per-request correlation id and surface it on the response."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the downstream ASGI application."""
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Bind the correlation id for HTTP requests; pass others through."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        with correlation_id_scope(_read_correlation_id(scope)) as correlation_id:
            await self._app(scope, receive, _with_response_header(send, correlation_id))


def _read_correlation_id(scope: Scope) -> str | None:
    """Return the first non-empty correlation header value from the request."""
    headers: dict[bytes, bytes] = {name.lower(): value for name, value in scope.get("headers", [])}
    for header in _REQUEST_HEADERS:
        value = headers.get(header)
        if value:
            text = value.decode("latin-1").strip()
            if text:
                return text
    return None


def _with_response_header(send: Send, correlation_id: str) -> Send:
    """Wrap ``send`` so the correlation id is added to the response start event."""

    async def wrapped(message: Message) -> None:
        if message["type"] == "http.response.start":
            headers = message.setdefault("headers", [])
            headers.append((_RESPONSE_HEADER, correlation_id.encode("latin-1")))
        await send(message)

    return wrapped
