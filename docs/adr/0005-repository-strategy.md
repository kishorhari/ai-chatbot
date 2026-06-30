# ADR-0005: Repository Strategy (In-Memory First, PostgreSQL Later)

- **Status:** Accepted (strategy ratified now; first repository arrives at roadmap Step 4–5)
- **Date:** 2026-06-30
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0001 (Clean Architecture), ADR-0002 (Provider Abstraction)

## Context

Conversation identity is foundational to memory (roadmap Step 4–5), but
PostgreSQL persistence is deliberately deferred to Step 8. We therefore need a
way to build and test conversation/memory logic *before* a database exists,
without that logic becoming coupled to either in-memory structures or, later, to
SQLAlchemy. This ADR records the strategy now so Milestone 1's skeleton reserves
the correct seams, even though no repository is implemented in Milestone 1
itself.

## Decision

Adopt the **Repository pattern** with the interface owned by the inner layers and
implementations owned by infrastructure:

- A repository **port** (e.g. `ConversationRepository`) is defined in
  domain/application and speaks only in domain aggregates.
- The **first implementation is in-memory**, used for development and tests.
- A **PostgreSQL/SQLAlchemy implementation** is added at Step 8 and swapped in via
  the composition root — **no change to application or domain code**.
- The aggregate shape (`Conversation`, `Message`, owner/principal identity) is
  designed up front so it maps cleanly to relational storage later; storage is an
  implementation detail behind the port.

This is the same swap-by-configuration pattern proven by the Echo/Ollama provider
pair (ADR-0004) — the provider abstraction de-risks the repository abstraction.

## Consequences

**Positive**
- Conversation and memory logic is built and tested with zero database dependency.
- The PostgreSQL swap at Step 8 is the cleanest possible demonstration of the
  Repository pattern: change one binding, all tests still pass.
- Designing the aggregate before storage avoids an in-memory model that resists
  relational mapping.

**Negative / Costs**
- The in-memory implementation is throwaway-ish production-shaped code.
- Care is needed so the in-memory repo does not accidentally encode behavior
  (e.g. ordering, concurrency) that the SQL implementation cannot honor — the
  contract test suite for repositories (added at Step 4–5) guards this.

**Neutral / Deferred**
- **Unit of Work / transaction boundaries** are explicitly deferred to the
  persistence step (Step 8), when real transactions exist. We will not build a UoW
  abstraction over in-memory storage speculatively.

## Alternatives Considered

- **Active Record / ORM-coupled models** (entities that know how to persist
  themselves) — couples domain to SQLAlchemy, defeats the deferral, and blocks
  in-memory development. Rejected.
- **Direct SQLAlchemy queries inside services** — leaks persistence into the
  application layer and prevents the in-memory-first approach. Rejected.

## Trade-offs Accepted

We accept maintaining a temporary in-memory implementation and deferring
transaction concerns in exchange for building memory logic immediately,
database-free, behind a stable port that PostgreSQL slots into later.
