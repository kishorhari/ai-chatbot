"""Unit tests for retrieval VOs, the error taxonomy, and port abstractness (M3.0)."""

from __future__ import annotations

import pytest

from aiplatform.domain.knowledge.errors import (
    DimensionMismatchError,
    KnowledgeDocumentNotFoundError,
    KnowledgeError,
    VectorStoreError,
)
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata
from aiplatform.domain.knowledge.ports import (
    EmbeddingProvider,
    KnowledgeRepository,
    VectorStore,
)
from aiplatform.domain.knowledge.retrieval import RetrievedChunk, RetrievedContext


def _chunk(score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=KnowledgeChunkId.generate(),
        document_id=KnowledgeDocumentId.generate(),
        text="passage",
        metadata=Metadata(),
        score=score,
    )


def test_empty_context() -> None:
    ctx = RetrievedContext.empty("q")
    assert ctx.is_empty
    assert ctx.chunks == ()


def test_context_requires_descending_score_order() -> None:
    with pytest.raises(ValueError, match="descending score"):
        RetrievedContext(query="q", chunks=(_chunk(0.2), _chunk(0.9)))


def test_ordered_sorts_defensively() -> None:
    ctx = RetrievedContext.ordered("q", [_chunk(0.2), _chunk(0.9), _chunk(0.5)])
    assert [round(c.score, 1) for c in ctx.chunks] == [0.9, 0.5, 0.2]
    assert not ctx.is_empty


def test_dimension_mismatch_error_carries_values() -> None:
    err = DimensionMismatchError(expected=768, actual=384)
    assert isinstance(err, KnowledgeError)
    assert err.expected == 768
    assert err.actual == 384


def test_not_found_error_is_a_knowledge_error() -> None:
    cid = KnowledgeDocumentId.generate()
    err = KnowledgeDocumentNotFoundError(cid)
    assert isinstance(err, KnowledgeError)
    assert err.document_id == cid
    assert str(cid) in str(err)


def test_vector_store_error_hierarchy() -> None:
    assert issubclass(VectorStoreError, KnowledgeError)


@pytest.mark.parametrize("port", [EmbeddingProvider, VectorStore, KnowledgeRepository])
def test_ports_cannot_be_instantiated(port: type) -> None:
    with pytest.raises(TypeError):
        port()  # type: ignore[abstract]
