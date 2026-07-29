# Development Roadmap — Milestone 3: Knowledge Retrieval (RAG)

**Status:** Proposed (architecture package for review — no implementation).

**Scope:** Introduce Retrieval-Augmented Generation. The assistant answers using
external knowledge (ingested documents) in addition to conversation history.
Knowledge becomes a **replaceable infrastructure capability** — like the LLM
provider (M1) and persistence (M2) — behind ports proven by contract suites.

**Governing ADRs (proposed):** [0011](../adr/0011-knowledge-and-retrieval-architecture.md)
(knowledge & retrieval architecture), [0012](../adr/0012-embedding-provider-abstraction.md)
(embedding abstraction), [0013](../adr/0013-vector-store-abstraction.md) (vector store
abstraction), [0014](../adr/0014-chunking-strategy.md) (chunking),
[0015](../adr/0015-retrieval-and-prompt-enrichment.md) (retrieval & prompt enrichment),
[0016](../adr/0016-knowledge-metadata-ingestion-and-persistence.md) (metadata,
ingestion & persistence). Foundational: ADR-0001 (Clean Architecture), ADR-0002
(provider abstraction precedent), ADR-0008 (repository/contract precedent),
ADR-0009 (context window), ADR-0010 (application-service layer).

> **The one M2 touch-point (ADR-0015, owner-refined).** ChatService gains a single
> additive collaborator — a `ContextProvider` port — and delegates the whole
> "obtain-and-enrich contextual knowledge" step to it, defaulting to a
> `NullContextProvider` (no-op). ChatService does **not** coordinate retrieval or
> enrichment itself; the `Retriever` and `PromptEnricher` are internal to the
> `ContextProvider`. With RAG disabled the M2 chat turn behaves identically and
> every M2 test passes unchanged; with RAG enabled by config, the provider
> retrieves + enriches before assembly. No other M1/M2 component changes; the
> frozen `LLMProvider` port and `PromptAssembler` are untouched.

---

## 1. Sub-milestones

| ID | Sub-milestone | Goal |
|----|---------------|------|
| M3.0 | Knowledge domain | `KnowledgeDocument` aggregate + `KnowledgeChunk`, ids, value objects (`EmbeddingVector`, `RetrievedChunk`, `RetrievedContext`, metadata), errors, and the domain ports — pure domain |
| M3.1 | Embedding provider + contract suite | `EmbeddingProvider` port, the shared embedding contract suite, a deterministic `FakeEmbeddingProvider`, and one real adapter (Ollama embeddings) |
| M3.2 | Vector store + contract suite | `VectorStore` port, the shared vector-store contract suite, `InMemoryVectorStore` passing it |
| M3.3 | Chunking + knowledge repository + indexing | `ChunkingStrategy` (application), `KnowledgeRepository` port + in-memory impl + contract suite, `IndexingService` (chunk → embed → store) |
| M3.4 | Retrieval | `Retriever` port, `SemanticRetriever`, `RetrievalService`, `RetrievedContext` assembly + metadata filtering |
| M3.5 | Context provider + ChatService seam | `PromptEnricher` (single-system-safe, budget-aware); `ContextProvider` port with `NullContextProvider` + `KnowledgeContextProvider` (composing retriever + enricher); ChatService delegates to the single `ContextProvider` collaborator (additive) |
| M3.6 | Delivery + composition | Knowledge ingestion/query HTTP endpoints (+ CLI), backend + RAG selection by config |
| M3.7 | pgvector backend | pgvector `VectorStore` + SQLAlchemy `KnowledgeRepository` + Alembic (extension + tables); the identical contract suites green against real Postgres/pgvector in CI |
| M3.8 | Hardening & gates | Retrieval/embedding evaluation harness, dependency-rule updates, coverage, docs, exit review |

The order is dependency-driven and mirrors M1/M2: domain contracts first; the
embedding and vector-store abstractions with their contract suites before any real
backend; the offline reference implementations (`Fake` embeddings, in-memory
vector store) before pgvector; retrieval before enrichment; enrichment before the
ChatService seam; delivery after the use case; **pgvector is the capstone** —
it proves the swap, so it comes last.

---

## 2. Functional scope

**In scope (M3):**
- Document ingestion (plain text / markdown; a pluggable loader seam for richer
  formats later).
- Chunking (token-aware, with configurable size and overlap).
- Embeddings (a provider abstraction; local-first default).
- A vector store (similarity search, upsert, delete-by-document, metadata filter).
- A knowledge record store (documents + chunks + metadata + ingestion status).
- Retrieval (embed query → top-k similarity search → `RetrievedContext`).
- Prompt enrichment (inject retrieved context into the request, budget-aware).
- Metadata filtering at query time.
- Configuration-driven selection of embedding backend, vector backend, knowledge
  backend, chunking parameters, retrieval `k`/threshold, and a RAG on/off toggle.

**Explicitly NOT in scope (deferred — see §13):** hybrid (keyword+vector) search,
reranking (cross-encoder), semantic/LLM chunking, knowledge editing/versioning,
automatic re-embedding on model change, streaming retrieval, per-user knowledge
permissions/tenancy, agent/tool-driven retrieval, memory summarization, OCR / rich
document parsing (PDF tables, images), and large-scale ANN index tuning.

---

## 3. File implementation order

Within `src/aiplatform/` (never implement a file before the inner files it imports
exist):

```
M3.0  domain/knowledge/ids.py                KnowledgeDocumentId, KnowledgeChunkId
      domain/knowledge/vectors.py            EmbeddingVector (dimension + values + cosine)
      domain/knowledge/metadata.py           Metadata, MetadataFilter (scalar VOs)
      domain/knowledge/chunk.py              KnowledgeChunk entity
      domain/knowledge/document.py           KnowledgeDocument aggregate root (+ IngestionStatus)
      domain/knowledge/retrieval.py          RetrievedChunk, RetrievedContext (VOs)
      domain/knowledge/errors.py             knowledge/retrieval error taxonomy
      domain/knowledge/ports.py              EmbeddingProvider, VectorStore, KnowledgeRepository (+ port VOs)

M3.1  infrastructure/knowledge/embedding/fake/adapter.py     FakeEmbeddingProvider (deterministic)
      tests/contract/embedding_contract.py                    shared embedding contract suite
      infrastructure/knowledge/embedding/ollama/adapter.py    OllamaEmbeddingProvider

M3.2  infrastructure/knowledge/vector/memory/store.py         InMemoryVectorStore
      tests/contract/vector_store_contract.py                 shared vector-store contract suite

M3.3  application/knowledge/chunking.py       ChunkingStrategy (port) + TokenAwareChunker (default)
      infrastructure/knowledge/repository/memory/repository.py  InMemoryKnowledgeRepository
      tests/contract/knowledge_repository_contract.py         shared knowledge-repo contract suite
      application/knowledge/indexing_service.py               IndexingService (chunk→embed→store)

M3.4  application/knowledge/retriever.py       Retriever (port)
      application/knowledge/semantic_retriever.py  SemanticRetriever (embed query → search)
      application/knowledge/retrieval_service.py   RetrievalService (query API + filtering)

M3.5  application/knowledge/prompt_enricher.py  PromptEnricher (context injection)
      application/knowledge/context_provider.py  ContextProvider (port) + NullContextProvider
                                                 + KnowledgeContextProvider (retriever + enricher)
      application/conversation/chat_service.py   (extend: delegate to one ContextProvider — additive)

M3.6  interface/http/routes/knowledge.py        ingest / list / delete / (debug) search endpoints
      interface/cli/ingest.py                    CLI ingestion + query
      composition/container.py (extend)          wire embedding/vector/knowledge backends + retriever by config

M3.7  infrastructure/knowledge/vector/pgvector/store.py       PgVectorStore
      infrastructure/knowledge/repository/sqlalchemy/...       SqlAlchemyKnowledgeRepository + mapping
      migrations/ (alembic)                                   pgvector extension + knowledge/chunk tables

M3.8  .importlinter (knowledge contracts), CI (pgvector), evaluation harness, docs, exit review
```

---

## 4. Dependency graph (build-time)

```
domain/llm  (Role, ChatMessage, CompletionRequest, TokenUsage)     ← frozen (M1)
domain/conversation (Conversation, Message)                        ← frozen (M2)
        ▲                                        ▲
        │ reuses VOs                             │ enriched, not modified
domain/knowledge                          application/knowledge
  (KnowledgeDocument, KnowledgeChunk,       (ChunkingStrategy, IndexingService,
   EmbeddingVector, RetrievedContext,        Retriever port + Null/Semantic,
   MetadataFilter, errors, ports:            RetrievalService, PromptEnricher)
   EmbeddingProvider, VectorStore,                 ▲
   KnowledgeRepository)                             │ depends on domain ports only
        ▲            ▲            ▲                  │
        │            │            │                  │ ChatService (M2) gains an
infra/knowledge/embedding  infra/knowledge/vector  infra/knowledge/repository
  (fake, ollama, openai…)   (memory, pgvector,      (memory, sqlalchemy/pgvector)
                             qdrant…)
        ▲            ▲            ▲
        └──────── composition ───┘  selects backends + retriever by config,
                       ▲             injects Retriever into ChatService
                       │
         interface/http/routes/knowledge, interface/cli/ingest
```

Dependencies flow inward to `domain`. `application/knowledge` depends only on
domain ports. All embedding / vector / knowledge adapters depend only on domain
(VOs + ports). `composition` is the only multi-layer importer. The frozen
`domain/llm` and `domain/conversation` are reused, never modified; the sole M2
change is the additive `Retriever` collaborator on `ChatService` (ADR-0015).

---

## 5. Deliverables

- `KnowledgeDocument` aggregate + `KnowledgeChunk`, domain-generated ids, and the
  retrieval value objects — pure domain.
- `EmbeddingProvider` port + a shared **embedding contract suite**, with a
  deterministic `FakeEmbeddingProvider` and one real adapter (Ollama embeddings).
- `VectorStore` port + a shared **vector-store contract suite**, with in-memory
  and **pgvector** implementations passing it (pgvector in CI).
- `KnowledgeRepository` port + a shared **knowledge-repository contract suite**,
  with in-memory and PostgreSQL implementations.
- `ChunkingStrategy` (token-aware default, reusing the M2 `TokenEstimator`).
- `IndexingService` (ingest: chunk → embed → store) and `RetrievalService`
  (query → `RetrievedContext`) with metadata filtering.
- `Retriever` port with `NullRetriever` (RAG off) and `SemanticRetriever` (RAG on);
  `PromptEnricher` injecting retrieved context, budget-aware.
- Knowledge HTTP endpoints (ingest, list, delete, debug-search) + CLI ingest/query.
- Alembic migration enabling the pgvector extension and the knowledge tables.
- CI running the three new contract suites, including against **pgvector**;
  dependency-rule contracts extended to the knowledge layer; a retrieval-evaluation
  harness. Updated docs: ADR-0011..0016, this roadmap, an M3 exit review.

---

## 6. Definition of Done (per deliverable / PR)

The M1/M2 bar, extended for retrieval:

- [ ] Lint + format clean; `mypy src` passes (strict on `domain`/`application`,
      including the new `knowledge` packages).
- [ ] `lint-imports` passes — no domain/application import of an embedding SDK, a
      vector client, `numpy`, or any knowledge adapter; frozen M1/M2 ports unchanged.
- [ ] Any new `EmbeddingProvider` / `VectorStore` / `KnowledgeRepository`
      implementation passes the shared contract suite unchanged.
- [ ] With RAG disabled (`NullRetriever`), every M2 chat test passes unchanged.
- [ ] Retrieved context participates in the context-token budget (never overflows
      `max_context_tokens`); the single-leading-system-message invariant holds.
- [ ] No secret/credential logged; DSNs/API keys read only through `Settings`
      (`SecretStr`).
- [ ] Docs/ADRs/CHANGELOG updated where behavior or a decision changed.

---

## 7. Exit criteria (Milestone 3 is "done" when)

1. **Ingest → retrieve round-trip** — a document is ingested, chunked, embedded,
   and stored; a query returns its relevant chunk(s); verified by test.
2. **Embedding abstraction proven** — the `FakeEmbeddingProvider` and ≥1 real
   embedding adapter pass the **identical** embedding contract suite.
3. **Vector store abstraction proven** — the in-memory and **pgvector** stores pass
   the **identical** vector-store contract suite; pgvector runs it in CI.
4. **Knowledge repository swap** — in-memory and PostgreSQL pass the identical
   knowledge-repository contract suite; backend is config-only.
5. **RAG is config-only and backward-compatible** — `AIP__KNOWLEDGE__ENABLED` (and
   backend keys) toggle retrieval with no application/domain code change; with RAG
   off, M2 behavior and tests are unchanged (`NullRetriever`).
6. **Enrichment correctness** — retrieved context appears in the generated
   `CompletionRequest`, a single leading system message is preserved, ordering is
   correct, and the assembled prompt never exceeds `max_context_tokens`; verified.
7. **Metadata filtering** — a query with a metadata filter returns only matching
   chunks; verified.
8. **Retrieval quality gate** — on a small fixed evaluation set, recall@k (or
   hit-rate@k) meets a declared threshold using the offline path; verified as an
   acceptance test.
9. **Dependency rule intact & ports frozen** — domain/application import no
   embedding/vector SDK; M1/M2 ports unchanged; all `import-linter` contracts pass.
10. **Determinism & coverage** — the offline path (fake embeddings + in-memory
    vector store) makes the full RAG chat deterministic and network-free;
    `domain`/`application` ≥ 95% coverage; docs current.

---

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|:----------:|:------:|------------|
| Embedding non-determinism makes RAG untestable offline | High if unaddressed | High | A deterministic `FakeEmbeddingProvider` (hash-based, fixed dimension) is the reference impl — the RAG contract/acceptance path never needs a model or network (mirrors Echo). |
| Vector-store semantics differ across backends (ordering, filter, distance metric) | Medium | High | One contract suite over in-memory **and pgvector in CI** from M3.7; suite written before pgvector; distance metric fixed in the port contract (cosine). |
| Retrieved context blows the context budget | Medium | Medium | Retrieval feeds the existing `ContextWindowPolicy`/budget; the enricher (inside the `ContextProvider`) reserves a retrieval sub-budget; verified at the boundary. |
| Embedding model change silently invalidates stored vectors | Medium | High | Record embedding model + dimension in chunk/vector metadata; dimension mismatch fails fast; re-embedding is a deferred, explicit operation (§13). |
| ChatService accumulates retrieval responsibility over time | Medium | Medium | A single `ContextProvider` collaborator (Null Object default) owns retrieval + enrichment; `ChatService` only delegates; all RAG logic stays in `application/knowledge`. |
| pgvector operational surface (extension, index type, tuning) | Medium | Medium | Reuse the M2 async engine/session; start with an exact/IVFFlat baseline; ANN tuning deferred (§13). |
| Ingestion of large documents blocks the request path | Low/Med | Medium | Ingestion is a distinct use case/endpoint; large-scale/async ingestion (background jobs) deferred (§13); M3 handles modest documents synchronously. |

---

## 9. Trade-offs accepted

- **Two knowledge stores** (a relational `KnowledgeRepository` record + a
  `VectorStore` index) rather than one — for independent replaceability of the
  vector index; the default pgvector backend may co-locate both in one Postgres.
- **A deterministic fake embedding model** as the reference implementation — an
  offline, network-free RAG test path, at the cost of a non-semantic fake (real
  quality is measured separately by the evaluation harness).
- **Similarity-only retrieval** in M3 (cosine top-k + metadata filter) — hybrid
  search and reranking deferred; a smaller, honest first cut.
- **Token-aware fixed-size chunking with overlap** — no semantic chunking yet;
  deterministic and cheap, reusing the M2 `TokenEstimator`.
- **RAG as an additive single `ContextProvider` collaborator on `ChatService`**
  (Null Object default) rather than a `Retriever` + `PromptEnricher` pair
  coordinated by `ChatService`, or a parallel `RagChatService` — one orchestrator,
  no accumulated retrieval responsibility, M2 behavior preserved when disabled.
- **pgvector as the default production vector store** (reusing the M2 Postgres)
  rather than a dedicated vector DB — fewer moving parts now; Qdrant/others remain
  a config-only swap behind the `VectorStore` port.
