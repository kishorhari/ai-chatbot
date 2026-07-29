# ADR-0016: Knowledge Metadata, Ingestion & Persistence

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0007 (Aggregate design), ADR-0008 (Persistence & contract suite), ADR-0011 (Knowledge & Retrieval Architecture), ADR-0013 (Vector Store)

## Context

Beyond embeddings and search, M3 needs a **record** of what was ingested (for
listing, deletion, re-indexing, and provenance), a **metadata model** for
filtering retrieval, and an **ingestion pipeline** coordinating chunk → embed →
store. These are domain-shape and orchestration decisions distinct from the
embedding/vector mechanics.

## Decision

**Aggregate (mirrors ADR-0007).** `KnowledgeDocument` is the aggregate root:
`KnowledgeDocumentId`, `source` (origin identifier/URI), `metadata`, `created_at`,
an ingestion `status` (e.g. `pending`/`indexed`/`failed`), and an ordered,
append-only list of `KnowledgeChunk` (`KnowledgeChunkId`, ordinal position, text,
inherited+own metadata, token count). Domain-generated UUID identity; invariants
(contiguous ordinals, non-empty source) enforced on the root. Chunks are immutable;
re-ingestion produces a new version rather than mutating (versioning itself is
deferred, §risks).

**Metadata model.** Metadata is a **typed, string-keyed value object** with scalar
values (str/int/float/bool) — enough for equality/`in` filtering, small enough to
map to a JSON/`JSONB` column and to a vector-store payload. A `MetadataFilter`
value object expresses query-time constraints (field equals / in set). Rich query
languages are deferred.

**`KnowledgeRepository` port** (domain) — `add(document)`, `get(id)`,
`delete(id)`, `list(filter)` — the document/chunk **record**, distinct from the
`VectorStore` index (ADR-0013). It gets a shared **knowledge-repository contract
suite** (round-trip, ordering, not-found, delete, isolation) and two
implementations: in-memory and SQLAlchemy/PostgreSQL — the ADR-0008 pattern,
reusing the M2 engine/session and Alembic.

**`IndexingService`** (application) orchestrates ingestion:
`load → chunk (ChunkingStrategy) → embed (EmbeddingProvider) → persist record
(KnowledgeRepository) + upsert vectors (VectorStore)`, recording the embedding
model + dimension in metadata so a later dimension mismatch fails fast. Deletion
removes both the record and its vectors. Embedding runs *outside* any DB
transaction (the ADR-0008 "slow work outside the transaction" precedent);
record-store consistency uses the existing transaction boundary. Cross-store
(record + vector) atomicity is best-effort in M3 (idempotent upsert + delete
compensation), with true cross-store consistency an explicit non-goal (§risks).

**Persistence layout.** The default pgvector backend co-locates the knowledge
record tables and the vector column in one Postgres (reusing M2 infrastructure); a
dedicated vector DB (Qdrant) remains a config-only swap behind `VectorStore`. A new
Alembic migration enables the `vector` extension and creates the
`knowledge_documents` / `knowledge_chunks` tables (+ the vector column/index).

## Consequences

**Positive**
- A queryable, deletable ingestion record with provenance; the aggregate maps to
  SQL exactly as `Conversation` did.
- Metadata filtering is uniform across the record store and the vector payload.
- Ingestion is one orchestrated, testable use case; embedding-model/dimension are
  recorded, catching silent invalidation.

**Negative / Costs**
- Two stores to keep consistent during ingest/delete; M3 accepts best-effort
  (idempotent upsert + compensating delete), not distributed transactions.
- Append-only + no versioning means re-ingesting a changed document is delete +
  re-add in M3.

## Alternatives Considered

- **No record store (vector store only).** Rejected: loses listing, deletion by
  document, provenance, and a re-index source of truth.
- **Free-form nested metadata / a full query DSL.** Rejected as over-scope: scalar
  key/values cover M3 filtering and map cleanly to `JSONB` and payloads.
- **A cross-store Unit of Work for record+vector atomicity.** Rejected as
  speculative (ADR-0008 stance); idempotent operations + compensation suffice at
  M3 scale.

## Trade-offs Accepted

We accept two coordinated stores with best-effort consistency and no versioning in
exchange for a queryable, provenance-bearing knowledge record that mirrors the
proven M2 aggregate/repository pattern.
