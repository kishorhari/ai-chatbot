"""Adapter-level transport & error-mapping tests for OllamaProvider (M1.4).

These exercise the transport behaviour the shared contract suite deliberately
omits: HTTP-status -> error mapping, connect-phase retry semantics, no-replay on
mid-stream failure, and that every relevant ``LLMError`` subtype is provably
produced (roadmap §5 exit criterion 6). httpx is mocked with respx — no live
Ollama required.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
import respx

from aiplatform.domain.llm.errors import (
    LLMAuthenticationError,
    LLMModelError,
    LLMProtocolError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransportError,
)
from aiplatform.domain.llm.messages import ChatMessage
from aiplatform.domain.llm.requests import CompletionRequest
from aiplatform.domain.llm.responses import CompletionChunk
from aiplatform.infrastructure.config.settings import OllamaSettings
from aiplatform.infrastructure.llm.ollama.adapter import OllamaProvider

_BASE_URL = "http://ollama.test"
_CHAT_URL = f"{_BASE_URL}/api/chat"

_SUCCESS_STREAM = (
    b'{"message":{"role":"assistant","content":"Hi"},"done":false}\n'
    b'{"message":{"role":"assistant","content":"!"},"done":true,'
    b'"done_reason":"stop","prompt_eval_count":3,"eval_count":2}\n'
)


def _settings(**kwargs: object) -> OllamaSettings:
    return OllamaSettings(base_url=_BASE_URL, model="test-model", **kwargs)  # type: ignore[arg-type]


@pytest_asyncio.fixture
async def provider() -> AsyncIterator[OllamaProvider]:
    instance = OllamaProvider(_settings())
    yield instance
    await instance.aclose()


async def _drain(provider: OllamaProvider) -> list[CompletionChunk]:
    request = CompletionRequest(messages=(ChatMessage.user("hello"),))
    return [chunk async for chunk in provider.stream_chat(request)]


@respx.mock
async def test_successful_stream_yields_chunks_and_terminal(provider: OllamaProvider) -> None:
    respx.post(_CHAT_URL).mock(return_value=httpx.Response(200, content=_SUCCESS_STREAM))
    chunks = await _drain(provider)
    assert "".join(c.delta for c in chunks) == "Hi!"
    assert chunks[-1].is_final is True
    assert chunks[-1].usage is not None
    assert chunks[-1].usage.completion_tokens == 2


@respx.mock
async def test_request_body_targets_resolved_model(provider: OllamaProvider) -> None:
    route = respx.post(_CHAT_URL).mock(return_value=httpx.Response(200, content=_SUCCESS_STREAM))
    await _drain(provider)
    sent = route.calls.last.request
    assert b'"model":"test-model"' in sent.content
    assert b'"stream":true' in sent.content


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, LLMAuthenticationError),
        (404, LLMModelError),
        (429, LLMRateLimitError),
        (500, LLMTransportError),
        (418, LLMProtocolError),
    ],
)
@respx.mock
async def test_http_status_maps_to_error(
    provider: OllamaProvider, status: int, error_type: type
) -> None:
    respx.post(_CHAT_URL).mock(return_value=httpx.Response(status, json={"error": "nope"}))
    with pytest.raises(error_type):
        await _drain(provider)


@respx.mock
async def test_read_timeout_is_mapped_and_not_retried(provider: OllamaProvider) -> None:
    route = respx.post(_CHAT_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(LLMTimeoutError):
        await _drain(provider)
    assert route.call_count == 1  # not a connect error -> no retry


@respx.mock
async def test_connect_error_retries_then_fails(provider: OllamaProvider) -> None:
    # Default max_connect_retries = 2 -> 3 attempts, all failing.
    route = respx.post(_CHAT_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(LLMTransportError):
        await _drain(provider)
    assert route.call_count == 3


@respx.mock
async def test_connect_error_then_success(provider: OllamaProvider) -> None:
    route = respx.post(_CHAT_URL).mock(
        side_effect=[httpx.ConnectError("refused"), httpx.Response(200, content=_SUCCESS_STREAM)]
    )
    chunks = await _drain(provider)
    assert "".join(c.delta for c in chunks) == "Hi!"
    assert route.call_count == 2


@respx.mock
async def test_malformed_json_line_raises_protocol_error(provider: OllamaProvider) -> None:
    respx.post(_CHAT_URL).mock(return_value=httpx.Response(200, content=b"{ not json }\n"))
    with pytest.raises(LLMProtocolError):
        await _drain(provider)


@respx.mock
async def test_mid_stream_error_object_raises_protocol_error(provider: OllamaProvider) -> None:
    stream = (
        b'{"message":{"role":"assistant","content":"par"},"done":false}\n'
        b'{"error":"internal failure"}\n'
    )
    respx.post(_CHAT_URL).mock(return_value=httpx.Response(200, content=stream))
    with pytest.raises(LLMProtocolError):
        await _drain(provider)


@respx.mock
async def test_cancellation_midstream_closes_cleanly(provider: OllamaProvider) -> None:
    respx.post(_CHAT_URL).mock(return_value=httpx.Response(200, content=_SUCCESS_STREAM))
    request = CompletionRequest(messages=(ChatMessage.user("hello"),))
    received = 0
    async for _chunk in provider.stream_chat(request):
        received += 1
        break  # abandon early; must not raise
    assert received == 1


@respx.mock
async def test_no_connect_retry_when_disabled() -> None:
    instance = OllamaProvider(_settings(max_connect_retries=0))
    try:
        route = respx.post(_CHAT_URL).mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(LLMTransportError):
            await _drain(instance)
        assert route.call_count == 1
    finally:
        await instance.aclose()


def test_capabilities_report_streaming_and_usage(provider: OllamaProvider) -> None:
    caps = provider.capabilities()
    assert caps.supports_streaming is True
    assert caps.supports_system_prompt is True
    assert caps.reports_token_usage is True
