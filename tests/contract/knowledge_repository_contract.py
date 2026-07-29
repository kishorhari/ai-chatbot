"""The shared KnowledgeRepository contract suite (ADR-0016).

A single behavioural specification every ``KnowledgeRepository`` implementation
must satisfy. Backends opt in by subclassing :class:`KnowledgeRepositoryContract`
and overriding the ``repository`` fixture. The in-memory repository (M3.3) and the
SQLAlchemy/pgvector repository (M3.7) passing this identical suite proves the
record-store swap — mirroring the conversation repository suite.

The knowledge document is add-once (ingestion writes it whole; there is no
incremental ``save``), so the suite covers add/get/delete/list, not-found and
already-exists semantics, ordering, metadata-filtered listing, and snapshot
independence. Not named ``test_*`` so only ``Test*`` subclasses are collected.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aiplatform.domain.knowledge.document import IngestionStatus, KnowledgeDocument
from aiplatform.domain.knowledge.errors import (
    KnowledgeDocumentAlreadyExistsError,
    KnowledgeDocumentNotFoundError,
)
from aiplatform.domain.knowledge.ids import KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter
from aiplatform.domain.knowledge.ports import KnowledgeRepository

_TS = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def _document(
    *,
    source: str = "handbook.md",
    metadata: Metadata | None = None,
    with_chunks: bool = True,
    status: IngestionStatus = IngestionStatus.INDEXED,
) -> KnowledgeDocument:
    doc = KnowledgeDocument.start(source=source, created_at=_TS, metadata=metadata)
    if with_chunks:
        doc.add_chunk("first chunk", metadata=metadata or Metadata(), token_count=3)
        doc.add_chunk("second chunk", metadata=metadata or Metadata(), token_count=3)
    if status is IngestionStatus.INDEXED:
        doc.mark_indexed()
    return doc


class KnowledgeRepositoryContract:
    """Behavioural invariants every ``KnowledgeRepository`` must satisfy."""

    @pytest.fixture
    def repository(self) -> KnowledgeRepository:
        """The repository under test. Subclasses MUST override this."""
        raise NotImplementedError("contract subclasses must provide a `repository` fixture")

    async def test_add_then_get_round_trips(self, repository: KnowledgeRepository) -> None:
        original = _document(metadata=Metadata.of({"lang": "en"}))
        await repository.add(original)

        loaded = await repository.get(original.id)
        assert loaded.id == original.id
        assert loaded.source == original.source
        assert loaded.created_at == original.created_at
        assert loaded.metadata == original.metadata
        assert loaded.status is IngestionStatus.INDEXED
        assert [c.text for c in loaded.chunks] == ["first chunk", "second chunk"]
        assert [c.ordinal for c in loaded.chunks] == [0, 1]
        assert loaded.chunks[0].token_count == 3

    async def test_get_unknown_raises_not_found(self, repository: KnowledgeRepository) -> None:
        with pytest.raises(KnowledgeDocumentNotFoundError):
            await repository.get(KnowledgeDocumentId.generate())

    async def test_add_duplicate_raises_already_exists(
        self, repository: KnowledgeRepository
    ) -> None:
        doc = _document()
        await repository.add(doc)
        with pytest.raises(KnowledgeDocumentAlreadyExistsError):
            await repository.add(doc)

    async def test_delete_removes_document(self, repository: KnowledgeRepository) -> None:
        doc = _document()
        await repository.add(doc)
        await repository.delete(doc.id)
        with pytest.raises(KnowledgeDocumentNotFoundError):
            await repository.get(doc.id)

    async def test_delete_unknown_raises_not_found(self, repository: KnowledgeRepository) -> None:
        with pytest.raises(KnowledgeDocumentNotFoundError):
            await repository.delete(KnowledgeDocumentId.generate())

    async def test_list_returns_all_with_empty_filter(
        self, repository: KnowledgeRepository
    ) -> None:
        await repository.add(_document(source="a.md"))
        await repository.add(_document(source="b.md"))
        listed = await repository.list(MetadataFilter.none())
        assert {d.source for d in listed} == {"a.md", "b.md"}

    async def test_list_applies_metadata_filter(self, repository: KnowledgeRepository) -> None:
        await repository.add(_document(source="en.md", metadata=Metadata.of({"lang": "en"})))
        await repository.add(_document(source="fr.md", metadata=Metadata.of({"lang": "fr"})))
        listed = await repository.list(MetadataFilter(equals=(("lang", "en"),)))
        assert [d.source for d in listed] == ["en.md"]

    async def test_documents_are_isolated(self, repository: KnowledgeRepository) -> None:
        a = _document(source="a.md")
        b = _document(source="b.md", with_chunks=False, status=IngestionStatus.PENDING)
        await repository.add(a)
        await repository.add(b)
        loaded_b = await repository.get(b.id)
        assert loaded_b.chunk_count == 0
        assert loaded_b.status is IngestionStatus.PENDING

    async def test_unsaved_mutation_of_loaded_copy_is_not_persisted(
        self, repository: KnowledgeRepository
    ) -> None:
        doc = _document()
        await repository.add(doc)
        first = await repository.get(doc.id)
        first.add_chunk("leaked?", token_count=1)  # mutate loaded copy; no re-add
        second = await repository.get(doc.id)
        assert second.chunk_count == 2  # storage unaffected

    async def test_get_returns_independent_instances(self, repository: KnowledgeRepository) -> None:
        doc = _document()
        await repository.add(doc)
        a = await repository.get(doc.id)
        b = await repository.get(doc.id)
        assert a is not b
        a.add_chunk("only in a", token_count=1)
        assert b.chunk_count == 2
