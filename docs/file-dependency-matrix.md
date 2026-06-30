# File Dependency Matrix — Milestone 1

Rows = files. "Depends on" lists the **internal** modules a file imports
(standard library and third-party deps omitted). The matrix is used to validate
the Dependency Rule and to surface circular-dependency risk before coding.

Layer legend: **D** domain · **A** application · **I** infrastructure ·
**X** interface · **C** composition.

| # | File | Layer | Depends on (internal) |
|---|------|-------|------------------------|
| 1 | `domain/llm/messages.py` | D | — |
| 2 | `domain/llm/requests.py` | D | `messages` |
| 3 | `domain/llm/responses.py` | D | — |
| 4 | `domain/llm/capabilities.py` | D | — |
| 5 | `domain/llm/errors.py` | D | — |
| 6 | `domain/llm/ports.py` | D | `requests`, `responses`, `capabilities`, `errors` |
| 7 | `application/llm/provider_registry.py` | A | `domain/llm/ports`, `domain/llm/errors` |
| 8 | `infrastructure/config/settings.py` | I | — (pydantic only) |
| 9 | `infrastructure/logging/context.py` | I | — (stdlib only) |
| 10 | `infrastructure/logging/setup.py` | I | `logging/context`, `config/settings` |
| 11 | `infrastructure/llm/echo/adapter.py` | I | `domain/llm/*` (ports, VOs, errors) |
| 12 | `infrastructure/llm/ollama/mapping.py` | I | `domain/llm/requests`, `responses`, `errors` |
| 13 | `infrastructure/llm/ollama/adapter.py` | I | `domain/llm/ports`, `ollama/mapping`, `config/settings`, `logging` |
| 14 | `composition/container.py` | C | `config`, `logging`, `infra/llm/echo`, `infra/llm/ollama`, `application/llm/provider_registry`, `domain/llm/ports` |
| 15 | `composition/bootstrap.py` | C | `composition/container`, `logging` |
| 16 | `interface/http/app.py` | X | `composition/bootstrap`, `interface/http/lifespan`, `routes/health` |
| 17 | `interface/http/lifespan.py` | X | `composition/container` |
| 18 | `interface/http/routes/health.py` | X | `application/llm/provider_registry` (readiness check) |
| 19 | `interface/cli/probe.py` | X | `composition/container`, `domain/llm/*` |

---

## Dependency-rule validation

- **Domain (1–6)** imports only other domain modules. ✅ No outward imports.
- **Application (7)** imports only domain. ✅
- **Infrastructure (8–13)** imports domain (to implement ports) + sibling infra
  (config/logging). ✅ Never imports application/interface/composition.
- **Interface (16–19)** imports composition + application + domain, and the
  cross-cutting `infrastructure.logging` kernel (see ADR-0006). ✅ Never imports
  a provider **adapter** (`infrastructure.llm`) or `infrastructure.config`
  directly — providers and settings arrive only via the wired container.
- **Composition (14–15)** imports everything. ✅ This is its sanctioned role.

As-shipped `import-linter` contracts (refined in M1.6; see ADR-0006 — the
original single `domain < application < {infrastructure, interface} <
composition` proved too coarse once delivery needed the logging kernel):

1. **Core layering** — `domain < application < infrastructure` (inward only).
2. **Inner purity** — domain / application / infrastructure must not import
   `composition` or `interface`.
3. **Interface adapter ban** — `interface` must not *directly* import
   `infrastructure.llm` or `infrastructure.config` (`allow_indirect_imports`:
   the transitive path through `composition` is the sanctioned route).
4. **Settings log-free** — `infrastructure.config` must not import
   `infrastructure.logging` (settings load before logging is configured).

`composition` is the exempt root: it imports everything and is imported only by
`interface`.

---

## Circular-dependency risk analysis

| Risk | Where it could appear | Verdict / Mitigation |
|------|----------------------|----------------------|
| `ports` ↔ value objects | `ports.py` imports VOs; a VO importing `ports` would cycle | **Low.** VOs (1–5) import nothing upward; keep it that way. Lint enforces. |
| `settings` ↔ `logging` | `logging/setup` imports `settings`; settings must NOT import logging | **Low.** Settings stays log-free (it loads before logging is configured). Documented in M1.1. |
| `registry` ↔ adapters | Registry is a port (application); adapters implement domain port, not the registry | **None by design.** Registry depends on `domain/ports`; adapters depend on `domain/ports`; they meet only at the composition root. |
| `container` ↔ `lifespan` | Both in/near composition; lifespan imports container | **Low.** One-directional: `lifespan → container`. Container never imports interface. |
| `ollama/adapter` ↔ `mapping` | Adapter imports mapping; mapping must not import adapter | **Low.** Mapping is pure translation, depends only on domain VOs/errors. |

**Conclusion:** no cycles in the planned graph. The two files to watch are
`settings.py` (must stay logging-free) and the value objects (must stay
port-free). Both are guarded by the layered lint contract and called out in the
implementation checklist.
