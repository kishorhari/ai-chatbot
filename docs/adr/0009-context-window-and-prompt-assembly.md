# ADR-0009: Context-Window Selection and Prompt Assembly

- **Status:** Accepted
- **Date:** 2026-07-06
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0003 (Streaming-First Provider), ADR-0007 (Conversation Aggregate), ADR-0002 (Provider Abstraction)

## Context

With durable conversation history (ADR-0007), the chat use case must turn *stored
history + a new user turn* into a `CompletionRequest` that fits the model's context
budget. Two coupled decisions follow: **which** messages to include
(context-window selection / "memory"), and **how** to compose them into a prompt
(prompt assembly). Both must:

- Respect `ProviderCapabilities.max_context_tokens` (already on the frozen port).
- Produce the existing `CompletionRequest` — the M1 port must **not** change.
- Avoid premature coupling to a specific tokenizer library or to summarization
  (which needs its own model call and belongs later).

"Memory" in M2 is deliberately literal: the recent conversation history retrieved
from the repository. Semantic recall over an external corpus is RAG (M3);
summary-based long-term memory is a later enhancement. Scoping memory to "recent
persisted history, windowed to fit" keeps M2 honest and small.

## Decision

Introduce two thin **application-layer** components in `application/conversation`,
operating on domain objects and emitting the frozen `CompletionRequest`:

### Context-window policy
- A `ContextWindowPolicy` selects the messages that fit a budget derived from
  `capabilities().max_context_tokens` minus a **response reservation**.
- Strategy: **always keep the system prompt**, then include the most recent
  messages, dropping the oldest that do not fit. Deterministic and unit-testable at
  the boundaries.
- Token accounting goes through a minimal **`TokenEstimator` seam** with a
  conservative heuristic default (character-based). Exact per-provider tokenization
  is **deferred** behind this seam — added only when accuracy demonstrably matters.
  The estimator over-counts rather than under-counts, so the budget is never
  exceeded by estimation error.

### Prompt assembly
- A `PromptAssembler` composes: system prompt → windowed history
  (`Message → ChatMessage`) → the new user message, producing a
  `CompletionRequest`.
- It enforces prompt invariants in one place: a single system message, correct
  role ordering, and the system prompt's precedence.
- Mapping `Message → ChatMessage` is the only point the persistence model meets the
  transport model; the provider port sees nothing new.

Neither component performs I/O beyond what the repository already returned; both are
pure functions of their inputs and are covered by unit tests.

## Consequences

**Positive**
- The chat use case has a clear, tested pipeline: recall → window → assemble →
  generate, with the token budget enforced before the provider is ever called.
- The frozen provider port is honored — assembly outputs the existing
  `CompletionRequest`.
- The tokenizer and summarization decisions are isolated behind seams, so they can
  be upgraded without touching callers.

**Negative / Costs**
- Heuristic token estimation is approximate; the response reservation must be
  conservative to stay safe. Accepted for M2; exact tokenization is a bounded later
  change.
- A hard-drop window can truncate relevant older context. Accepted: summary memory
  and RAG address this in later milestones.

## Alternatives Considered

- **Send the entire history.** Rejected: exceeds the context budget and cost grows
  unbounded.
- **Exact per-provider tokenizer now.** Rejected: premature coupling to a specific
  library for marginal M2 benefit; deferred behind the `TokenEstimator` seam.
- **Summary-based memory in M2.** Rejected: requires an extra model call and
  eviction policy; out of scope, revisited after RAG (M3).
- **Assembly inside the adapter/interface.** Rejected: it is application
  orchestration; placing it in infrastructure or delivery would leak use-case logic
  and risk touching the port.

## Trade-offs Accepted

We accept approximate token estimation and lossy windowing in M2 in exchange for a
small, deterministic, well-tested memory/assembly pipeline that respects the model's
context budget and leaves the frozen provider port and future summarization/RAG work
cleanly seamed off.
