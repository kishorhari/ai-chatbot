"""The shared VectorStore contract suite (ADR-0013).

A single behavioural specification every ``VectorStore`` implementation must
satisfy. Backends opt in by subclassing :class:`VectorStoreContract` and
overriding the ``store`` fixture. The ``InMemoryVectorStore`` (M3.2) and the
pgvector store (M3.7) passing this identical suite is the executable proof the
vector-search swap is real — mirroring the provider and repository suites.

The metric is cosine (fixed by the contract), so tests use hand-chosen vectors
with distinct similarities and assert ordering, ``k`` bounding, metadata
filtering, delete-by-document, upsert-by-chunk-id semantics, payload fidelity, and
dimension validation. Ties are avoided so ordering is backend-independent.

Not named ``test_*`` so pytest collects only the ``Test*`` subclasses.
"""

from __future__ import annotations

import math

import pytest

from aiplatform.domain.knowledge.errors import DimensionMismatchError
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter
from aiplatform.domain.knowledge.ports import VectorEntry, VectorStore
from aiplatform.domain.knowledge.vectors import EmbeddingVector

_DOC_A = KnowledgeDocumentId.generate()
_DOC_B = KnowledgeDocumentId.generate()


def _entry(
    vector: tuple[float, ...],
    *,
    document_id: KnowledgeDocumentId = _DOC_A,
    text: str = "passage",
    metadata: Metadata | None = None,
    chunk_id: KnowledgeChunkId | None = None,
) -> VectorEntry:
    return VectorEntry(
        chunk_id=chunk_id or KnowledgeChunkId.generate(),
        document_id=document_id,
        vector=EmbeddingVector(vector),
        text=text,
        metadata=metadata if metadata is not None else Metadata(),
    )


class VectorStoreContract:
    """Behavioural invariants every ``VectorStore`` must satisfy."""

    @pytest.fixture
    def store(self) -> VectorStore:
        """The store under test. Subclasses MUST override this."""
        raise NotImplementedError("contract subclasses must provide a `store` fixture")

    async def test_upsert_then_search_returns_the_entry(self, store: VectorStore) -> None:
        entry = _entry((1.0, 0.0, 0.0), text="hello")
        await store.upsert([entry])
        matches = await store.search(
            EmbeddingVector((1.0, 0.0, 0.0)), k=1, filter=MetadataFilter.none()
        )
        assert len(matches) == 1
        assert matches[0].chunk_id == entry.chunk_id
        assert matches[0].text == "hello"
        assert math.isclose(matches[0].score, 1.0)

    async def test_empty_store_returns_no_matches(self, store: VectorStore) -> None:
        matches = await store.search(EmbeddingVector((1.0, 0.0)), k=5, filter=MetadataFilter.none())
        assert matches == []

    async def test_results_are_ordered_by_descending_similarity(self, store: VectorStore) -> None:
        near = _entry((1.0, 0.0, 0.0), text="near")
        mid = _entry((0.8, 0.6, 0.0), text="mid")
        far = _entry((0.0, 1.0, 0.0), text="far")
        await store.upsert([far, near, mid])  # deliberately out of order
        matches = await store.search(
            EmbeddingVector((1.0, 0.0, 0.0)), k=3, filter=MetadataFilter.none()
        )
        assert [m.text for m in matches] == ["near", "mid", "far"]
        assert matches[0].score >= matches[1].score >= matches[2].score

    async def test_k_bounds_the_number_of_results(self, store: VectorStore) -> None:
        await store.upsert(
            [_entry((1.0, 0.0, 0.0)), _entry((0.9, 0.1, 0.0)), _entry((0.0, 0.0, 1.0))]
        )
        matches = await store.search(
            EmbeddingVector((1.0, 0.0, 0.0)), k=2, filter=MetadataFilter.none()
        )
        assert len(matches) == 2

    async def test_metadata_filter_restricts_results(self, store: VectorStore) -> None:
        en = _entry((1.0, 0.0), text="english", metadata=Metadata.of({"lang": "en"}))
        fr = _entry((1.0, 0.0), text="french", metadata=Metadata.of({"lang": "fr"}))
        await store.upsert([en, fr])
        matches = await store.search(
            EmbeddingVector((1.0, 0.0)), k=10, filter=MetadataFilter(equals=(("lang", "en"),))
        )
        assert [m.text for m in matches] == ["english"]

    async def test_delete_removes_only_that_documents_vectors(self, store: VectorStore) -> None:
        a = _entry((1.0, 0.0), document_id=_DOC_A, text="a")
        b = _entry((1.0, 0.0), document_id=_DOC_B, text="b")
        await store.upsert([a, b])
        await store.delete(_DOC_A)
        matches = await store.search(
            EmbeddingVector((1.0, 0.0)), k=10, filter=MetadataFilter.none()
        )
        assert [m.text for m in matches] == ["b"]
        assert matches[0].document_id == _DOC_B

    async def test_delete_is_idempotent(self, store: VectorStore) -> None:
        await store.delete(KnowledgeDocumentId.generate())  # nothing stored → no error

    async def test_upsert_replaces_by_chunk_id(self, store: VectorStore) -> None:
        chunk_id = KnowledgeChunkId.generate()
        await store.upsert([_entry((1.0, 0.0), text="old", chunk_id=chunk_id)])
        await store.upsert([_entry((0.0, 1.0), text="new", chunk_id=chunk_id)])
        matches = await store.search(
            EmbeddingVector((0.0, 1.0)), k=10, filter=MetadataFilter.none()
        )
        assert len(matches) == 1
        assert matches[0].text == "new"

    async def test_matches_carry_full_payload(self, store: VectorStore) -> None:
        entry = _entry(
            (1.0, 0.0),
            document_id=_DOC_B,
            text="payload",
            metadata=Metadata.of({"title": "T"}),
        )
        await store.upsert([entry])
        match = (
            await store.search(EmbeddingVector((1.0, 0.0)), k=1, filter=MetadataFilter.none())
        )[0]
        assert match.chunk_id == entry.chunk_id
        assert match.document_id == _DOC_B
        assert match.text == "payload"
        assert match.metadata.get("title") == "T"

    async def test_dimension_mismatch_on_query_is_rejected(self, store: VectorStore) -> None:
        await store.upsert([_entry((1.0, 0.0, 0.0))])  # establishes dimension 3
        with pytest.raises(DimensionMismatchError):
            await store.search(EmbeddingVector((1.0, 0.0)), k=1, filter=MetadataFilter.none())

    async def test_dimension_mismatch_on_upsert_is_rejected(self, store: VectorStore) -> None:
        await store.upsert([_entry((1.0, 0.0, 0.0))])  # establishes dimension 3
        with pytest.raises(DimensionMismatchError):
            await store.upsert([_entry((1.0, 0.0))])  # dimension 2
