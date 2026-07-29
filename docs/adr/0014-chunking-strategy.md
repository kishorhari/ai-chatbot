# ADR-0014: Chunking Strategy

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0009 (Context Window & TokenEstimator), ADR-0011 (Knowledge & Retrieval Architecture)

## Context

A document must be split into retrievable units before embedding. Chunk size and
overlap materially affect retrieval quality: too large dilutes similarity and
wastes context budget; too small fragments meaning; no overlap severs ideas at
boundaries. Multiple strategies are genuinely foreseeable (fixed-size, token-aware
recursive, sentence/semantic), so this is a real seam — not speculative.

## Decision

Define **`ChunkingStrategy` as an application-layer port** (in
`application/knowledge`), not a domain port: chunking is a processing policy in the
use-case layer, exactly like `ContextWindowPolicy` and `PromptAssembler` (ADR-0009).
Crucially, this placement lets chunking **reuse the M2 `TokenEstimator`** (also
application) to size chunks by tokens — a domain port could not depend on it
(domain must not import application).

- Contract: `chunk(text, metadata) -> list[KnowledgeChunk]` producing ordered,
  contiguous chunks (each carrying its ordinal position and inherited metadata).
- Default implementation `TokenAwareChunker`: recursive split on natural
  boundaries (paragraph → sentence) targeting a configurable token size with a
  configurable token overlap, estimated via `TokenEstimator`. Deterministic.
- Configuration: `AIP__KNOWLEDGE__CHUNK__SIZE_TOKENS`,
  `AIP__KNOWLEDGE__CHUNK__OVERLAP_TOKENS`.

Chunking is **pure** (no I/O, embedding, storage, or retrieval) and is invoked only
by the `IndexingService`. It emits domain `KnowledgeChunk` entities; it does not
embed or persist them.

## Consequences

**Positive**
- A clean seam for future strategies (semantic/LLM chunking) with a deterministic,
  dependency-light default now.
- Token-aware sizing reuses proven M2 machinery and aligns chunk budgeting with the
  same estimator used for the context window.
- Pure and deterministic → trivially unit-testable (fixed input → fixed chunks).

**Negative / Costs**
- Fixed-size chunking can still split mid-idea; overlap mitigates but does not
  eliminate this. Semantic chunking is deferred until quality demands it.

## Alternatives Considered

- **A domain-layer chunking port.** Rejected: it would need the application-layer
  `TokenEstimator`, inverting the dependency rule; and chunking is a use-case
  policy, not a domain invariant.
- **A single hard-coded chunker (no port).** Rejected: multiple strategies are
  clearly foreseeable, so a seam is justified now (unlike `ContextWindowPolicy`,
  which had one obvious strategy at M2).
- **Character-based chunking.** Rejected as the default: token budgets, not
  characters, are what the model and the context window care about.

## Trade-offs Accepted

We accept fixed-size-with-overlap chunking now (semantic chunking deferred) in
exchange for a deterministic, token-aware, easily-testable default behind a seam
that future strategies can fill.
