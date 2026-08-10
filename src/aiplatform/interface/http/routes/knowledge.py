"""Knowledge endpoints — document ingestion and retrieval (debug) search.

Thin delivery (ADR-0010): each handler parses transport input, calls one wired
knowledge service resolved from the composition root, and maps the result to a
wire model. When the knowledge feature is disabled (``AIP__KNOWLEDGE__ENABLED``
off) the container exposes no knowledge services and these endpoints report 503 —
the chat surface is then exactly M2.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from aiplatform.composition.container import KnowledgeComponents
from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter, MetadataValue
from aiplatform.domain.knowledge.retrieval import RetrievedChunk

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# --- wire models ------------------------------------------------------------


class IngestRequest(BaseModel):
    """Body for ingesting a document."""

    source: str = Field(min_length=1)
    text: str = Field(min_length=1)
    metadata: dict[str, MetadataValue] | None = None


class IngestResponse(BaseModel):
    """The result of ingesting a document."""

    document_id: str
    source: str
    chunk_count: int


class SearchRequest(BaseModel):
    """Body for a retrieval query."""

    query: str = Field(min_length=1)
    k: int | None = Field(default=None, gt=0)
    metadata: dict[str, MetadataValue] | None = None


class RetrievedChunkResponse(BaseModel):
    """A single retrieved chunk on the wire."""

    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: dict[str, MetadataValue]


class SearchResponse(BaseModel):
    """A retrieval result on the wire."""

    query: str
    chunks: list[RetrievedChunkResponse]


# --- endpoints --------------------------------------------------------------


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def ingest_document(body: IngestRequest, request: Request) -> IngestResponse:
    """Ingest a document: chunk, embed, and persist record + vectors."""
    service = _knowledge(request).indexing_service
    try:
        result = await service.index(
            source=body.source, text=body.text, metadata=Metadata.of(body.metadata)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return IngestResponse(
        document_id=str(result.document_id), source=result.source, chunk_count=result.chunk_count
    )


@router.post("/search")
async def search_knowledge(body: SearchRequest, request: Request) -> SearchResponse:
    """Retrieve the knowledge relevant to a query (a debug/inspection endpoint)."""
    service = _knowledge(request).retrieval_service
    metadata_filter = (
        MetadataFilter(equals=tuple(body.metadata.items()))
        if body.metadata
        else MetadataFilter.none()
    )
    context = await service.search(body.query, k=body.k, filter=metadata_filter)
    return SearchResponse(
        query=context.query, chunks=[_chunk_response(chunk) for chunk in context.chunks]
    )


# --- composition-resolved services -----------------------------------------


def _knowledge(request: Request) -> KnowledgeComponents:
    """Resolve the wired knowledge services, or 503 when unavailable/disabled."""
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="service not ready"
        )
    knowledge = container.knowledge
    if knowledge is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="knowledge feature is disabled",
        )
    return knowledge


def _chunk_response(chunk: RetrievedChunk) -> RetrievedChunkResponse:
    """Map a retrieved chunk to its wire form."""
    return RetrievedChunkResponse(
        chunk_id=str(chunk.chunk_id),
        document_id=str(chunk.document_id),
        text=chunk.text,
        score=chunk.score,
        metadata=chunk.metadata.as_dict(),
    )
