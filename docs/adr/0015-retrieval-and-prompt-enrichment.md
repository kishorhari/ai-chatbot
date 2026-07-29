# ADR-0015: Retrieval Strategy & Prompt Enrichment

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0009 (Context Window & PromptAssembler), ADR-0010 (Application Service Layer), ADR-0011 (Knowledge & Retrieval Architecture)
- **Modifies:** the M2 `ChatService` — **additively** (one injected collaborator, backward-compatible)
- **Refinement (owner-ratified):** `ChatService` orchestrates a single
  `ContextProvider` collaborator; it does not coordinate retrieval or enrichment
  itself. The `Retriever` and `PromptEnricher` are internal collaborators *of the
  `ContextProvider`*, not of `ChatService`.

## Context

Two questions: (1) how is knowledge retrieved for a turn, and (2) how does it enter
the prompt without reopening the frozen `PromptAssembler` (a pure builder,
ADR-0010) or violating the single-leading-system-message invariant (ADR-0007), and
without exceeding the context budget (ADR-0009)? And RAG must be switchable off,
leaving M2 behavior identical.

## Decision

**One collaborator for `ChatService`: the `ContextProvider`.** `ChatService`
orchestrates a **single** application port —

    ContextProvider.enrich(messages, query, filter?) -> tuple[ChatMessage, ...]

— that returns the (possibly context-augmented) message sequence to assemble.
`ChatService` does **not** embed, search, or enrich itself, and gains no retrieval
knowledge over time (owner-ratified refinement): it delegates the entire
"obtain-and-enrich contextual knowledge" step to this one collaborator, then hands
the result to the frozen `PromptAssembler`. Two implementations:
- `NullContextProvider` — returns the messages unchanged (RAG off; the Null
  Object). This is what keeps M2 behavior byte-for-byte identical.
- `KnowledgeContextProvider` — composes the retrieval and enrichment internals
  below and returns the augmented messages.

**Retrieval (internal to the ContextProvider).** A `Retriever` port —
`retrieve(query, filter, k) -> RetrievedContext` — with a `SemanticRetriever`
implementation that embeds the query (`EmbeddingProvider`) and searches the
`VectorStore`; a `RetrievalService` adds metadata-filter handling and an optional
score threshold. `RetrievedContext` is an ordered, immutable VO of `RetrievedChunk`s
with scores + metadata. These are collaborators **of the `KnowledgeContextProvider`**
— `ChatService` never sees them.

**Enrichment (internal to the ContextProvider).** A pure `PromptEnricher` merges
the retrieved passages into the **single leading system message** (base
instructions + a delimited context block) — never a second system message, so the
assembler's invariant (ADR-0007/0009) holds. It reserves a **retrieval sub-budget**
within `max_context_tokens` (via `TokenEstimator`) so enrichment can never overflow
the window; excess passages are dropped lowest-score-first. The augmented sequence
is **ephemeral** (request-only, never persisted — the aggregate is untouched).

**The one M2 change.** `ChatService` gains exactly one collaborator, the
`ContextProvider`, and its flow becomes:
`recall → append user → window → context_provider.enrich(windowed, query) →
assemble → generate → persist`.
With `NullContextProvider` wired, `enrich` returns its input and behavior and every
M2 test are unchanged. The frozen `PromptAssembler` still just maps whatever
messages it is given. A single collaborator — not a `Retriever` + `PromptEnricher`
pair coordinated by `ChatService`, and not a parallel `RagChatService` — keeps
orchestration in one place (ADR-0010) and prevents `ChatService` from accumulating
retrieval responsibilities.

Configuration: `AIP__KNOWLEDGE__ENABLED`, `AIP__KNOWLEDGE__RETRIEVAL__K`,
`AIP__KNOWLEDGE__RETRIEVAL__MIN_SCORE`,
`AIP__KNOWLEDGE__RETRIEVAL__CONTEXT_TOKEN_BUDGET`.

## Consequences

**Positive**
- RAG toggles by config; disabled, the system is byte-for-byte M2.
- The frozen assembler and the aggregate invariant are both respected; retrieved
  context participates in the existing budget rather than bypassing it.
- Future retrieval strategies (hybrid, rerank) implement the same `Retriever` port.

**Negative / Costs**
- `ChatService` is modified (the only M2 touch-point) — but minimally: one
  collaborator, one delegated call. Justified: RAG *is* an augmentation of the chat
  turn; a parallel service would duplicate orchestration and split the
  single-orchestrator principle.
- Merging context into the system message is a policy choice; alternatives (a
  leading user preamble) exist and can be revisited — behind the `ContextProvider`,
  invisible to `ChatService`.

## Alternatives Considered

- **`ChatService` coordinates a `Retriever` + `PromptEnricher` directly.**
  Rejected (owner refinement): `ChatService` would accumulate retrieval
  responsibilities over time. Collapsed into a single `ContextProvider`
  collaborator that owns retrieval + enrichment internally.
- **A parallel `RagChatService`.** Rejected: duplicates the M2 turn (persist,
  transaction, clock) and two orchestrators drift.
- **Modify `PromptAssembler` to accept context.** Rejected: violates its
  pure-builder charter (ADR-0010); enrichment is orchestration.
- **Inject context as a second system message.** Rejected: breaks the
  single-leading-system invariant (ADR-0007).
- **Retrieve outside the budget and prepend verbatim.** Rejected: can overflow the
  context window; enrichment must be budget-aware.

## Trade-offs Accepted

We accept one additive `ChatService` collaborator and a system-message injection
policy in exchange for config-toggled, budget-safe RAG that leaves the frozen
assembler, the aggregate invariant, and M2 behavior intact.
