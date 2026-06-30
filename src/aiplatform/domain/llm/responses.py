"""Response value objects — what a provider yields back.

Streaming is the canonical path (ADR-0003): a generation arrives as a sequence
of ``CompletionChunk`` terminating in exactly one final chunk. ``CompletionResult``
is the aggregated, non-streaming view, derivable purely from those chunks.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, computed_field


class FinishReason(StrEnum):
    """Why generation stopped, normalised to a closed domain set.

    Adapters map vendor-specific reasons onto these values so callers never have
    to string-match a provider's wording (ADR-0002).
    """

    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


class TokenUsage(BaseModel):
    """Token accounting for a generation.

    ``total_tokens`` is derived, so the prompt/completion split can never
    contradict the total.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_tokens(self) -> int:
        """Total tokens consumed (prompt + completion)."""
        return self.prompt_tokens + self.completion_tokens

    @classmethod
    def empty(cls) -> Self:
        """Return a zero-usage instance (e.g. for stub providers)."""
        return cls(prompt_tokens=0, completion_tokens=0)


@dataclass(frozen=True, slots=True)
class CompletionChunk:
    """One increment of a streamed generation.

    Modelled as a slotted, frozen dataclass rather than a pydantic model: chunks
    are produced on the streaming hot path, internally by adapters (not from
    external input), so they want cheap construction over input coercion.

    Invariant: ``finish_reason`` and ``usage`` describe the *completed*
    generation and may only appear on the terminal chunk.

    Attributes:
        delta: The text fragment carried by this chunk (may be empty).
        is_final: True for exactly one terminal chunk per stream.
        finish_reason: Why generation stopped; terminal chunk only.
        usage: Token accounting; terminal chunk only.
    """

    delta: str
    is_final: bool = False
    finish_reason: FinishReason | None = None
    usage: TokenUsage | None = None

    def __post_init__(self) -> None:
        """Enforce the terminal-only invariant for ``finish_reason``/``usage``."""
        if not self.is_final and (self.finish_reason is not None or self.usage is not None):
            raise ValueError("non-final chunk must not carry finish_reason or usage")


class CompletionResult(BaseModel):
    """The aggregated result of a (possibly streamed) generation.

    Attributes:
        text: The full generated text (the concatenation of all chunk deltas).
        model: The model that produced the result.
        finish_reason: Why generation stopped, if reported.
        usage: Token accounting (zero-usage when the provider reports none).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    model: str = Field(min_length=1)
    finish_reason: FinishReason | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage.empty)

    @classmethod
    def from_chunks(cls, chunks: Iterable[CompletionChunk], *, model: str) -> Self:
        """Aggregate a finished stream into a single result.

        Pure aggregation, so the port's derived ``complete_chat`` (ADR-0003) only
        has to drive the async iteration and delegate the joining here — keeping
        the join logic defined exactly once (rule 21).

        Args:
            chunks: The chunks of one stream, in order.
            model: The model that produced them.

        Returns:
            The aggregated :class:`CompletionResult`.

        Raises:
            ValueError: If the stream contained no terminal chunk.
        """
        parts: list[str] = []
        final: CompletionChunk | None = None
        for chunk in chunks:
            parts.append(chunk.delta)
            if chunk.is_final:
                final = chunk
        if final is None:
            raise ValueError("cannot build a result from a stream with no final chunk")
        return cls(
            text="".join(parts),
            model=model,
            finish_reason=final.finish_reason,
            usage=final.usage or TokenUsage.empty(),
        )
