# ADR-0010: Application Service Layer (Use-Case Orchestration)

- **Status:** Accepted
- **Date:** 2026-07-10
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0001 (Clean Architecture), ADR-0002 (Provider Abstraction), ADR-0007 (Aggregate), ADR-0008 (Persistence & Transaction Boundary), ADR-0009 (Context Window & Prompt Assembly)

## Context

Milestone 2 introduces the platform's first genuinely *orchestrated* use case: a
chat turn must **recall** a conversation (repository), **window** its history to a
token budget (`ContextWindowPolicy`), **assemble** a request
(`PromptAssembler` → `CompletionRequest`), **generate** a reply (`LLMProvider` via
the registry), and **persist** the user message and assistant reply **atomically**
(repository within a transaction boundary, ADR-0008).

That coordination has to live *somewhere*. Two anti-patterns are tempting and must
be foreclosed explicitly:

1. **Orchestration in the delivery layer** (an HTTP route or the CLI driving
   repository + provider + assembler directly). This couples transport to the use
   case, duplicates the flow across surfaces, and violates the thin-delivery rule
   already established in M1 (interface holds no business logic).
2. **Orchestration in `PromptAssembler`** (the assembler recalling history or
   writing messages). This overloads a component whose single responsibility is to
   turn a resolved set of messages into a `CompletionRequest`, and it would drag
   persistence concerns into prompt construction.

The M1 pattern gives the template: the domain owns pure rules and ports; adapters
implement ports; the composition root wires concretes. What M1 did not yet need —
because a single provider call is not a multi-step use case — is a named home for
*use-case coordination*. M2 needs it.

## Decision

Ratify a thin **Application Service layer** in the `application` package as the
home for use-case orchestration.

### 1. What an application service is

- A **concrete coordinator of one use case** (e.g. `ChatService.send_message`),
  living in `application/conversation/`.
- It depends **only on ports and pure collaborators** — `ConversationRepository`
  (domain port), the transaction scope (application port, ADR-0008), `Clock`
  (application port), `PromptAssembler` / `ContextWindowPolicy` /
  `TokenEstimator` (application-layer pure components), and `LLMProvider` /
  `ProviderRegistry` (domain/application ports). It **never** imports a concrete
  adapter, `httpx`, SQLAlchemy, or a framework.
- It is **not a swappable port** and therefore needs **no ABC/Protocol**: unlike
  `LLMProvider` or `ConversationRepository`, there is one implementation per use
  case. It is a plain class, constructed by the composition root with its
  dependencies injected. (This is a deliberate contrast with the repository/provider
  ports — services orchestrate ports, they are not themselves swapped.)

### 2. Responsibility boundaries (the point of this ADR)

- **Application service** owns the *flow* and the **transaction boundary**: recall →
  window → assemble → generate → persist-atomically. It translates between the
  conversation aggregate and the provider port (mapping stored `Message` history
  into the assembler's input), and it is the single place that opens the
  `atomic()` scope (ADR-0008).
- **`PromptAssembler` stays pure**: given already-resolved messages and a policy,
  it produces a `CompletionRequest` and nothing else. It performs no recall, no
  persistence, no provider call, no transaction. (This is the boundary the review
  asked to protect.)
- **Domain aggregate** keeps its invariants (sequence, single system message,
  ownership); the service coordinates but never re-implements aggregate rules.
- **Delivery** (HTTP/CLI) stays thin: it validates/adapts transport, calls **one**
  application-service method, and maps the result to a response — no business flow.

### 3. Dependency direction

`interface → application service → { domain ports, application ports } → domain`.
Concrete adapters (repository backend, provider) are injected by `composition`. The
service imports no infrastructure. This is enforced by the existing layered
`import-linter` contract (`domain < application < infrastructure`) with no new
contract required for M2.2–M2.3; persistence-specific contracts arrive with M2.5.

## Responsibilities / Non-Responsibilities

Recorded explicitly so the boundary survives as more use cases and delivery
surfaces are added. If a change would add any item from the right-hand column to a
service, it belongs in the named collaborator instead.

**The application service (e.g. `ChatService`) IS responsible for:**

- **Use-case flow** — sequencing recall → window → assemble → generate →
  persist-atomically for one use case.
- **The transaction boundary** — opening the single `atomic()` scope (ADR-0008) so
  the user message and the assistant reply persist together or not at all.
- **Collaborator coordination** — selecting resolved history via
  `ContextWindowPolicy`, handing it to `PromptAssembler`, resolving the provider
  via the registry, and invoking the `LLMProvider` port.
- **Time acquisition** — obtaining "now" from the `Clock` port and passing it into
  the aggregate (the domain never reads the clock, ADR-0007).
- **Result/error translation** — presenting domain, repository, and provider
  outcomes coherently to its caller.

**The application service is NOT responsible for (must delegate):**

- **Building the `CompletionRequest`** — that is `PromptAssembler` (a pure builder;
  Message → ChatMessage mapping, ordering/single-system validation).
- **Windowing / token budgeting** — `ContextWindowPolicy` + `TokenEstimator`.
- **Aggregate invariants** — sequence contiguity, single leading system message,
  ownership — enforced by `Conversation`; the service coordinates, never
  re-implements them.
- **Persistence mechanics** — snapshotting, ordering, SQL, sessions — owned by the
  `ConversationRepository` implementations.
- **Reading the system clock** — behind the `Clock` port.
- **Transport concerns** — HTTP/CLI parsing, serialization, status codes, auth —
  owned by the delivery layer.
- **Vendor/transport specifics** — request/response shapes, transport errors —
  owned by provider adapters, surfaced only as the domain `LLMError` taxonomy.

## Consequences

**Positive**
- Prompt assembly is provably single-purpose; the review's concern is structural,
  not conventional.
- The chat use case is testable in isolation with fakes (fake repo, fake clock,
  Echo provider) — no HTTP, no DB.
- New delivery surfaces (SSE later, gRPC hypothetically) reuse the same service
  unchanged.
- The transaction boundary has one owner, matching ADR-0008.

**Negative / Costs**
- One more layer/vocabulary term. Mitigated: services are thin and only appear when
  a use case genuinely spans multiple ports; single-port pass-throughs do not get a
  service.

## Alternatives Considered

- **Orchestrate in delivery.** Rejected: couples transport to use case, duplicates
  across surfaces, violates thin delivery.
- **Orchestrate in `PromptAssembler`.** Rejected: overloads a pure builder with
  persistence/provider coordination — the exact conflation this ADR prevents.
- **Make the service a swappable port (ABC).** Rejected as speculation: there is one
  implementation per use case; a port with a single implementation is ceremony
  without payoff (contrast the genuinely-two-implementation repository/provider
  ports).

## Sequencing note (no roadmap reorder)

The roadmap already realizes this layer: `PromptAssembler` (M2.2) is the pure
builder; `chat_service` (M2.3) is the application service. `chat_service` **depends
on** `PromptAssembler`, so it correctly follows it in implementation order — a
service cannot precede the collaborator it orchestrates. This ADR **ratifies the
boundary ahead of both**, so M2.2 is implemented knowing the assembler must remain
orchestration-free. No milestone is reordered.

## Trade-offs Accepted

We accept one additional architectural concept (the application service) in
exchange for a single, testable home for use-case orchestration and a prompt
assembler that stays a pure `CompletionRequest` builder.
