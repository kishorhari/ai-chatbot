"""Unit tests for RetrievalService policy (M3.4)."""

from __future__ import annotations

import pytest

from aiplatform.application.knowledge.retrieval_service import RetrievalService
from aiplatform.application.knowledge.retriever import Retriever
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter
from aiplatform.domain.knowledge.retrieval import RetrievedChunk, RetrievedContext


class _StubRetriever(Retriever):
    """Records the arguments it was called with and returns a fixed context."""

    def __init__(self, context: RetrievedContext) -> None:
        self._context = context
        self.calls: list[tuple[str, int, MetadataFilter]] = []

    async def retrieve(self, query: str, *, k: int, filter: MetadataFilter) -> RetrievedContext:
        self.calls.append((query, k, filter))
        return self._context


def _chunk(score: float, text: str = "t") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=KnowledgeChunkId.generate(),
        document_id=KnowledgeDocumentId.generate(),
        text=text,
        metadata=Metadata(),
        score=score,
    )


def _context(*scores: float) -> RetrievedContext:
    return RetrievedContext.ordered("q", [_chunk(s) for s in scores])


async def test_uses_default_k_and_empty_filter() -> None:
    stub = _StubRetriever(_context(0.9))
    service = RetrievalService(stub, default_k=7)
    await service.search("query")
    query, k, filter_ = stub.calls[0]
    assert query == "query"
    assert k == 7
    assert filter_.is_empty


async def test_explicit_k_and_filter_are_forwarded() -> None:
    stub = _StubRetriever(_context(0.9))
    service = RetrievalService(stub)
    f = MetadataFilter(equals=(("lang", "en"),))
    await service.search("q", k=2, filter=f)
    _, k, forwarded = stub.calls[0]
    assert k == 2
    assert forwarded is f


async def test_threshold_drops_low_scoring_chunks() -> None:
    stub = _StubRetriever(_context(0.9, 0.5, 0.1))
    service = RetrievalService(stub, min_score=0.4)
    context = await service.search("q")
    assert [round(c.score, 1) for c in context.chunks] == [0.9, 0.5]


async def test_threshold_can_be_disabled() -> None:
    stub = _StubRetriever(_context(0.9, -0.2, -0.8))
    service = RetrievalService(stub, min_score=-1.0)
    context = await service.search("q")
    assert len(context.chunks) == 3


async def test_result_preserves_descending_order() -> None:
    stub = _StubRetriever(_context(0.9, 0.7, 0.5))
    context = await RetrievalService(stub, min_score=0.0).search("q")
    scores = [c.score for c in context.chunks]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize(("default_k", "min_score"), [(0, 0.0), (-1, 0.0), (5, 1.5), (5, -2.0)])
def test_invalid_policy_is_rejected(default_k: int, min_score: float) -> None:
    with pytest.raises(ValueError):
        RetrievalService(_StubRetriever(_context()), default_k=default_k, min_score=min_score)
