# ADR-0007: Conversation and Message Aggregates

- **Status:** Accepted
- **Date:** 2026-07-06
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0001 (Clean Architecture), ADR-0005 (Repository Strategy), ADR-0008 (Persistence), ADR-0009 (Context Window & Prompt Assembly)

## Context

Milestone 2 introduces conversation identity and durable message history — the
first stateful domain in the platform. The aggregate shape chosen now must:

1. Map cleanly to relational storage later (ADR-0005) without an in-memory model
   that resists SQL.
2. Feed context-window assembly and prompt construction (ADR-0009).
3. Absorb multi-tenancy (M6) and agent memory (M4) **additively**, not by schema
   rewrite.
4. Leave the **frozen** M1 `LLMProvider` port and its `CompletionRequest` /
   `ChatMessage` value objects untouched (the port is finalized; M2 must not
   reopen it).

The domain already has a transport value object `ChatMessage` (role + content) in
`domain/llm`. A naive move would be to persist that object directly. But a
transport message (what is sent to a provider) and a stored message (an entity
with identity, ordering, timestamps, and provenance) have different lifecycles and
different reasons to change. Conflating them would drag persistence concerns toward
the frozen provider port.

## Decision

Introduce a **`Conversation` aggregate** in a new `domain/conversation` package,
with **`Message` as an entity inside that aggregate** and `Conversation` as the
aggregate root and transactional consistency boundary.

- **Identity is domain-generated, not database-generated.** `ConversationId` and
  `MessageId` are UUIDs created in the domain, so identity exists before
  persistence — the in-memory-first strategy and DB-free tests depend on this.
- **Messages are append-only and immutable.** Once added, a message is never
  mutated; an edit or regeneration is a *new* message. This simplifies concurrency,
  gives a natural audit trail, matches how LLM conversations actually evolve, and
  maps to append-only rows.
- **Ordering is an explicit `sequence` integer**, contiguous within a conversation
  — never inferred from timestamps (which collide and suffer clock skew).
  Repositories must preserve sequence order; this is asserted by the repository
  contract suite (ADR-0008).
- **Ownership is present from day one.** `Conversation` carries an `owner` /
  principal identity field even though M2 is single-user, so M6 multi-tenancy adds
  enforcement, not a column.
- **Stored `Message` is distinct from transport `ChatMessage`.** `Message` is a
  domain entity (`MessageId`, `Role`, content, `sequence`, `created_at`, optional
  `TokenUsage`/metadata). Prompt assembly (ADR-0009) maps `Message → ChatMessage`
  when building a `CompletionRequest`. Existing value objects (`Role`,
  `TokenUsage`) are reused, not duplicated.
- **Invariants live on the root.** Appending goes through the aggregate
  (`conversation.append(...)`), which enforces sequence contiguity, the
  single-system-message rule, and ownership — in one place.

The aggregate is deliberately shallow: `Conversation` (1) → (N) `Message`, no
deeper nesting, so the relational mapping (ADR-0008) is a two-table translation.

## Consequences

**Positive**
- Persistence-ready by construction; the SQL mapping is mechanical.
- Immutability + explicit sequence removes whole classes of ordering/concurrency
  bugs and makes the repository contract suite straightforward.
- The frozen provider port is untouched — transport and storage evolve
  independently.
- Multi-tenancy and agent memory are additive extensions of the root.

**Negative / Costs**
- Two message representations (stored `Message`, transport `ChatMessage`) plus a
  mapping step. Accepted: the same "map at the boundary" trade-off already accepted
  for providers (ADR-0002).
- Append-only means regenerations/edits accumulate rows; pruning/archival is a
  later concern (noted, deferred).

## Alternatives Considered

- **Persist `ChatMessage` directly.** Rejected: conflates transport with storage
  and couples persistence to the frozen port.
- **Mutable messages.** Rejected: concurrency and audit pain; no clean SQL story.
- **Timestamp-based ordering.** Rejected: collisions and clock skew; ordering must
  be deterministic.
- **Database-generated identity.** Rejected: couples identity to persistence and
  blocks in-memory-first development and DB-free tests.

## Trade-offs Accepted

We accept a second message representation and a mapping step in exchange for a
storage-ready, immutable, deterministically-ordered aggregate that keeps the frozen
provider port and future tenancy/agent features cleanly separated.
