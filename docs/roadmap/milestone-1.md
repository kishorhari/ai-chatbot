# Development Roadmap — Milestone 1: Project Skeleton + LLM Provider

**Scope:** Clean Architecture skeleton, configuration, logging, the streaming-first
`LLMProvider` port, the Ollama adapter, the Echo provider, the provider registry,
health endpoints, and a CLI probe.

**Out of scope:** chat use case, conversation identity, memory, persistence, auth
(later roadmap steps).

---

## 1. Sub-milestones

| ID | Sub-milestone | Goal |
|----|---------------|------|
| M1.0 | Project bootstrap | Installable package, `src/` layout, tooling, CI skeleton |
| M1.1 | Configuration & logging | Fail-fast settings + structured logging with correlation id |
| M1.2 | Domain contracts | Value objects, `LLMProvider` port, error taxonomy — pure, no I/O |
| M1.3 | Echo provider + contract suite | Reference impl + the shared provider contract tests |
| M1.4 | Ollama adapter | Real provider behind the same contract suite |
| M1.5 | Composition + registry | Wire providers, expose registry, selection by config |
| M1.6 | Delivery surfaces | FastAPI app factory, health/ready endpoints, CLI probe |
| M1.7 | Hardening & gates | Dependency-rule linting, coverage, docs, exit review |

The order is dependency-driven: contracts (M1.2) precede implementations
(M1.3/M1.4); the Echo provider (M1.3) precedes Ollama (M1.4) so the contract
suite exists before the harder adapter; composition (M1.5) precedes delivery
(M1.6) because the surfaces need a wired registry.

---

## 2. File implementation order

Within `src/aiplatform/`:

```
M1.0  pyproject.toml, .gitignore, .env.example, README, ruff/mypy config
M1.1  infrastructure/config/settings.py
      infrastructure/logging/context.py
      infrastructure/logging/setup.py
M1.2  domain/llm/messages.py
      domain/llm/requests.py
      domain/llm/responses.py
      domain/llm/capabilities.py
      domain/llm/errors.py
      domain/llm/ports.py
      application/llm/provider_registry.py        (port only)
M1.3  infrastructure/llm/echo/adapter.py
      tests/contract/provider_contract.py          (shared suite)
M1.4  infrastructure/llm/ollama/mapping.py
      infrastructure/llm/ollama/adapter.py
M1.5  composition/container.py
      composition/bootstrap.py
      (concrete ProviderRegistry impl, if not folded into container)
M1.6  interface/http/app.py
      interface/http/lifespan.py
      interface/http/routes/health.py
      interface/cli/probe.py
M1.7  importlinter config, CI workflow, docs cross-links
```

**Rule:** never implement a file before the inner files it imports exist. The
domain layer (M1.2) is implemented before any adapter that depends on it.

---

## 3. Dependency graph (build-time)

```
config ─┐
logging ┘── (cross-cutting, no domain dependency)

domain/llm (messages, requests, responses, capabilities, errors)
        ▲                        ▲
        │ implements             │ uses
domain/llm/ports (LLMProvider) ──┘
        ▲                        ▲
        │                        │
infra/llm/echo            application/llm/provider_registry (port)
infra/llm/ollama                 ▲
        ▲                        │
        └──────── composition ───┘── builds registry, injects providers
                       ▲
                       │
              interface/http, interface/cli
```

Dependencies flow inward to `domain`. `composition` is the only multi-layer importer.

---

## 4. Deliverables

- Installable Python package under `src/aiplatform/` with pinned tooling.
- Validated, fail-fast configuration with `.env.example` documenting every key.
- Structured logging with per-request correlation id propagation.
- `LLMProvider` port + complete domain value objects and `LLMError` taxonomy.
- `EchoProvider` and `OllamaProvider`, both passing one shared contract suite.
- `ProviderRegistry` with default + named lookup, swappable by config.
- FastAPI app exposing `/health` and `/ready`; CLI probe that streams a prompt.
- CI pipeline running lint, type-check, dependency-rule check, and tests.

---

## 5. Exit criteria (Milestone 1 is "done" when)

1. **Dependency rule passes in CI** — domain imports nothing outward; only
   composition imports infrastructure; build fails on violation.
2. **Both providers pass the identical contract suite** — Echo (unit) and Ollama
   (integration, opt-in).
3. **Config fails fast** — invalid/missing required config aborts startup with a
   clear message, verified by test.
4. **`/ready` reflects composition** — returns 200 only after wiring completes.
5. **Streaming + cancellation verified** — a mid-stream cancellation releases the
   connection and raises nothing (tested against Echo; manually confirmed against
   Ollama).
6. **Every `LLMError` subtype is provably produced** by a simulated failure; no
   transport-native exception escapes an adapter.
7. **Provider swap is config-only** — `AIP__LLM__DEFAULT_PROVIDER=echo` switches
   providers with no code edit, verified.
8. **Logs are structured and correlated** — a single request shares one
   `correlation_id` across records; no secret is ever logged.
9. **Docs current** — ADR-0001..0005, this roadmap, the dependency matrix, and
   the testing strategy reflect the shipped code.
