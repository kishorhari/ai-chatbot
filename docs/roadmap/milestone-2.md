# Development Roadmap — Milestone 2: Conversation & Persistence

**Scope:** Conversation identity and durable message history behind a repository
port; the first real chat use case (recall → window → assemble → generate); memory
as recent persisted history; and the in-memory → PostgreSQL swap proven by one
shared repository contract suite.

**Out of scope (deferred):** semantic recall / RAG (M3), tool calling / agents (M4),
summary-based long-term memory, multi-aggregate Unit of Work, SSE streaming HTTP
delivery, authentication / multi-tenancy (M6). Cloud providers (M7) remain
untouched; a thin third-provider spike to re-prove the port is a **prerequisite to
M4**, not part of M2.

**Governing ADRs:** [0007](../adr/0007-conversation-message-aggregate.md) (aggregate),
[0008](../adr/0008-persistence-repository-and-transactions.md) (persistence),
[0009](../adr/0009-context-window-and-prompt-assembly.md) (memory/assembly).
Foundational: [0005](../adr/0005-repository-strategy.md) (repository strategy).

---

## 1. Sub-milestones

| ID | Sub-milestone | Goal |
|----|---------------|------|
| M2.0 | Conversation aggregate | `Conversation` root + `Message` entity, IDs, sequence, ownership, invariants — pure domain |
| M2.1 | Repository port + contract suite + in-memory | `ConversationRepository` port, the shared repository contract suite, in-memory impl passing it |
| M2.2 | Memory & prompt assembly | `ContextWindowPolicy`, `TokenEstimator` seam, `PromptAssembler` → `CompletionRequest` |
| M2.3 | Chat use case + transaction boundary | Application service tying recall/window/assemble/generate; atomic user+assistant persist |
| M2.4 | Delivery + composition | Conversation HTTP endpoints (+ CLI), backend selection by config |
| M2.5 | PostgreSQL repository | SQLAlchemy models + mapping + Alembic; same contract suite green against real Postgres in CI |
| M2.6 | Hardening & gates | Dependency-rule updates, coverage, docs, exit review |

> **Reserved ahead of schedule:** the `application/clock.py` `Clock` port (the
> application's source of "now") is introduced now, before its M2.3 consumer, so
> the application layer never reaches for `datetime.now()` directly and use cases
> stay deterministic. The domain already takes injected, timezone-aware timestamps
> (ADR-0007); this is the seam that will supply them.

The order is dependency-driven: the aggregate (M2.0) precedes the repository
(M2.1); the repository and contract suite exist before the SQL implementation
(M2.5) so the swap is a binding change; memory/assembly (M2.2) precede the use case
(M2.3) that consumes them; the use case precedes delivery (M2.4). PostgreSQL is the
**capstone** — it proves the abstraction, so it comes last.

---

## 2. File implementation order

Within `src/aiplatform/` (never implement a file before the inner files it imports
exist):

```
M2.0  domain/conversation/ids.py                 ConversationId, MessageId
      domain/conversation/message.py             Message entity (Role, sequence, created_at, TokenUsage?)
      domain/conversation/conversation.py        Conversation aggregate root + invariants

M2.1  domain/conversation/ports.py               ConversationRepository (port)
      tests/contract/repository_contract.py       shared repository contract suite
      infrastructure/persistence/memory/repository.py   InMemoryConversationRepository

M2.2  application/conversation/token_estimator.py TokenEstimator port + heuristic default
      application/conversation/context_window.py  ContextWindowPolicy
      application/conversation/prompt_assembler.py PromptAssembler -> CompletionRequest

M2.3  application/clock.py                          Clock port (source of "now") — RESERVED EARLY
      application/conversation/transaction.py     minimal atomic() scope (port)
      application/conversation/chat_service.py     the chat use case (consumes Clock)
      infrastructure/persistence/memory/transaction.py  copy-on-commit scope

M2.4  interface/http/routes/conversations.py       create / append / fetch endpoints
      interface/cli/chat.py                         CLI chat loop (optional, reuses probe patterns)
      composition/container.py (extend)             wire repository + chat service by config

M2.5  infrastructure/persistence/sqlalchemy/models.py       tables
      infrastructure/persistence/sqlalchemy/mapping.py      domain <-> ORM
      infrastructure/persistence/sqlalchemy/repository.py   SqlAlchemyConversationRepository
      infrastructure/persistence/sqlalchemy/transaction.py  session/transaction scope
      migrations/ (alembic)                                  initial schema

M2.6  .importlinter (persistence contracts), CI (postgres service), docs, exit review
```

---

## 3. Dependency graph (build-time)

```
domain/llm (Role, TokenUsage, ChatMessage, CompletionRequest)   ← frozen (M1)
        ▲                                   ▲
        │ reuses VOs                        │ maps Message → ChatMessage
domain/conversation                 application/conversation
  (Conversation, Message, ids,        (chat_service, prompt_assembler,
   ConversationRepository port)         context_window, token_estimator,
        ▲            ▲                   transaction port)
        │            │                          ▲
        │            └──────────────────────────┤ depends on domain ports only
        │                                        │
infrastructure/persistence/memory       infrastructure/persistence/sqlalchemy
  (in-memory repo + txn)                   (models, mapping, repo, txn, alembic)
        ▲                                        ▲
        └──────────────── composition ──────────┘  selects backend by config,
                              ▲                     builds chat service
                              │
                     interface/http/routes/conversations, interface/cli/chat
```

Dependencies flow inward to `domain`. `application/conversation` depends only on
domain ports. Both repository implementations depend only on domain (aggregate +
port). `composition` is the only multi-layer importer. The frozen `domain/llm` port
is reused, never modified.

---

## 4. Deliverables

- `Conversation` aggregate + `Message` entity: domain-generated IDs, explicit
  sequence, ownership field, append-only immutability, invariants on the root.
- `ConversationRepository` port + a **shared repository contract suite**.
- Two repository implementations — **in-memory** and **PostgreSQL/SQLAlchemy** —
  passing the identical suite; selectable via `AIP__PERSISTENCE__BACKEND`.
- `ContextWindowPolicy` + `TokenEstimator` seam honoring `max_context_tokens`.
- `PromptAssembler` producing the existing `CompletionRequest` (port unchanged).
- A **chat use case** with an atomic (single-aggregate) transaction boundary.
- Conversation HTTP endpoints (create, append message, fetch history) + optional CLI
  chat loop, wired at the composition root.
- Alembic migrations for the initial schema.
- CI running the repository contract suite against a **real PostgreSQL** service
  container; dependency-rule contracts extended to the persistence layer.
- Updated docs: ADR-0007..0009, this roadmap, and an M2 exit review.

---

## 5. Definition of Done (per deliverable / PR)

A unit of M2 work is "done" only when **all** of the following hold — the same bar
as M1, extended for persistence:

- [ ] Lint + format clean (`ruff check`, `ruff format --check`).
- [ ] `mypy src` passes (strict on `domain`/`application`, including the new
      `conversation` packages).
- [ ] `lint-imports` passes — no domain/application import of SQLAlchemy or of any
      persistence adapter; the frozen `domain/llm` port is unmodified.
- [ ] Tests pass: unit for new logic; the repository contract suite for any new
      repository; integration for the SQLAlchemy path.
- [ ] Any new `ConversationRepository` implementation passes the shared contract
      suite unchanged.
- [ ] No secret/credential logged; DB DSN read only through `Settings`
      (`SecretStr` for the password).
- [ ] Aggregate invariants (sequence contiguity, single system message, ownership)
      are enforced in the domain and tested.
- [ ] Docs/ADRs/CHANGELOG updated where behavior or a decision changed.

---

## 6. Exit criteria (Milestone 2 is "done" when)

1. **Round-trip through the port** — a conversation can be created, messages
   appended, and full history retrieved with correct sequence ordering; verified by
   test.
2. **Swap proven by one suite** — the in-memory and PostgreSQL repositories pass the
   **identical** repository contract suite, and PostgreSQL runs it in CI via a
   service container.
3. **Port frozen, rule intact** — the M1 `LLMProvider` / `CompletionRequest` are
   unchanged; `domain`/`application` import no SQLAlchemy; all dependency contracts
   pass.
4. **Swap is config-only** — `AIP__PERSISTENCE__BACKEND=memory|postgres` switches
   backends with no application/domain code change, verified.
5. **Context budget respected** — assembled prompts never exceed
   `max_context_tokens`; the system prompt is always retained; overflow drops oldest
   first; verified at the boundaries.
6. **Valid prompt assembly** — the chat use case produces a well-formed
   `CompletionRequest` (single system message, correct ordering) from stored history
   + new turn.
7. **Atomic chat turn** — the user message and assistant reply persist together; a
   simulated mid-cycle failure leaves no partial write; verified.
8. **Invariants + coverage** — message immutability and aggregate invariants are
   enforced and tested; `domain`/`application` at ≥ 95% coverage.
9. **Docs current** — ADR-0007..0009, this roadmap, the repository contract-suite
   documentation, and the M2 exit review reflect the shipped code.

---

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|:----------:|:------:|------------|
| In-memory repo encodes behavior PostgreSQL can't honor (ordering, concurrency, txn semantics) | Medium | High | Repository contract suite runs against **real PostgreSQL in CI** from M2.5; write the suite before the SQL impl. |
| Aggregate resists relational mapping | Low | High | Designed for relational mapping up front (ADR-0007); separate ORM models + explicit mapping (ADR-0008). |
| Token estimation inaccuracy → context overflow or over-truncation | Medium | Medium | Conservative over-counting heuristic + response reservation; exact tokenization deferred behind the `TokenEstimator` seam. |
| Transaction-boundary scope creep (premature multi-aggregate UoW) | Medium | Medium | Single-aggregate `atomic()` only; multi-aggregate UoW explicitly deferred (ADR-0008). |
| Async SQLAlchemy / `asyncpg` operational surface (pooling, session lifecycle) | Medium | Medium | Session-per-request; pool config in `Settings`; load tuning deferred until concurrency exists. |
| Correlation ID not carried across the DB session lifecycle | Low | Low/Med | Reuse the logging kernel (ADR-0006); assert correlation on persistence log lines. |
| Scope: M2 is large (aggregate + repo + memory + use case + delivery + Postgres) | Medium | Medium | Sub-milestones M2.0–M2.6; PostgreSQL as the capstone; each sub-milestone independently verifiable. |
| Building further on a port still unproven vs SSE/tool-call providers | Low (for M2) | Medium | M2 is layer-orthogonal to the port's transport shape; schedule a thin third-provider spike as a **prerequisite to M4**. |

---

## 8. Trade-offs accepted

- **Two message representations** (stored `Message` vs transport `ChatMessage`) and
  a mapping step — for a storage-ready aggregate that keeps the frozen port clean
  (ADR-0007).
- **Domain↔ORM translation boilerplate** — for a completely persistence-ignorant
  domain (ADR-0008), the same trade-off already accepted for provider mapping.
- **Explicit sequence integers** over timestamp ordering — determinism over
  convenience.
- **Literal recent-history memory** (no summarization) with lossy windowing — a
  small, honest M2; summary memory and RAG come later.
- **Heuristic token estimation** — zero new heavy dependencies now, at the cost of
  approximate budgeting, bounded by a conservative reservation.
- **Minimal single-aggregate transaction boundary** — atomicity where it is
  genuinely needed, without a speculative Unit of Work.
- **PostgreSQL in CI** (service container) rather than opt-in — more runner cost for
  a swap claim that is *proven*, not asserted.
