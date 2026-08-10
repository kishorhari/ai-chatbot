# ADR-0013: Vector Store Abstraction

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0008 (Repository contract precedent), ADR-0011 (Knowledge & Retrieval Architecture), ADR-0012 (Embedding Abstraction)

## Context

Similarity search over embeddings is the retrieval engine, and its backend is
volatile: pgvector (a Postgres extension), Qdrant, Chroma, FAISS, or an in-memory
structure for tests. Backends differ in distance metrics, filtering, index types,
and consistency. RAG must depend on a stable contract, and — as with the
repository (ADR-0008) — the swap must be *proven* by one suite, not asserted.

## Decision

Define a **domain port `VectorStore`** (in `domain/knowledge/ports`), a
retrieval-specialised sibling of the repository pattern:

- `upsert(entries)` where an entry is `(chunk_id, EmbeddingVector, payload)` — the
  payload carries the chunk text + filterable metadata so retrieval is a single
  call (no second lookup at query time).
- `search(query_vector, k, filter) -> list[Match]` where a `Match` is
  `(chunk_id, score, payload)`, ordered by descending similarity.
- `delete(document_id)` — remove all vectors for a document (re-index / removal).
- **Distance metric fixed in the contract as cosine similarity**, and the stored
  vector **dimension is validated** against the embedding provider's
  `capabilities()` — a mismatch fails fast.

Ship one **vector-store contract suite** (`vector_store_contract.py`) asserting:
upsert-then-search round-trip; **top-k ordering by similarity** (nearer vectors
rank higher); k bounding; metadata-filter correctness (only matching payloads
returned); delete-by-document; and isolation between documents. An
**`InMemoryVectorStore`** (brute-force cosine) is the reference implementation; a
**`PgVectorStore`** (M3.7) is the production one and runs the identical suite
against real Postgres/pgvector in CI (the ADR-0008 precedent).

Selection is by configuration: `AIP__KNOWLEDGE__VECTOR__BACKEND=memory|pgvector|…`.

**Two stores, deliberately.** `VectorStore` (search index) is separate from
`KnowledgeRepository` (the document/chunk record, ADR-0016). This lets the vector
index be replaced independently (e.g. Qdrant for vectors, Postgres for records).
The default pgvector backend may co-locate both in one Postgres, but they remain
distinct ports.

## Consequences

**Positive**
- Vector backends are swappable behind one proven contract; the in-memory store
  keeps retrieval tests offline and deterministic.
- Fixing cosine + dimension validation in the contract removes a class of
  cross-backend surprises.
- pgvector reuses the M2 async engine/session — minimal new operational surface.

**Negative / Costs**
- The payload duplicates chunk text between the record store and the index
  (accepted for single-call retrieval; the record store remains the source of
  truth for re-indexing).
- ANN index tuning (IVFFlat/HNSW parameters) is real work; deferred — an exact or
  default-index baseline first (§ roadmap risks).

## Alternatives Considered

- **One store (fold vectors into `KnowledgeRepository`).** Rejected: couples the
  record to a specific index and blocks swapping the vector backend independently.
- **Return ids only from `search` (no payload), then load text from the repo.**
  Rejected for M3: a second round-trip per query for no benefit at this scale;
  payloads keep retrieval one call. Revisit if payload duplication becomes costly.
- **Let each backend choose its own distance metric.** Rejected: non-comparable
  scores across backends break the contract suite and retrieval thresholds.

## Trade-offs Accepted

We accept payload duplication and a separate index port in exchange for
independently swappable, contract-proven vector search with offline tests.
