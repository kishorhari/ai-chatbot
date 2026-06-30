"""Opt-in live integration tests against a real Ollama server (M1.7).

These are excluded from default/CI runs (the testing strategy marks live
provider verification as nightly/pre-release, not mandatory). Run explicitly::

    AIP__OLLAMA__BASE_URL=http://localhost:11434 \
    AIP__OLLAMA__MODEL=llama3 \
    pytest -m live

Assertions are limited to the *structural* contract invariants (terminal chunk,
non-empty text, usage, cancellation). Cross-call equality is deliberately NOT
asserted here because a live model is non-deterministic — that exact-equality
invariant is proven offline by the shared contract suite against Echo and the
respx-mocked Ollama.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from aiplatform.domain.llm.messages import ChatMessage
from aiplatform.domain.llm.requests import CompletionRequest, GenerationParams
from aiplatform.infrastructure.config.settings import load_settings
from aiplatform.infrastructure.llm.ollama.adapter import OllamaProvider

pytestmark = pytest.mark.live


@pytest_asyncio.fixture
async def provider() -> AsyncIterator[OllamaProvider]:
    """A real OllamaProvider built from environment configuration."""
    instance = OllamaProvider(load_settings().ollama)
    yield instance
    await instance.aclose()


async def test_live_stream_terminates_with_a_final_chunk(provider: OllamaProvider) -> None:
    request = CompletionRequest(
        messages=(ChatMessage.user("Reply with a short greeting."),),
        params=GenerationParams(temperature=0.0, max_tokens=64),
    )
    chunks = [chunk async for chunk in provider.stream_chat(request)]
    assert len(chunks) >= 1
    assert sum(1 for chunk in chunks if chunk.is_final) == 1
    assert chunks[-1].is_final is True
    assert "".join(chunk.delta for chunk in chunks).strip() != ""
    assert chunks[-1].usage is not None


async def test_live_complete_chat_returns_text(provider: OllamaProvider) -> None:
    request = CompletionRequest(
        messages=(ChatMessage.user("Reply with the single word: pong"),),
        params=GenerationParams(temperature=0.0, max_tokens=16),
    )
    result = await provider.complete_chat(request)
    assert result.text.strip() != ""
    assert result.model


async def test_live_cancellation_midstream_raises_nothing(provider: OllamaProvider) -> None:
    request = CompletionRequest(messages=(ChatMessage.user("Count slowly to twenty."),))
    received = 0
    async for _chunk in provider.stream_chat(request):
        received += 1
        break  # abandon early; the underlying HTTP stream must close cleanly
    assert received >= 1
