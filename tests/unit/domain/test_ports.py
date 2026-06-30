"""Unit tests for the LLMProvider port's derived behaviour (M1.2-c).

The full behavioural contract is verified by the shared provider contract suite
(M1.3) against real implementations. Here we test only the logic that lives *in*
the port itself: the default-derived ``complete_chat`` and abstractness.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from aiplatform.domain.llm.capabilities import ProviderCapabilities
from aiplatform.domain.llm.messages import ChatMessage
from aiplatform.domain.llm.ports import LLMProvider
from aiplatform.domain.llm.requests import CompletionRequest
from aiplatform.domain.llm.responses import CompletionChunk, FinishReason, TokenUsage


class _FakeProvider(LLMProvider):
    """Minimal provider yielding three chunks, for exercising the port default."""

    async def stream_chat(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        yield CompletionChunk(delta="Hel")
        yield CompletionChunk(delta="lo")
        yield CompletionChunk(
            delta="!",
            is_final=True,
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(prompt_tokens=1, completion_tokens=2),
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            model="fake-default-model",
            supports_streaming=True,
            supports_system_prompt=True,
            reports_token_usage=True,
        )


def _request(model: str | None = None) -> CompletionRequest:
    return CompletionRequest(messages=(ChatMessage.user("hi"),), model=model)


def test_port_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


async def test_complete_chat_concatenates_stream() -> None:
    result = await _FakeProvider().complete_chat(_request())
    assert result.text == "Hello!"
    assert result.finish_reason is FinishReason.STOP
    assert result.usage.total_tokens == 3


async def test_complete_chat_uses_capability_model_when_request_has_no_override() -> None:
    result = await _FakeProvider().complete_chat(_request(model=None))
    assert result.model == "fake-default-model"


async def test_complete_chat_honours_request_model_override() -> None:
    result = await _FakeProvider().complete_chat(_request(model="explicit-model"))
    assert result.model == "explicit-model"
