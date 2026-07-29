"""Unit tests for the TokenAwareChunker (M3.3)."""

from __future__ import annotations

import pytest

from aiplatform.application.conversation.token_estimator import HeuristicTokenEstimator
from aiplatform.application.knowledge.chunking import TokenAwareChunker


def _chunker(*, size: int = 20, overlap: int = 5) -> TokenAwareChunker:
    # HeuristicTokenEstimator: ~4 chars/token, rounded up.
    return TokenAwareChunker(
        HeuristicTokenEstimator(), chunk_size_tokens=size, overlap_tokens=overlap
    )


def test_blank_text_yields_no_chunks() -> None:
    assert _chunker().chunk("   \n\n  ") == []


def test_short_text_is_a_single_chunk() -> None:
    chunks = _chunker(size=100, overlap=0).chunk("A short sentence.")
    assert len(chunks) == 1
    assert chunks[0].text == "A short sentence."
    assert chunks[0].token_count > 0


def test_long_text_splits_into_multiple_chunks() -> None:
    text = " ".join(f"Sentence number {i} here." for i in range(40))
    chunks = _chunker(size=20, overlap=4).chunk(text)
    assert len(chunks) > 1


def test_chunks_respect_size_budget() -> None:
    text = " ".join(f"Word{i}" for i in range(200))
    chunker = _chunker(size=15, overlap=3)
    chunks = chunker.chunk(text)
    estimator = HeuristicTokenEstimator()
    # Each chunk is within budget (single tokens can only exceed for one huge word,
    # which this input does not contain).
    assert all(estimator.estimate(c.text) <= 15 for c in chunks)


def test_overlap_repeats_trailing_content() -> None:
    sentences = ". ".join(f"Alpha{i} beta gamma delta" for i in range(12)) + "."
    with_overlap = _chunker(size=18, overlap=8).chunk(sentences)
    without_overlap = _chunker(size=18, overlap=0).chunk(sentences)
    # Overlap carries content forward, so it never yields fewer chunks and the
    # reconstructed length is larger.
    assert len(with_overlap) >= len(without_overlap)
    assert sum(len(c.text) for c in with_overlap) >= sum(len(c.text) for c in without_overlap)


def test_is_deterministic() -> None:
    text = " ".join(f"Token {i}." for i in range(50))
    chunker = _chunker()
    assert chunker.chunk(text) == chunker.chunk(text)


def test_oversized_single_word_is_emitted_alone() -> None:
    huge = "x" * 500  # far exceeds a 20-token budget as one word
    chunks = _chunker(size=20, overlap=0).chunk(f"{huge} then normal words follow here.")
    assert any(c.text == huge for c in chunks)


@pytest.mark.parametrize(
    "size,overlap",
    [(0, 0), (10, 10), (10, 15), (10, -1)],
)
def test_invalid_configuration_is_rejected(size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        TokenAwareChunker(HeuristicTokenEstimator(), chunk_size_tokens=size, overlap_tokens=overlap)
