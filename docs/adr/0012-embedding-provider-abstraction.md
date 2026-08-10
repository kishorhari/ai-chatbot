# ADR-0012: Embedding Provider Abstraction

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0002 (LLM Provider Abstraction — the precedent), ADR-0004 (Echo reference provider), ADR-0011 (Knowledge & Retrieval Architecture)

## Context

Turning text into vectors is a volatile, vendor-specific capability: the model may
be a local SentenceTransformers checkpoint, an Ollama embedding model
(`nomic-embed-text`), or a cloud API (OpenAI, Voyage). Each differs in dimension,
batching, tokenization, cost, and failure modes. RAG must not couple to any of
them, and — critically — the test suite must not require a model, GPU, or network.

## Decision

Define a **domain port `EmbeddingProvider`** (in `domain/knowledge/ports`),
mirroring `LLMProvider` (ADR-0002):

- Speaks in domain value objects: `str` in, `EmbeddingVector` out (a dimension +
  immutable float sequence). Never vendor payloads.
- Distinguishes `embed_documents(texts)` (batch, for ingestion) from
  `embed_query(text)` (single, for retrieval) — some models use different prefixes
  for the two, and batching matters for ingestion throughput.
- Exposes `capabilities()` (at least the embedding **dimension** and model id) with
  no I/O, so the vector store and ingestion can validate dimension consistency.
- Maps all transport/vendor failures to the domain error taxonomy (reusing the
  `LLMError` family or a parallel `EmbeddingError`); no SDK exception escapes.

Ship a deterministic **`FakeEmbeddingProvider`** as the reference implementation
(ADR-0004 precedent): a hash-based, fixed-dimension, L2-normalised vector that is
stable for a given input and requires no model or network. It makes the whole RAG
path deterministic and offline. A real **`OllamaEmbeddingProvider`** (reusing the
M1 httpx/Ollama adapter style) is the first production implementation.

Both must pass one **embedding contract suite** (`embedding_contract.py`):
determinism (same input → same vector), stable dimension across inputs,
`embed_documents` batch equals per-item `embed_query` where the model defines them
equal, non-empty input handling, and dimension matching `capabilities()`.

Selection is by configuration: `AIP__KNOWLEDGE__EMBEDDING__BACKEND=fake|ollama|…`.

## Consequences

**Positive**
- Embedding vendors are swappable; a new one is an adapter + a passing suite.
- The fake provider makes RAG fully deterministic and CI-friendly offline.
- Dimension is a first-class, checkable capability, preventing silent
  vector/store mismatches.

**Negative / Costs**
- A mapping/adapter per vendor. The fake is non-semantic, so retrieval *quality* is
  measured separately (the evaluation harness), not by the contract suite.

## Alternatives Considered

- **Reuse `LLMProvider` for embeddings.** Rejected: embedding is a distinct
  operation (no streaming, no chat), and overloading the port would muddy both.
- **Mocks instead of a real fake provider.** Rejected for the same reason as
  ADR-0004: a mock asserts our assumptions; a real deterministic implementation
  proves the abstraction and exercises every layer above it.

## Trade-offs Accepted

We accept a per-vendor adapter and a non-semantic fake in exchange for a
vendor-neutral, offline-testable embedding seam consistent with the LLM provider.
