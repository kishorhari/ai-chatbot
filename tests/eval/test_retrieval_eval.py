"""Milestone 3 retrieval quality gate (roadmap §7, criterion 8).

Wires the **offline** RAG path exactly as the composition root does when
``embedding=fake`` and ``vector=memory`` — ``FakeEmbeddingProvider`` +
``InMemoryVectorStore`` + ``InMemoryKnowledgeRepository`` +
``IndexingService`` / ``SemanticRetriever`` / ``RetrievalService`` — indexes the
committed golden corpus, runs every labelled query, and asserts the aggregate
metrics clear a declared threshold. Because the whole path is deterministic and
network-free, this is a stable acceptance test, not a flaky benchmark.

The harness reuses the production application services unchanged — it introduces
no evaluation code into ``src`` — so what it measures is the real retrieval
mechanism, not a test-only reimplementation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

import pytest_asyncio
from golden_dataset import (
    GOLDEN_DOCUMENTS,
    GOLDEN_QUERIES,
    EvaluationReport,
    build_report,
    evaluate_query,
)

from aiplatform.application.conversation.token_estimator import HeuristicTokenEstimator
from aiplatform.application.knowledge.chunking import TokenAwareChunker
from aiplatform.application.knowledge.indexing_service import IndexingService
from aiplatform.application.knowledge.retrieval_service import RetrievalService
from aiplatform.application.knowledge.semantic_retriever import SemanticRetriever
from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter
from aiplatform.domain.knowledge.retrieval import RetrievedContext
from aiplatform.infrastructure.clock import SystemClock
from aiplatform.infrastructure.knowledge.embedding.fake.adapter import FakeEmbeddingProvider
from aiplatform.infrastructure.knowledge.repository.memory.repository import (
    InMemoryKnowledgeRepository,
)
from aiplatform.infrastructure.knowledge.vector.memory.store import InMemoryVectorStore

# --- Declared gate ---------------------------------------------------------
# The offline lexical path is expected to rank each topic's own document first
# on this deliberately-separable corpus. The gate is set just below a perfect
# run so an accidental regression fails while leaving no illusion of semantic
# quality (the fake embedding is lexical by construction).
K = 3
MIN_MEAN_RECALL_AT_K = 1.0
MIN_HIT_RATE_AT_K = 1.0
MIN_MRR = 0.95


class _OfflineRag:
    """The wired offline RAG path (indexing + retrieval over one shared store)."""

    def __init__(self) -> None:
        embedder = FakeEmbeddingProvider(dimension=256)
        vector_store = InMemoryVectorStore()
        repository = InMemoryKnowledgeRepository()
        chunker = TokenAwareChunker(HeuristicTokenEstimator())
        self.indexing = IndexingService(
            chunker=chunker,
            embedder=embedder,
            repository=repository,
            vector_store=vector_store,
            clock=SystemClock(),
        )
        self.retrieval = RetrievalService(
            SemanticRetriever(embedder=embedder, vector_store=vector_store),
            default_k=K,
            min_score=-1.0,  # rank-only evaluation; thresholding is tested elsewhere
        )

    async def index_all(self) -> None:
        for document in GOLDEN_DOCUMENTS:
            await self.indexing.index(
                source=document.source,
                text=document.text,
                metadata=Metadata.of({"topic": document.topic, "source": document.source}),
            )

    async def ranked_sources(
        self, query: str, *, k: int = K, filter: MetadataFilter | None = None
    ) -> tuple[str, ...]:
        context = await self.retrieval.search(query, k=k, filter=filter)
        return _sources_in_order(context)


def _sources_in_order(context: RetrievedContext) -> tuple[str, ...]:
    """Distinct document sources in retrieved order (most-relevant first)."""
    ordered: list[str] = []
    for chunk in context.chunks:
        source = chunk.metadata.get("source")
        if isinstance(source, str) and source not in ordered:
            ordered.append(source)
    return tuple(ordered)


@pytest_asyncio.fixture
async def rag() -> AsyncIterator[_OfflineRag]:
    harness = _OfflineRag()
    await harness.index_all()
    yield harness


async def _report(rag: _OfflineRag, *, k: int = K) -> EvaluationReport:
    evaluations = [
        evaluate_query(
            query=q.query,
            relevant=q.relevant_sources,
            retrieved=await rag.ranked_sources(q.query, k=k),
            k=k,
        )
        for q in GOLDEN_QUERIES
    ]
    return build_report(evaluations, k=k)


async def test_recall_at_k_meets_declared_gate(rag: _OfflineRag) -> None:
    report = await _report(rag)
    misses = [(e.query, e.retrieved) for e in report.misses()]
    assert report.mean_recall_at_k >= MIN_MEAN_RECALL_AT_K, f"misses: {misses}"


async def test_hit_rate_and_mrr_meet_declared_gate(rag: _OfflineRag) -> None:
    report = await _report(rag)
    assert report.hit_rate_at_k >= MIN_HIT_RATE_AT_K
    assert report.mean_reciprocal_rank >= MIN_MRR


async def test_top_1_is_a_relevant_document_for_every_query(rag: _OfflineRag) -> None:
    # Retrieval correctness: the single best-ranked source is a labelled answer.
    for q in GOLDEN_QUERIES:
        ranked = await rag.ranked_sources(q.query, k=1)
        assert ranked, f"no result for {q.query!r}"
        assert ranked[0] in q.relevant_sources, f"{q.query!r} -> {ranked[0]}"


async def test_metadata_filter_restricts_to_matching_topic(rag: _OfflineRag) -> None:
    # A filtered query returns only chunks whose topic matches the filter — the
    # science-topic filter must exclude the business document even for a query
    # that mentions a company.
    business_query = "ownership of a company and its profits"
    unfiltered = await rag.ranked_sources(business_query, k=6)
    assert "finance.md" in unfiltered

    science_only = MetadataFilter(equals=(("topic", "science"),))
    filtered = await rag.ranked_sources(business_query, k=6, filter=science_only)
    assert filtered, "science filter returned nothing"
    assert "finance.md" not in filtered
    assert _all_science(filtered)


def _all_science(sources: Iterable[str]) -> bool:
    science = {d.source for d in GOLDEN_DOCUMENTS if d.topic == "science"}
    return all(source in science for source in sources)


async def test_offline_retrieval_is_deterministic(rag: _OfflineRag) -> None:
    # Two identical runs against the same store return identical rankings — the
    # property that makes this a stable gate rather than a benchmark.
    first = await rag.ranked_sources(GOLDEN_QUERIES[0].query, k=6)
    second = await rag.ranked_sources(GOLDEN_QUERIES[0].query, k=6)
    assert first == second


async def test_a_fresh_index_reproduces_the_same_ranking() -> None:
    # Determinism across independent indexings (fresh stores), not just repeated
    # queries against one store — the reproducibility the committed gate relies on.
    query = GOLDEN_QUERIES[3].query
    run_one = _OfflineRag()
    await run_one.index_all()
    run_two = _OfflineRag()
    await run_two.index_all()
    assert await run_one.ranked_sources(query, k=6) == await run_two.ranked_sources(query, k=6)
