# ADR-0011: Knowledge & Retrieval Architecture (RAG)

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0001 (Clean Architecture), ADR-0002 (Provider Abstraction), ADR-0007 (Aggregate), ADR-0008 (Persistence), ADR-0009 (Context Window), ADR-0010 (Application Service Layer)
- **Supersedes/Modifies:** none (M1/M2 frozen; one additive seam, ADR-0015)

## Context

The assistant answers only from conversation history. Milestone 3 adds
Retrieval-Augmented Generation: answers grounded in an external knowledge base of
ingested documents. The strategic requirement is explicit — **knowledge must be a
replaceable infrastructure capability**, exactly like the LLM provider (M1) and
persistence (M2): a stable port with a contract suite, an offline reference
implementation, a real implementation, and selection by configuration.

Two sub-capabilities are volatile and must be isolated behind ports: the
**embedding model** (SentenceTransformers / Ollama / OpenAI …) and the **vector
store** (pgvector / Qdrant / Chroma / FAISS …). A naive design that called an
embedding SDK or a vector client from the application layer would repeat the
"vendor leaks everywhere" mistake ADR-0002 was written to prevent.

## Decision

Introduce a **`domain/knowledge`** bounded context and an
**`application/knowledge`** use-case package, layered exactly as the rest of the
system (Domain → Application → Ports → Infrastructure).

- **Domain model (ADR-0016):** a shallow `KnowledgeDocument` aggregate (root) → (N)
  `KnowledgeChunk`, mirroring `Conversation → Message`: domain-generated UUID
  identity, immutable chunks, explicit ordinal position, source + metadata, and an
  ingestion status on the root. The **embedding vector is *not* a domain field** —
  it is an infrastructure representation held by the vector store, keyed by chunk
  id. The domain owns text + metadata + position; the vector is a detail.
- **Three domain ports** (ADR-0012/0013/0016): `EmbeddingProvider` (text → vector),
  `VectorStore` (upsert / similarity-search / delete vectors), and
  `KnowledgeRepository` (persist the document/chunk record). Each speaks only in
  domain value objects, never in SDK types, and each earns trust through a shared
  contract suite with ≥2 implementations.
- **Application use cases (ADR-0014/0015):** `ChunkingStrategy` (pure), an
  `IndexingService` (ingest), a `RetrievalService`/`SemanticRetriever` behind a
  `Retriever` port, and a `PromptEnricher`. Orchestration lives in application
  services (ADR-0010); the frozen `PromptAssembler` stays a pure builder.
- **Reuse, don't reopen:** the M1 `LLMProvider`/`CompletionRequest` and the M2
  `Conversation`/`ContextWindowPolicy`/`TokenEstimator` are reused unchanged. The
  only M2 modification is an additive `Retriever` collaborator on `ChatService`
  (ADR-0015), a no-op when RAG is disabled.
- **Selection by configuration:** `AIP__KNOWLEDGE__*` chooses the embedding
  backend, the vector backend, the knowledge backend, chunking parameters, and a
  RAG on/off toggle — no application/domain change to switch any of them.

## Consequences

**Positive**
- Embedding model and vector store are swappable behind proven ports; adding one
  is "write an adapter + pass the contract suite + one wiring line."
- The domain stays pure and vector-library-free; `import-linter` guarantees it.
- The offline reference path (fake embeddings + in-memory vector store) makes the
  entire RAG chat deterministic and testable without a model, GPU, or network.
- The RAG core is orthogonal to future milestones (tools, agents, memory), which
  can consume `RetrievalService`/`Retriever` without new coupling.

**Negative / Costs**
- A new bounded context and several ports/adapters — more surface than a direct
  SDK call. Mitigated by mirroring the already-paid-for provider/persistence
  patterns.
- Two stores (record + vector index) to keep consistent during ingestion.

## Alternatives Considered

- **Call an embedding SDK / vector client directly from `ChatService`.** Rejected:
  the exact vendor-coupling ADR-0002 forbids; untestable offline.
- **A single "RAG library" (e.g. LangChain/LlamaIndex) as the seam.** Rejected for
  the same reasons as ADR-0002's framework alternative — it would *be* our contract
  and obscure the boundaries. Such a library may live *behind* an adapter later.
- **Store embedding vectors on the domain chunk.** Rejected: couples the domain to
  a dimension and a numeric representation; the vector is an infrastructure concern.

## Trade-offs Accepted

We accept a new bounded context and two coordinated stores in exchange for a
knowledge capability that is replaceable, offline-testable, and layered identically
to the rest of the platform — with the frozen M1/M2 ports intact.
