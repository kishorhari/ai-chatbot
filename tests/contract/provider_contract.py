"""The shared LLMProvider contract suite (ADR-0004 / testing-strategy).

A single behavioural specification that **every** ``LLMProvider`` implementation
must satisfy. Concrete providers opt in by subclassing :class:`LLMProviderContract`
and overriding the ``provider`` fixture; the inherited tests then run against that
implementation. Two independent providers passing this identical suite is the
operational proof that the abstraction is real and not "Ollama-shaped".

This module is intentionally **not** named ``test_*`` so pytest does not collect
the base class directly — only the ``Test*`` subclasses are collected.

Scope: this suite asserts the universal, provider-independent invariants
(ordering/terminal chunk, aggregation, cancellation, capability purity). The
mapping of *failures* to ``LLMError`` subtypes is provider-specific fault
injection and is verified in each adapter's own tests (e.g. the Ollama respx
tests in M1.4), not here, since Echo has no failure modes to simulate.
"""

from __future__ import annotations

import pytest

from aiplatform.domain.llm.capabilities import ProviderCapabilities
from aiplatform.domain.llm.messages import ChatMessage
from aiplatform.domain.llm.ports import LLMProvider
from aiplatform.domain.llm.requests import CompletionRequest, GenerationParams


class LLMProviderContract:
    """Behavioural invariants every ``LLMProvider`` implementation must satisfy."""

    @pytest.fixture
    def provider(self) -> LLMProvider:
        """The provider under test. Subclasses MUST override this."""
        raise NotImplementedError("contract subclasses must provide a `provider` fixture")

    @pytest.fixture
    def chat_request(self) -> CompletionRequest:
        """A deterministic request (fixed seed) usable by every provider."""
        return CompletionRequest(
            messages=(
                ChatMessage.system("You are a test fixture."),
                ChatMessage.user("Hello there, general kenobi"),
            ),
            params=GenerationParams(seed=42),
        )

    async def test_stream_terminates_with_exactly_one_final_chunk(
        self, provider: LLMProvider, chat_request: CompletionRequest
    ) -> None:
        chunks = [chunk async for chunk in provider.stream_chat(chat_request)]
        assert len(chunks) >= 1
        assert sum(1 for chunk in chunks if chunk.is_final) == 1
        assert chunks[-1].is_final is True
        assert all(not chunk.is_final for chunk in chunks[:-1])

    async def test_complete_chat_equals_joined_stream_deltas(
        self, provider: LLMProvider, chat_request: CompletionRequest
    ) -> None:
        joined = "".join([chunk.delta async for chunk in provider.stream_chat(chat_request)])
        result = await provider.complete_chat(chat_request)
        assert result.text == joined

    async def test_terminal_chunk_carries_usage(
        self, provider: LLMProvider, chat_request: CompletionRequest
    ) -> None:
        chunks = [chunk async for chunk in provider.stream_chat(chat_request)]
        assert chunks[-1].usage is not None

    async def test_cancellation_midstream_raises_nothing(
        self, provider: LLMProvider, chat_request: CompletionRequest
    ) -> None:
        received = 0
        async for _chunk in provider.stream_chat(chat_request):
            received += 1
            break  # abandon the stream early; the iterator must close cleanly
        assert received >= 1

    def test_capabilities_are_pure_and_consistent(self, provider: LLMProvider) -> None:
        first = provider.capabilities()
        second = provider.capabilities()
        assert isinstance(first, ProviderCapabilities)
        assert first == second  # deterministic; no hidden per-call I/O or state
        assert first.supports_streaming is True  # streaming-first port (ADR-0003)
