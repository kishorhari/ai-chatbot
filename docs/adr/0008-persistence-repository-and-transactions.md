# ADR-0008: Persistence — Repository Contract, Transaction Boundary, and Relational Mapping

- **Status:** Accepted
- **Date:** 2026-07-06
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0005 (Repository Strategy), ADR-0007 (Conversation Aggregate), ADR-0002 (Provider Abstraction — mapping precedent)

## Context

ADR-0005 ratified the Repository pattern, an in-memory-first implementation, and
**explicitly deferred** the Unit of Work / transaction question to "the persistence
step." Milestone 2 *is* that step: it ships both the in-memory repository and the
PostgreSQL implementation. Three decisions that ADR-0005 left open must now be made:

1. The **repository port** shape and where it lives.
2. Whether — and how — to introduce a **transaction boundary** now that real
   transactions exist.
3. The **relational mapping** strategy that keeps `domain`/`application` free of
   any SQLAlchemy import (the dependency rule, ADR-0001).

The provider abstraction (ADR-0002/0004) gives a proven template: one port, a
shared contract suite, two implementations, swap by configuration.

## Decision

### 1. Repository port + contract suite

- Define **`ConversationRepository`** in `domain/conversation` (the repository of a
  domain aggregate is a domain contract, consistent with `LLMProvider` living in
  the domain). It speaks **only** in domain aggregates — never ORM rows or DTOs.
- Keep the interface minimal (YAGNI): `get(id)`, `add(conversation)`,
  `save(conversation)` (append via the loaded aggregate), and `next_sequence` /
  owner-scoped listing only as concrete use cases require them.
- Ship a **repository contract suite** (`tests/contract/repository_contract.py`),
  mirroring the provider contract suite. Every implementation must pass it:
  round-trip fidelity, sequence ordering, isolation between conversations,
  not-found semantics, and append/concurrency behavior. **This is the executable
  proof of the swap.**

### 2. Transaction boundary — minimal, single-aggregate; multi-aggregate UoW deferred

A chat turn is a read-modify-append-write on **one** aggregate and must be atomic
(the user message and the assistant reply persist together or not at all). We adopt
a **minimal explicit transaction boundary** — an application-layer
`atomic()` / transaction-scope abstraction — scoped to a single aggregate:

- In-memory: a copy-on-commit scope (mutations visible only on commit).
- SQLAlchemy: a session/transaction per scope (session-per-request).

We **do not** build a general multi-aggregate Unit of Work. ADR-0005 warned against
a speculative UoW; with exactly one aggregate per use case, a full UoW would be that
speculation. A multi-aggregate UoW is deferred until a use case genuinely spans
aggregates (e.g. M4 agent memory + conversation, or M6 billing).

> **Owner ratification point.** This is the one M2 decision with two defensible
> answers (minimal transaction scope now vs. repository-managed transactions with
> no application-visible boundary). We recommend the minimal explicit boundary
> because it keeps the application layer transaction-aware without leaking sessions,
> and because the read-append-write cycle is genuinely atomic — not speculative.

### 3. Relational mapping — separate ORM models + explicit translation

Domain aggregates stay **pure** (no ORM base class, no mapped columns, no SQLAlchemy
import — not even metadata). Persistence lives entirely in
`infrastructure/persistence/sqlalchemy`:

- SQLAlchemy models (`conversations`, `messages` tables) defined there.
- Explicit **mapping functions** translate domain ↔ ORM, exactly as
  `ollama/mapping.py` translates transport ↔ domain (ADR-0002 precedent).
- **Alembic** owns schema migrations (infrastructure concern).

New runtime dependencies (infrastructure only): `sqlalchemy[asyncio]`, `asyncpg`,
`alembic`. Async throughout, to match the async provider port and FastAPI.

### 4. Selection by configuration

`AIP__PERSISTENCE__BACKEND=memory|postgres` selects the implementation at the
composition root — no application/domain change, mirroring provider selection.

### 5. PostgreSQL in CI

Unlike the opt-in live Ollama tests, the repository contract suite runs against a
**real PostgreSQL service container in CI**. The swap claim is thereby proven on
every push, not merely asserted.

## Consequences

**Positive**
- The PostgreSQL swap is the cleanest possible Repository-pattern demonstration:
  change one binding, the identical contract suite stays green — verified in CI.
- Domain/application never import SQLAlchemy; the dependency rule holds trivially.
- Atomicity for the chat turn is explicit and testable.

**Negative / Costs**
- Domain↔ORM translation boilerplate (accepted; same trade-off as provider mapping).
- Async SQLAlchemy + `asyncpg` add operational surface (pooling, session lifecycle).
- Alembic introduces migration discipline earlier than a toy project would need.

## Alternatives Considered

- **Imperative/classical SQLAlchemy mapping of domain classes.** Rejected: even
  external mapping ties domain object shape to the mapper; separate models are
  cleaner and match the existing mapping precedent.
- **Active Record / ORM-coupled domain models.** Rejected by ADR-0005 already.
- **Full multi-aggregate Unit of Work now.** Rejected: speculative with one
  aggregate; revisit when a real cross-aggregate use case exists.
- **Opt-in-only PostgreSQL tests (like live Ollama).** Rejected: the swap is the
  milestone's headline claim and cheap to run in CI via a service container.

## Trade-offs Accepted

We accept mapping boilerplate, async-persistence operational surface, and early
Alembic discipline in exchange for a domain that is completely persistence-ignorant
and a swap that is proven in CI rather than asserted.
