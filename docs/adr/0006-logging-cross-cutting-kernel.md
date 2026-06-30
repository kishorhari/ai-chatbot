# ADR-0006: Logging/Correlation as a Cross-Cutting Kernel

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Project Owner, Principal Architect
- **Related:** ADR-0001 (Clean Architecture), M1.6 (delivery surfaces)

## Context

The Dependency Rule (ADR-0001) keeps source dependencies pointing inward, and the
original `import-linter` contract enforced this by declaring `interface` and
`infrastructure` to be **independent siblings** — neither could import the other.
The intent behind that rule, as written in the dependency matrix, was narrow and
correct: *the interface (delivery) layer must never import a concrete provider
adapter; it receives providers only via the wired registry from the composition
root.*

Implementing the M1.6 requirement — **correlation IDs must propagate from the
HTTP request boundary** — exposed that the blanket independence rule was too
coarse. The correlation-id middleware must set the very `contextvar` that the
structured-logging pipeline reads (`infrastructure/logging/context.py`), so a
delivery-layer component must import `infrastructure.logging`. More generally,
**every layer logs** — an interface that cannot import the logging kernel cannot
emit a structured log line, which is untenable.

Structured logging and correlation context are therefore not an "adapter" in the
ADR-0002 sense (a swappable, vendor-specific implementation behind a port). They
are a **cross-cutting kernel**, used uniformly by all layers, analogous to the
standard library.

## Decision

Treat `infrastructure.logging` (the structlog setup and the correlation-id
context) as a **cross-cutting kernel that any layer may import**, while keeping
the genuine isolation rules intact.

The `import-linter` contracts are refined to encode the *real* intent rather than
the coarse proxy:

1. **Core layering** — `domain < application < infrastructure` (inward-only).
2. **Inner purity** — `domain`, `application`, `infrastructure` must not import
   `composition` or `interface`.
3. **Interface adapter ban** — `interface` must not **directly** import
   `infrastructure.llm` (provider adapters) or `infrastructure.config`
   (configuration). Indirect access *through the composition root* is allowed
   (`allow_indirect_imports = True`), because routing through composition is
   exactly the sanctioned path.
4. **Settings log-free** — `infrastructure.config` must not import
   `infrastructure.logging` (settings load before logging is configured).

Net effect: the interface may use the logging kernel and reach everything else
*via composition*, but a route that directly imports a concrete provider or reads
configuration is still a build failure.

## Consequences

**Positive**
- The architecturally important guarantee is preserved and mechanically enforced:
  delivery never imports a provider adapter directly.
- Request-boundary correlation propagation and structured logging in any layer
  are now possible without violating the dependency rule.
- The contracts now express the true intent, so they are less likely to be
  worked around.

**Negative / Costs**
- A documented exception exists: `interface -> infrastructure.logging` is allowed.
  This must be understood as deliberate, not accidental (the purpose of this ADR).
- `allow_indirect_imports = True` on the adapter-ban contract means only *direct*
  adapter imports are caught; the transitive path through composition is trusted.
  This is correct here (composition is the wiring root) but is a narrowing of the
  check that future maintainers should understand.

## Alternatives Considered

- **Re-export `correlation_id_scope` through `composition`** so the interface
  depends only on composition. Rejected as a pass-through indirection whose only
  purpose is to satisfy the linter; it obscures that logging is a shared kernel.
- **Keep the blanket `interface : infrastructure` independence and forbid
  logging in the interface.** Rejected: it makes structured logging and
  request-boundary correlation impossible in the delivery layer.

## Trade-offs Accepted

We accept one explicit, documented cross-cutting dependency
(`interface -> infrastructure.logging`) in exchange for honest, intent-revealing
dependency contracts and the ability to log and correlate at the request
boundary — while still mechanically forbidding direct provider/config imports in
delivery.
