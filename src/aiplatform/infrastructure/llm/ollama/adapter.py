"""OllamaProvider — the streaming ``LLMProvider`` adapter for Ollama.

This module owns **transport and orchestration** only; all data translation and
error classification live in :mod:`.mapping`. It streams over an async httpx
connection, applies connect/total timeouts from settings, retries **only the
connect phase** (never replaying a partially-streamed body), and guarantees that
no transport-native exception escapes — every failure surfaces as an
``LLMError`` subtype (ADR-0002). Consumer cancellation closes the underlying
HTTP stream via the ``async with`` context, releasing the connection and raising
nothing (ADR-0003).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from aiplatform.domain.llm.capabilities import ProviderCapabilities
from aiplatform.domain.llm.errors import LLMProtocolError
from aiplatform.domain.llm.ports import LLMProvider
from aiplatform.domain.llm.requests import CompletionRequest
from aiplatform.domain.llm.responses import CompletionChunk
from aiplatform.infrastructure.config.settings import OllamaSettings
from aiplatform.infrastructure.logging.setup import get_logger

from .mapping import (
    CHAT_PATH,
    build_chat_request,
    error_from_response,
    map_transport_error,
    parse_chunk,
    parse_retry_after,
)

_logger = get_logger("aiplatform.infrastructure.llm.ollama")


class OllamaProvider(LLMProvider):
    """Streaming provider backed by a local (or remote) Ollama server.

    Args:
        settings: Ollama connection and timeout configuration.
        client: An optional pre-built httpx client (e.g. for testing). When
            omitted, the provider builds and owns one from ``settings`` and
            disposes of it in :meth:`aclose`.
    """

    NAME = "ollama"

    def __init__(
        self, settings: OllamaSettings, *, client: httpx.AsyncClient | None = None
    ) -> None:
        """Initialise the provider, building an httpx client when none is given."""
        self._settings = settings
        self._owns_client = client is None
        self._client = client if client is not None else self._build_client(settings)

    def capabilities(self) -> ProviderCapabilities:
        """Return Ollama's capabilities (pure, no I/O).

        Context window varies per model and is not declared here.
        """
        return ProviderCapabilities(
            model=self._settings.model,
            supports_streaming=True,
            supports_system_prompt=True,
            reports_token_usage=True,
            max_context_tokens=None,
        )

    async def stream_chat(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        """Stream a completion from Ollama as domain chunks.

        Retries are confined to the connect phase: a connect failure before any
        chunk is yielded is retried up to ``max_connect_retries`` times; any
        failure once streaming has begun is mapped and raised without retry, so a
        partially-streamed body is never replayed.
        """
        body = build_chat_request(request, model=self._resolve_model(request))
        attempts = self._settings.max_connect_retries + 1
        for attempt in range(attempts):
            try:
                async with self._client.stream("POST", CHAT_PATH, json=body) as response:
                    await self._raise_for_status(response)
                    async for chunk in self._parse_stream(response):
                        yield chunk
                return
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                _logger.warning(
                    "ollama.connect_failed",
                    attempt=attempt + 1,
                    max_attempts=attempts,
                    error=type(exc).__name__,
                )
                if attempt + 1 >= attempts:
                    raise map_transport_error(exc) from exc
            except httpx.HTTPError as exc:
                raise map_transport_error(exc) from exc

    async def aclose(self) -> None:
        """Dispose of the owned httpx client (no-op for an injected client)."""
        if self._owns_client:
            await self._client.aclose()

    def _resolve_model(self, request: CompletionRequest) -> str:
        """Resolve the effective model: request override, else configured default."""
        return request.model or self._settings.model

    async def _raise_for_status(self, response: httpx.Response) -> None:
        """Map a non-2xx response to an ``LLMError``, reading the error body."""
        if response.status_code < 400:
            return
        raw = await response.aread()
        retry_after = parse_retry_after(response.headers.get("retry-after"))
        raise error_from_response(
            response.status_code,
            body=raw.decode("utf-8", errors="replace"),
            retry_after=retry_after,
        )

    async def _parse_stream(self, response: httpx.Response) -> AsyncIterator[CompletionChunk]:
        """Decode the NDJSON stream into domain chunks."""
        async for line in response.aiter_lines():
            stripped = line.strip()
            if not stripped:
                continue
            payload = self._decode_line(stripped)
            error = payload.get("error")
            if error:
                raise LLMProtocolError(f"Ollama stream error: {error}")
            yield parse_chunk(payload)

    @staticmethod
    def _decode_line(line: str) -> dict[str, Any]:
        """Decode a single NDJSON line, mapping decode failures to a domain error."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LLMProtocolError("malformed JSON line from Ollama", cause=exc) from exc
        if not isinstance(data, dict):
            raise LLMProtocolError("unexpected non-object line from Ollama")
        return data

    @staticmethod
    def _build_client(settings: OllamaSettings) -> httpx.AsyncClient:
        """Build an httpx client with connect/read timeouts and optional auth."""
        timeout = httpx.Timeout(
            connect=settings.connect_timeout_seconds,
            read=settings.request_timeout_seconds,
            write=settings.request_timeout_seconds,
            pool=settings.connect_timeout_seconds,
        )
        headers: dict[str, str] = {}
        if settings.api_key is not None:
            headers["Authorization"] = f"Bearer {settings.api_key.get_secret_value()}"
        return httpx.AsyncClient(base_url=settings.base_url, timeout=timeout, headers=headers)
