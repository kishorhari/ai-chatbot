"""Chunking — splitting document text into retrievable units (ADR-0014).

``ChunkingStrategy`` is an **application-layer** port (not domain): chunking is a
processing policy in the use-case layer, like ``ContextWindowPolicy`` and
``PromptAssembler``, and this placement lets it reuse the M2 ``TokenEstimator`` to
size chunks by tokens (a domain port could not depend on it).

The default ``TokenAwareChunker`` is pure and deterministic: it splits text on
natural boundaries (paragraph → sentence → word) into segments, then greedily
packs them into windows targeting ``chunk_size_tokens`` with ``overlap_tokens`` of
trailing context carried into the next window. It performs no embedding, storage,
or I/O — the ``IndexingService`` invokes it and does the rest.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from aiplatform.application.conversation.token_estimator import TokenEstimator

_PARAGRAPH = re.compile(r"\n\s*\n")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """A prospective chunk produced by chunking, before it enters the aggregate.

    Attributes:
        text: The chunk text.
        token_count: The estimator's token count for ``text`` (reused as the
            chunk's recorded ``token_count``, avoiding a second estimation).
    """

    text: str
    token_count: int


class ChunkingStrategy(ABC):
    """Splits document text into ordered ``ChunkDraft``s."""

    @abstractmethod
    def chunk(self, text: str) -> list[ChunkDraft]:
        """Return the ordered chunks of ``text`` (empty for blank input)."""


class TokenAwareChunker(ChunkingStrategy):
    """Greedy, token-aware chunker with overlap (the default strategy)."""

    def __init__(
        self,
        estimator: TokenEstimator,
        *,
        chunk_size_tokens: int = 512,
        overlap_tokens: int = 64,
    ) -> None:
        """Configure the target size and overlap.

        Raises:
            ValueError: If the size is not positive, or the overlap is negative or
                not strictly smaller than the size (overlap must let packing
                progress).
        """
        if chunk_size_tokens <= 0:
            raise ValueError("chunk_size_tokens must be positive")
        if not 0 <= overlap_tokens < chunk_size_tokens:
            raise ValueError("overlap_tokens must be in [0, chunk_size_tokens)")
        self._estimator = estimator
        self._chunk_size = chunk_size_tokens
        self._overlap = overlap_tokens

    def chunk(self, text: str) -> list[ChunkDraft]:
        """Split then greedily pack ``text`` into overlapping token-bounded chunks."""
        segments = self._segments(text)
        if not segments:
            return []

        chunks: list[ChunkDraft] = []
        current: list[str] = []
        current_tokens = 0
        for segment in segments:
            segment_tokens = self._estimator.estimate(segment)
            if current and current_tokens + segment_tokens > self._chunk_size:
                chunks.append(self._emit(current))
                current, current_tokens = self._carry_overlap(current)
            current.append(segment)
            current_tokens += segment_tokens
        if current:
            chunks.append(self._emit(current))
        return chunks

    def _segments(self, text: str) -> list[str]:
        """Split into sentence-ish segments, each within the chunk budget."""
        segments: list[str] = []
        for paragraph in _PARAGRAPH.split(text.strip()):
            for sentence in _SENTENCE.split(paragraph.strip()):
                sentence = sentence.strip()
                if not sentence:
                    continue
                if self._estimator.estimate(sentence) <= self._chunk_size:
                    segments.append(sentence)
                else:
                    segments.extend(self._split_words(sentence))
        return segments

    def _split_words(self, sentence: str) -> list[str]:
        """Split an over-long sentence into word groups within the budget."""
        groups: list[str] = []
        current: list[str] = []
        for word in sentence.split():
            current.append(word)
            if self._estimator.estimate(" ".join(current)) > self._chunk_size:
                if len(current) > 1:
                    current.pop()
                    groups.append(" ".join(current))
                    current = [word]
                else:  # a single word exceeds the budget (degenerate); emit alone
                    groups.append(word)
                    current = []
        if current:
            groups.append(" ".join(current))
        return groups

    def _emit(self, segments: list[str]) -> ChunkDraft:
        """Join accumulated segments into a chunk draft."""
        text = " ".join(segments)
        return ChunkDraft(text=text, token_count=self._estimator.estimate(text))

    def _carry_overlap(self, segments: list[str]) -> tuple[list[str], int]:
        """Return the trailing segments (and their token sum) to overlap into the next chunk."""
        if self._overlap == 0:
            return [], 0
        carried: list[str] = []
        tokens = 0
        for segment in reversed(segments):
            segment_tokens = self._estimator.estimate(segment)
            if tokens + segment_tokens > self._overlap:
                break
            carried.insert(0, segment)
            tokens += segment_tokens
        return carried, tokens
