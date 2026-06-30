"""The ``LLMProvider`` port — the provider-agnostic generation contract.

Streaming is the canonical operation (ADR-0003): every adapter implements
``stream_chat``; ``complete_chat`` is *derived* here by aggregating the stream,
and an adapter may override it to use a cheaper one-shot endpoint. The port
speaks exclusively in domain value objects and raises only ``LLMError`` subtypes
(ADR-0002) — no vendor or transport concept appears in this module.

It is defined as an abstract base class rather than a ``Protocol`` precisely so
the derived ``complete_chat`` can live here once (rule 21) and be inherited by
every adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from .capabilities import ProviderCapabilities
from .requests import CompletionRequest
from .responses import CompletionChunk, CompletionResult


class LLMProvider(ABC):
    """Abstract port for language-model text generation.

    Implementations must satisfy the shared provider contract suite, which is the
    operational definition of "the abstraction is real" (ADR-0004).
    """

    @abstractmethod
    def stream_chat(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        """Stream a completion as an ordered sequence of chunks.

        Contract (asserted by the provider contract suite):

        * Yields at least one chunk and terminates in **exactly one** chunk with
          ``is_final=True``.
        * Is **cancellable**: if the consumer stops iterating, the implementation
          releases any upstream resources and raises nothing (ADR-0003).
        * Raises **only** ``LLMError`` subtypes — no transport-native exception
          escapes, even when the failure occurs after some chunks were yielded
          (in which case the partial output is provisional and must be discarded).

        Args:
            request: The conversation and generation parameters.

        Returns:
            An async iterator over the generated chunks.
        """

    async def complete_chat(self, request: CompletionRequest) -> CompletionResult:
        """Aggregate ``stream_chat`` into a single result (default-derived).

        Consumes the entire stream and concatenates the deltas. Because
        :meth:`CompletionResult.from_chunks` requires a terminal chunk, a stream
        that fails mid-way raises (propagating the ``LLMError``) rather than
        producing a misleadingly complete result.

        Override this to call a provider's one-shot/non-streaming endpoint when
        that is cheaper.

        Args:
            request: The conversation and generation parameters.

        Returns:
            The aggregated completion result.
        """
        chunks = [chunk async for chunk in self.stream_chat(request)]
        model = request.model or self.capabilities().model
        return CompletionResult.from_chunks(chunks, model=model)

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return static capability metadata.

        Must perform **no I/O** — capabilities are declared, not probed (ADR-0003).
        """
