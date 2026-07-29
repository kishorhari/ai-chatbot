# Milestone 2 — Final Retrospective

**Status:** Milestone 2 (Conversation & Persistence) complete. This is the closing
engineering document for M2.

**Headline metrics:** 5 layers (unchanged) · one `ConversationRepository` port
proven across 3 backends by 1 contract suite · one chat use case with a verified
atomic boundary · 5 mechanically-enforced dependency contracts · 4 new ADRs
(0007–0010) · domain + application coverage **100%** · 325 offline tests
(+11 PostgreSQL-only, CI).

---

## 1. Milestone objective

M1 delivered a stateless vertical slice: a provider-agnostic `LLMProvider` port,
two providers behind one contract suite, and HTTP/CLI delivery — but no memory. A
conversation was a single request with no past and no future.

Milestone 2 set out to add the platform's **first stateful domain** —
conversation identity and durable message history — and the first genuinely
*orchestrated* use case (a chat turn that recalls history, fits it to a budget,
assembles a prompt, generates, and persists atomically), **without** disturbing
the frozen M1 port or leaking persistence into the business logic. The defining
success criterion was behavioral: prove the storage backend is swappable by
running the *same* contract suite against an in-memory store and a real
PostgreSQL, exactly as M1 proved provider-swappability with Echo and Ollama.

The bet was that the boundaries established in M1 would absorb a stateful domain
and a real database as additive infrastructure, not as a rewrite.

## 2. Architectural concepts introduced

Each concept exists to hold a specific boundary; none was added speculatively.

- **Conversation aggregate** (`domain/conversation`). A `Conversation` root owning
  append-only `Message` entities, with identity, contiguous `sequence`, ownership,
  and the single-leading-system-message rule enforced *on the root*. It exists so
  history has one consistency boundary and one place its invariants live, and so
  the model maps cleanly to relational storage later (ADR-0007).
- **Repository pattern** (`ConversationRepository` port). A domain-owned interface
  speaking only in aggregates. It exists to invert the persistence dependency:
  application code depends on the port, never on a database.
- **Repository contract testing** (`repository_contract.py`). One executable
  behavioral spec every backend must satisfy. It exists to make "the abstraction
  is real" a *fact* (three passing backends) rather than a hope — the same device
  as the provider contract suite.
- **Prompt pipeline** (context window → assembler). The staged transformation from
  stored history to a provider request. It exists to keep budgeting and
  request-building as small, single-purpose, independently-testable steps.
- **Context window** (`ContextWindowPolicy`). Chooses which messages fit a model's
  token budget — always keep the system prompt, then most-recent-first, drop the
  oldest that do not fit. It exists because context is finite and recency matters
  most; a lossy, deterministic policy is honest about that.
- **Token estimation** (`TokenEstimator` seam + heuristic default). A conservative
  character-based over-estimate behind a port. It exists to budget *without*
  taking on a heavy per-provider tokenizer dependency now, while leaving the seam
  for an exact tokenizer later.
- **ChatService** (application service). Orchestrates one chat turn:
  recall → append user → window → assemble → generate → append assistant →
  persist atomically. It exists as the single home for that flow (ADR-0010) so no
  route or builder coordinates it.
- **ConversationService** (application service). Conversation lifecycle and
  retrieval (create, fetch). It exists so *creating* a conversation (aggregate
  construction + clock + atomic persist) is orchestration in the application
  layer, not logic in an endpoint.
- **Transaction boundary** (`TransactionBoundary` port + `atomic()`). An
  application-owned scope delimiting one atomic unit of work. It exists so the
  application decides *when* work commits without ever seeing a session, and so
  atomicity is a testable contract rather than an implementation accident.
- **Composition root** (extended `container.py`). The one place concretes are
  wired to ports and the persistence backend is chosen by config. It exists to
  keep every other layer ignorant of concrete types and their lifecycles.
- **SQLAlchemy repository** (+ session provider). The production persistence
  backend over async SQLAlchemy/asyncpg. It exists as the second repository
  implementation — the one that proves the swap against a real database.
- **Explicit mapping layer** (`sqlalchemy/mapping.py`). Pure functions translating
  aggregate ↔ ORM rows. It exists so the domain carries no ORM base class, column,
  or SQLAlchemy import — persistence stays a detail behind the port (ADR-0008).

## 3. ADR summary

**ADR-0007 — Conversation and Message Aggregates.**
*Problem:* the first stateful domain must map cleanly to SQL later, feed prompt
assembly, and absorb tenancy/agents additively, without dragging persistence
toward the frozen provider port. *Decision:* a shallow `Conversation` (1) → (N)
`Message` aggregate; domain-generated UUIDs; append-only immutable messages;
explicit `sequence` ordering (never timestamps); an `owner` from day one; a stored
`Message` distinct from the transport `ChatMessage`; invariants on the root.
*Consequences:* persistence-ready by construction and free of ordering/concurrency
ambiguity; the cost is a second message representation and a mapping step
(accepted, mirroring provider mapping).

**ADR-0008 — Persistence: Repository Contract, Transaction Boundary, Relational
Mapping.** *Problem:* ADR-0005 deferred the Unit-of-Work question to "the
persistence step"; M2 is it. *Decision:* a domain `ConversationRepository` port +
shared contract suite; a *minimal, single-aggregate* `atomic()` boundary (no
speculative multi-aggregate UoW); separate ORM models + explicit mapping (no ORM
in the domain); backend by `AIP__PERSISTENCE__BACKEND`; the suite runs against real
PostgreSQL in CI. *Consequences:* the swap is proven, not asserted; the domain
never imports SQLAlchemy; atomicity is explicit — at the cost of mapping
boilerplate and async-persistence operational surface.

**ADR-0009 — Context-Window Selection and Prompt Assembly.**
*Problem:* fit arbitrarily long history into a finite context budget and build a
valid request, without a heavy tokenizer dependency and without letting assembly
become orchestration. *Decision:* a deterministic `ContextWindowPolicy` (retain
system, most-recent-first, drop oldest, reserve room for the reply) over a
`TokenEstimator` seam (conservative heuristic default); a **pure** `PromptAssembler`
that maps resolved messages to a `CompletionRequest` and does nothing else.
*Consequences:* budgeting is approximate but bounded by a conservative reservation;
an exact tokenizer can slot in behind the seam; assembly stays orchestration-free.

**ADR-0010 — Application Service Layer.**
*Problem:* the chat turn spans repository, clock, transaction, assembler, and
provider — that coordination needs a home, and neither the delivery layer nor the
prompt assembler may own it. *Decision:* a thin application-service layer (plain
injected classes, not swappable ports) owning use-case flow and the transaction
boundary; the assembler stays a pure builder; delivery stays thin. *Consequences:*
prompt assembly is provably single-purpose and the use case is testable with
fakes; the cost is one more architectural term, mitigated by keeping services thin
and rare.

## 4. Major architectural decisions

- **Generation outside the transaction.** `complete_chat` is slow and cancellable;
  holding a database transaction across it would pin a connection and extend locks
  for the duration of an LLM call. The turn instead reads, generates *outside* any
  transaction, then performs a single atomic `save`. *Rejected:* wrapping the whole
  turn in one transaction (simple, but couples DB-hold time to model latency).
- **Stateless application services.** All per-request state lives in locals;
  services and collaborators are shared singletons. This makes concurrency trivial
  and construction a one-time composition concern. *Rejected:* per-request service
  instances (needless allocation and lifecycle).
- **Explicit mapping** (domain ↔ ORM) over an ORM-mapped domain. Keeps the domain
  import-free of SQLAlchemy and the dependency rule trivially true. *Rejected:*
  Active Record and imperative/classical mapping — both tie the domain's shape to
  the mapper (ADR-0008).
- **Repository contract suite** as the definition of "done" for a backend. One
  spec, N implementations. *Rejected:* per-backend bespoke tests (combinatorial
  maintenance; no shared guarantee).
- **Append-only persistence.** A message is never mutated; edits/regenerations are
  new messages. Removes update/concurrency ambiguity and gives an audit trail;
  `save` inserts only messages beyond those stored. *Rejected:* mutable messages
  (no clean SQL story, concurrency pain — ADR-0007).
- **Prompt-assembly purity.** The assembler builds a `CompletionRequest` and does
  nothing else — no recall, persistence, provider call, or transaction. Keeps the
  most-likely-to-grow component single-purpose. *Rejected:* an assembler that also
  recalls/persists (the exact conflation ADR-0010 forecloses).
- **DTO boundaries.** Services return immutable DTOs (`ChatResult`,
  `ConversationView`), never the aggregate, so delivery renders without reaching
  into the domain. *Rejected:* returning aggregates to delivery (leaks the domain
  into transport and invites mutation).
- **Dependency-rule enforcement** by `import-linter`, extended in M2 to forbid
  SQLAlchemy in domain/application and repository adapters in delivery. A boundary
  violation is a failed build, not a review nit. *Rejected:* convention-only
  discipline (rots silently).

## 5. Repository evolution

```
ConversationRepository (domain port, speaks only in aggregates)
        ↓ implemented by
InMemoryConversationRepository (dict; snapshot on read+write)
        ↓ validated against
the shared ConversationRepositoryContract (11 invariants)
        ↓ then the same port implemented by
SqlAlchemyConversationRepository — exercised locally over SQLite (aiosqlite)
        ↓ and authoritatively over
real PostgreSQL in CI (service container)
        ↑ all three bound to
one contract suite — unchanged
```

Why this demonstrates architectural correctness: the *port and its behavioral
contract were fixed before the SQL implementation existed*. Adding PostgreSQL was
therefore a binding change, not a redesign — the identical suite that the
in-memory store passes is the acceptance test the SQL store must also pass. Three
independent implementations satisfying one unchanged spec is executable proof that
the abstraction is real and that `domain`/`application` are genuinely
persistence-ignorant (the `import-linter` `core-persistence-agnostic` contract
guarantees they hold no SQLAlchemy import). Snapshot independence — a loaded
aggregate's mutation never reaching storage until `save` — is part of the
*contract*, so both backends honor it; PostgreSQL does so intrinsically (each load
rehydrates from rows), and a dedicated transaction test proves **real rollback** on
the SQL path, which the in-memory pass-through cannot demonstrate.

## 6. Prompt pipeline evolution

```
Conversation (stored aggregate: full, ordered, append-only history)
        ↓  ChatService recalls it and appends the new user message
ContextWindowPolicy.select(messages, max_context_tokens)
        ↓  chooses the messages that fit the budget (system + most-recent)
PromptAssembler.assemble(windowed, model)
        ↓  maps stored Message → transport ChatMessage, validates placement
CompletionRequest  (the frozen M1 value object — unchanged)
        ↓  ChatService hands it to the resolved provider
LLMProvider.complete_chat(request)  →  reply text + usage
```

Responsibilities, each single-purpose:

- **Conversation** — owns history and its invariants; the source of truth.
- **ContextWindowPolicy** — *selection only*: retain a leading system message,
  include most-recent messages while they fit `max_context_tokens` minus a
  response reservation, drop the oldest that do not, preserve order; guarantees at
  least the newest message. Uses a `TokenEstimator` (conservative heuristic) to
  cost messages.
- **PromptAssembler** — *building only*: project the resolved messages onto
  `ChatMessage`, enforce single-leading-system placement, produce a
  `CompletionRequest`. No recall, persistence, provider call, or transaction.
- **CompletionRequest / LLMProvider** — the frozen M1 seam, reused verbatim; M2
  added no provider-port change.
- **ChatService** — the only orchestrator, sequencing the above and owning the
  transaction boundary around the final persist.

The pipeline is a chain of pure transformations bracketed by the one service that
coordinates them — which is why each stage is unit-testable in isolation and why
the frozen port needed no modification.

## 7. Delivery layer

- **HTTP** (`interface/http/routes/conversations.py`): three endpoints —
  `POST /conversations` (create, optionally with a system prompt),
  `POST /conversations/{id}/messages` (a chat turn),
  `GET /conversations/{id}` (fetch history). Each handler parses/validates
  transport input, calls **one** application-service method resolved from the
  container, and maps a DTO to a pydantic wire model. Domain/application errors
  become HTTP status via app-level exception handlers (`ConversationNotFound` →
  404, `LLMError` → 502) — transport translation, not business logic.
- **CLI** (`interface/cli/chat.py`): a multi-turn chat that boots the container,
  creates a conversation, and drives each turn through the same services — the
  offline, HTTP-free way to exercise the whole use case (verified against Echo).
- **Composition root** (`composition/container.py`): the sole place that imports
  concretes and wires them to ports — providers, the persistence backend (by
  config), the clock, the pipeline collaborators, and both services (sharing one
  repository). It also owns disposal (HTTP clients, the DB engine).
- **Dependency injection**: services receive their collaborators as constructor
  arguments; delivery receives services from the container via `app.state`; nothing
  above infrastructure constructs a concrete. The `Clock` and `TransactionBoundary`
  ports keep even "now" and "commit" injectable.

Delivery stays thin because every decision that is *not* transport — orchestration,
persistence, generation, time — lives behind a port or a service. This is enforced,
not merely intended: `import-linter` forbids the interface from importing a
provider adapter, a persistence adapter, or configuration directly. Adding a fourth
delivery surface (SSE, gRPC) would reuse the services unchanged.

## 8. Testing strategy

- **Unit tests** — pure logic in isolation: aggregate invariants (sequence,
  single-system, immutability, ownership), context-window selection (budget,
  system retention, oldest-drop, order, reservation), prompt-assembler placement
  rules, token estimator, mapping round-trips, settings.
- **Contract tests** — the shared `ConversationRepositoryContract` (11 invariants)
  run against **in-memory**, **SQLite-SQL**, and **PostgreSQL-SQL**; the provider
  contract suite from M1 still runs against Echo and respx-mocked Ollama.
- **Integration tests** — the HTTP create→append→fetch flow via `TestClient`
  against Echo; the container end-to-end (create → chat → fetch) over a shared
  repository.
- **Rollback tests** — `atomic()` on the SQL path: a mid-scope failure leaves no
  write (real transaction), plus service-level `provider_error_persists_nothing`
  and `save_failure_leaves_no_partial_write`.
- **Coverage** — `domain` + `application` at **100%** (target ≥ 95%); a diagnostic,
  not the goal.
- **import-linter** — five contracts run as a gate (layering, inner purity,
  interface adapter ban, settings-log-free, persistence-agnostic core).
- **CI** — lint → type-check → dependency rule → `alembic upgrade head` against a
  **PostgreSQL 16 service container** → the full suite with the Postgres DSN set,
  so the swap is proven on every push.

Why this validates *architecture*, not just implementation: the contract suites
assert **behavior a boundary promises**, independent of who implements it. Two
providers and three repositories passing unchanged suites is evidence the ports
are genuine seams; `import-linter` proves the dependency direction the ADRs claim;
the rollback tests prove the transaction boundary is real. The tests would catch a
boundary regression (e.g. the domain importing SQLAlchemy, or a backend violating
snapshot independence) that a coverage number never would.

## 9. Risks deferred

All deferrals are deliberate, to keep M2 honest and small:

- **RetryPolicy** — `retryable`/`retry_after` are data on `LLMError`; no policy
  consumes them yet. Belongs in the application layer once a real retry need exists.
- **Optimistic concurrency** — M2 is single-writer; the unique `(conversation_id,
  sequence)` constraint is the current guard. Version columns / conflict handling
  wait for concurrent writers.
- **Streaming (SSE) delivery** — the provider port already streams; exposing it
  over HTTP is a transport concern (roadmap Step 7), not a core change.
- **Tool calling** — additive provider capability + a future contract revision;
  out of M2's persistence scope.
- **RAG / semantic recall** — M3; M2's memory is literal recent history by design.
- **Conversation summarization** — long-term memory beyond the window; deferred
  with the windowing policy left as the seam.
- **Multi-tenancy** — the `owner` field exists from day one so M6 adds enforcement,
  not a column.
- **Authentication** — identity enters at the delivery boundary later; today
  `owner` is supplied explicitly.
- **Background jobs / workers** — no async work queue yet; correlation propagation
  across spawned tasks is noted for when one appears.

Each is deferred because building it now would be speculation against an unproven
need — the same discipline that kept the transaction boundary single-aggregate.

## 10. Lessons learned

- **The contract-suite pattern generalized cleanly.** What proved the provider
  abstraction in M1 proved the repository abstraction in M2 with no new machinery —
  a strong signal the pattern is a reusable tool, not a one-off.
- **The M1 boundaries held under weight.** Adding a stateful domain and a real
  database touched no domain/application code except by addition; the frozen port
  stayed frozen. The upfront boundary cost paid off exactly as intended.
- **Simpler than expected:** the PostgreSQL swap. Because the port and contract
  existed first, the SQL backend was "implement three methods + a mapping + a
  migration," and the existing suite was its acceptance test — no redesign, no
  caller changes.
- **Required more thought:** the transaction/session sharing. Making `atomic()`
  application-owned while the repository and boundary transparently share one
  session (without leaking sessions into the application) needed a context-variable
  session provider and care that generation stays *outside* the transaction. This
  was the subtlest part of M2.
- **Principles that emerged (or hardened):**
  - *Fix the contract before the implementation* — the behavioral spec is the
    acceptance test the next backend must pass.
  - *Snapshot/rollback semantics belong to the port contract*, not to an
    implementation — so every backend honors them.
  - *Orchestration has exactly one home* (the application service); builders and
    delivery stay pure/thin, enforced mechanically.
  - *Defer transactional and concurrency machinery until a real multi-writer or
    multi-aggregate use case exists* — speculation is the expensive mistake.

## 11. Milestone outcome

Milestone 2 delivered conversation identity and durable message history behind a
domain-owned repository port, a budget-aware prompt pipeline feeding the unchanged
M1 provider port, and an atomic chat use case coordinated by a thin application
service. The repository abstraction is proven — not asserted — by one contract
suite passing against in-memory, SQLite, and real PostgreSQL (the last in CI), and
the chat turn's atomicity is verified down to a real database rollback. The
domain and application layers remain infrastructure-ignorant and the M1 ports are
untouched, both facts mechanically enforced by five `import-linter` contracts.

The platform now has a tested, swappable persistence foundation and its first
orchestrated use case, built additively on the M1 core. It is ready for the
higher-order features (streaming transport, retrieval, tools, tenancy) that will
sit on top of these boundaries — which remain the load-bearing structure, not a
thing to be rewritten.
