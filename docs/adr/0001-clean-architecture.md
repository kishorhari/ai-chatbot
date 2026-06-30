# ADR-0001: Clean Architecture in a Modular Monolith

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Project Owner (Senior Backend Engineer), Principal Architect
- **Related:** ADR-0002 (Provider Abstraction), ADR-0005 (Repository Strategy)

## Context

We are building an enterprise-grade AI assistant platform from scratch. The
roadmap commits us to layering many features onto one core over time: chat,
conversation memory, streaming, prompt management, persistence, authentication,
RAG, agents, and ERPNext integration. Two forces dominate the design:

1. **Volatility of the outer edges.** The LLM provider (Ollama today, others
   later) and the storage backend (in-memory first, PostgreSQL later) are both
   *certain* to change. The cost of those swaps must be near-zero.
2. **A learning objective.** The owner is optimizing this codebase to *learn
   how AI applications are architected*, so the structure must make the
   dependency direction and boundaries obvious, not hide them behind magic.

We need an architecture that protects business rules from infrastructure churn,
keeps the system testable without a running Ollama or database, and stays a
single deployable at this stage.

## Decision

Adopt **Clean Architecture** with four concentric layers inside a **modular
monolith**, governed by the **Dependency Rule**: source dependencies point
inward only.

- **domain** — pure entities, value objects, ports (interfaces), and errors. No
  framework, no I/O, no logging imports.
- **application** — use cases / orchestration. Depends only on domain; depends
  on *ports*, never concrete adapters.
- **infrastructure** — adapters that implement domain ports (LLM providers,
  config, logging, future repositories). The only layer that touches the
  outside world.
- **interface** — delivery mechanisms (FastAPI HTTP, CLI dev probe). Depends on
  application.
- **composition** — the composition root; the single place permitted to import
  everything and wire concretes to ports at startup.

The rule is enforced **mechanically** in CI (e.g. `import-linter` contracts),
not by convention alone.

## Consequences

**Positive**
- Provider and storage swaps become configuration/wiring changes, not rewrites.
- Every layer above infrastructure is testable in isolation against fakes.
- The dependency direction is explicit and teachable — it serves the learning goal.
- Boundaries stay clean enough that extracting a service later (if ever needed)
  is cheap, without paying the distributed-systems tax now.

**Negative / Costs**
- More upfront ceremony: more packages, more indirection, more interfaces than a
  flat script-style app.
- Risk of over-abstraction if the rule is applied dogmatically to trivial code.
  Mitigation: keep value objects and use cases thin; only introduce a port where
  a real second implementation is foreseeable.

**Neutral**
- Requires discipline and a CI gate; a violated import is a build failure, not a
  review nit.

## Alternatives Considered

- **Layered N-tier / transaction-script** — simpler initially, but couples
  business logic to frameworks and storage, exactly the volatility we must
  insulate. Rejected.
- **Hexagonal / Ports & Adapters** — effectively the same philosophy; Clean
  Architecture is the variant we name here. Considered equivalent; we adopt
  Clean's layer vocabulary for clarity.
- **Microservices from day one** — premature distribution. We lack the scale,
  team size, and stable boundaries to justify the operational overhead.
  Rejected (see roadmap rationale).

## Trade-offs Accepted

We accept additional structural overhead and a CI enforcement gate in exchange
for swappability, testability, and a codebase whose dependency graph is its own
documentation.
