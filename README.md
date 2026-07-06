# AI Platform

> A provider-agnostic AI assistant platform built on Clean Architecture in a modular monolith. The LLM provider — and, later, the storage backend — sit behind ports, so they are swapped by configuration, not by rewrites.

[![CI](https://github.com/kishorhari/ai-chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/kishorhari/ai-chatbot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Architecture: Clean](https://img.shields.io/badge/architecture-clean-success.svg)](docs/adr/0001-clean-architecture.md)
[![Lint & format: Ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![Types: mypy](https://img.shields.io/badge/types-mypy-2a6db2.svg)](https://mypy-lang.org/)
[![Dependency rule: import-linter](https://img.shields.io/badge/dependency--rule-import--linter-blueviolet.svg)](.importlinter)

---

## Overview

AI Platform is the foundation for a long-lived AI assistant. The architectural
thesis is simple and deliberately strict: **the parts of an AI system that change
most often — the model provider and the storage backend — must never be allowed
to leak into the business logic.** Everything is organized so that swapping Ollama
for a cloud model, or an in-memory store for PostgreSQL, is a wiring change at a
single composition root, not a refactor that ripples through the codebase.

Milestone 1 (`v0.1.0-m1`) delivers a complete, tested vertical slice of that
foundation: configuration, structured logging, a streaming-first `LLMProvider`
port, two independent provider implementations proven against one shared contract
suite, the composition root that wires them, and HTTP + CLI delivery surfaces.

This is intentionally **not** a feature-complete chatbot yet. It is the
load-bearing core that every later feature — conversation memory, RAG, agents,
multi-tenancy — is designed to sit on top of without disturbing it.

## Motivation — why this project exists

Most LLM applications begin as a script that calls a vendor SDK directly. That is
fast on day one and expensive forever after: the vendor's request/response shapes,
exceptions, and quirks spread into every layer, and the first provider migration
becomes a rewrite.

This repository takes the opposite bet. It treats the LLM and the database as
**volatile infrastructure** and invests up front in the boundaries that contain
them. The goals are:

- **Provider independence as a provable property**, not a stated aspiration. Two
  providers passing one identical contract suite is the executable proof that the
  abstraction is real (see [ADR-0004](docs/adr/0004-echo-provider.md)).
- **A dependency direction that is enforced by a machine, not by code review.** A
  boundary violation is a failed CI build, not a comment someone might miss.
- **A codebase whose structure is its own documentation** — readable as a study in
  how to architect an AI application that survives years of feature growth.

The full design history lives in [`docs/`](docs/README.md): six ADRs, a roadmap, a
file-dependency matrix, a testing strategy, a git strategy, and the Milestone 1
exit review and retrospective.

## Key features

- **Streaming-first provider port.** `stream_chat` is the canonical operation;
  `complete_chat` is derived from it. Streaming becomes a transport detail rather
  than a future refactor ([ADR-0003](docs/adr/0003-streaming-first-provider-design.md)).
- **Vendor-neutral error taxonomy.** Every transport/vendor failure maps to a
  domain `LLMError` subtype (`Transport`, `Timeout`, `Protocol`, `Authentication`,
  `RateLimit`, `Model`); **no `httpx`/`json` exception escapes an adapter**. Callers
  branch on type and a `retryable` flag — never on string-matched vendor messages.
- **Two providers, one contract.** `EchoProvider` (offline, deterministic) and
  `OllamaProvider` (real, over `httpx`) satisfy the same parametrized contract
  suite, including mid-stream cancellation.
- **Configuration-driven selection.** `AIP__LLM__DEFAULT_PROVIDER=echo|ollama`
  swaps the active provider with zero code changes.
- **Fail-fast configuration.** Invalid or unknown config aborts at load with a
  clear message; secrets are `SecretStr` and are redacted from logs and reprs.
- **Structured logging with request correlation.** One `correlation_id` flows from
  the HTTP boundary through every log record ([ADR-0006](docs/adr/0006-logging-cross-cutting-kernel.md)).
- **Mechanically enforced architecture.** Four `import-linter` contracts run in CI;
  the dependency rule cannot silently rot.

## Architecture overview

Source dependencies point **inward only** — the Dependency Rule
([ADR-0001](docs/adr/0001-clean-architecture.md)):

```
domain  ◀  application  ◀  { infrastructure, interface }  ◀  composition (root)
```

| Layer | Responsibility | May depend on | Imports a vendor SDK? |
|-------|----------------|---------------|:---------------------:|
| **domain** | Value objects, the `LLMProvider` port, the `LLMError` taxonomy. Pure — no framework, I/O, or logging. | (nothing) | ❌ |
| **application** | Use cases and orchestration; the `ProviderRegistry` port. | domain | ❌ |
| **infrastructure** | Adapters implementing ports: LLM providers, config, logging. The only layer that touches the outside world. | domain | ✅ (only here) |
| **interface** | Delivery surfaces: FastAPI HTTP app, CLI probe. | application, domain, composition, `infrastructure.logging` kernel | ❌ |
| **composition** | The composition root — the single place permitted to wire concretes to ports. | everything | ✅ |

The lone, deliberate cross-cutting exception is `infrastructure.logging`, which any
layer may import because *every* layer logs and the correlation context must be set
at the request boundary. That exception is documented and still mechanically bounded
([ADR-0006](docs/adr/0006-logging-cross-cutting-kernel.md)); a delivery route that
directly imports a provider adapter or reads configuration is still a build failure.

A request flows: **HTTP/CLI → composition-wired `ProviderRegistry` → `LLMProvider`
port → adapter → vendor.** Nothing above `infrastructure` ever names a vendor.

## Folder structure

```
.
├── src/aiplatform/
│   ├── domain/llm/            # Value objects, LLMProvider port, error taxonomy (pure)
│   │   ├── messages.py        #   ChatMessage, Role
│   │   ├── requests.py        #   CompletionRequest
│   │   ├── responses.py       #   CompletionChunk, CompletionResult, TokenUsage
│   │   ├── capabilities.py    #   ProviderCapabilities
│   │   ├── errors.py          #   LLMError hierarchy
│   │   └── ports.py           #   LLMProvider (stream_chat / complete_chat / capabilities)
│   ├── application/llm/       # ProviderRegistry port (resolve by name / default)
│   ├── infrastructure/
│   │   ├── config/            # Fail-fast pydantic settings
│   │   ├── logging/           # structlog setup + correlation-id contextvar
│   │   └── llm/
│   │       ├── echo/          # Reference provider — deterministic, no network
│   │       └── ollama/        # Ollama adapter + transport→domain error mapping
│   ├── composition/           # Composition root: container, bootstrap, registry wiring
│   └── interface/
│       ├── http/              # FastAPI app factory, lifespan, middleware, /health /ready
│       └── cli/               # Dev probe that streams a prompt
├── tests/
│   ├── unit/                  # Per-module logic in isolation
│   ├── contract/              # Shared provider contract suite (run against every provider)
│   └── integration/           # Ollama via respx + opt-in live (`-m live`)
├── docs/                      # ADRs, roadmap, dependency matrix, testing & git strategy
├── .github/workflows/ci.yml   # Lint → type-check → dependency rule → tests
├── .importlinter              # The four enforced dependency contracts
├── pyproject.toml             # Package, dependencies, ruff/mypy/pytest/coverage config
└── .env.example               # Every configuration key, documented
```

## Technology stack

| Concern | Choice | Notes |
|---------|--------|-------|
| Language | **Python 3.13** | `from __future__ import annotations`, modern typing |
| Web framework | **FastAPI** + **Uvicorn** | Delivery surface only; isolated in `interface` |
| Validation / settings | **Pydantic v2** + **pydantic-settings** | Domain value objects and fail-fast config |
| HTTP client | **httpx** | Confined to the Ollama adapter; never imported above infrastructure |
| Logging | **structlog** | Structured console/JSON output, correlation IDs |
| Default model runtime | **Ollama** | Local-first; pluggable behind the port |
| Testing | **pytest**, **pytest-asyncio**, **respx** | Unit / contract / integration |
| Lint & format | **Ruff** | `E,F,I,N,UP,B,ANN,D,ASYNC,RUF`, line length 100 |
| Type checking | **mypy** | Strict on `domain`/`application` |
| Architecture enforcement | **import-linter** | Dependency rule as a CI gate |
| Build backend | **Hatchling** | `src/` layout, single distributable package |

## Design principles

1. **The Dependency Rule is law.** Source dependencies point inward only, and it is
   enforced by `import-linter`, not by convention.
2. **Ports in the inside, adapters on the outside.** A port is introduced only where
   a real second implementation is foreseeable (LLM provider, repository).
3. **Abstractions are proven, not asserted.** A port earns trust by having two
   passing implementations against one contract suite.
4. **Fail fast and loud.** Misconfiguration aborts at startup, never at request time.
5. **No vendor exception escapes its adapter.** Failures cross the boundary as a
   domain error taxonomy with a `retryable` signal.
6. **Streaming is the superset.** Design for the harder case once; derive the easier.
7. **Avoid speculative abstraction.** Repository, Unit of Work, and retry policy are
   designed for but not built until a real second case exists.

## Architectural Decision Records

Every significant decision is recorded with context, alternatives considered, and
trade-offs accepted. Read them in order in [`docs/adr/`](docs/adr/):

| ADR | Decision | Status |
|-----|----------|:------:|
| [0001](docs/adr/0001-clean-architecture.md) | Clean Architecture in a modular monolith | Accepted |
| [0002](docs/adr/0002-llm-provider-abstraction.md) | LLM provider abstraction (domain port + adapters) | Accepted |
| [0003](docs/adr/0003-streaming-first-provider-design.md) | Streaming-first provider design | Accepted |
| [0004](docs/adr/0004-echo-provider.md) | Echo provider as the reference implementation | Accepted |
| [0005](docs/adr/0005-repository-strategy.md) | Repository strategy (in-memory first, PostgreSQL later) | Accepted |
| [0006](docs/adr/0006-logging-cross-cutting-kernel.md) | Logging/correlation as a cross-cutting kernel | Accepted |

## Supported providers

| Provider | Status | Network | Purpose | Selector |
|----------|:------:|:-------:|---------|----------|
| **Echo** | ✅ Implemented | None | Deterministic reference impl; keeps the port honest; fast offline tests | `AIP__LLM__DEFAULT_PROVIDER=echo` (local/test only) |
| **Ollama** | ✅ Implemented | Local HTTP | Real local model runtime over `httpx` | `AIP__LLM__DEFAULT_PROVIDER=ollama` |
| OpenAI / Anthropic (Claude) / Gemini / DeepSeek | 🗓️ Planned (Milestone 7) | Cloud HTTP/SSE | Cloud models, provider routing, cost optimization | — |

Adding a provider is "write an adapter + its mapping + one registry line, and pass
the shared contract suite." See [ROADMAP.md](ROADMAP.md) for the cloud-provider plan.

## Development setup

**Requirements:** Python **3.13**. For the live Ollama path, a running
[Ollama](https://ollama.com/) instance.

```bash
# Clone
git clone https://github.com/kishorhari/ai-chatbot.git
cd ai-chatbot

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # bash/zsh
# venv\Scripts\Activate.ps1        # Windows PowerShell

# Install the package with dev extras
pip install -e ".[dev]"

# Configure
cp .env.example .env               # then edit as needed
```

Run the quality gates locally (the same set CI enforces):

```bash
ruff check . && ruff format --check .     # lint + format
mypy src                                  # type-check (strict on domain/application)
lint-imports                              # dependency-rule contracts
pytest -m "not live" --cov=aiplatform     # unit + contract + respx integration, with coverage
```

Run the application surfaces:

```bash
uvicorn aiplatform.interface.http.app:create_app --factory --reload   # HTTP API: /health, /ready
python -m aiplatform.interface.cli.probe                              # CLI probe (streams a prompt)
```

The live Ollama tests are opt-in and excluded from CI:

```bash
AIP__OLLAMA__BASE_URL=http://localhost:11434 AIP__OLLAMA__MODEL=llama3 pytest -m live
```

## Testing strategy

Tests are organized as a taxonomy, each with a clear purpose
([full strategy](docs/testing-strategy.md)):

| Type | Purpose | Network | In CI |
|------|---------|---------|:-----:|
| **Unit** | One module in isolation (value objects, mapping, settings, logging) | none | every push |
| **Contract** | A behavioral spec **every** `LLMProvider` must satisfy, run against each impl | none (Echo) / mocked (Ollama) | every push |
| **Integration** | Real adapter against simulated transport (`respx`) and opt-in live Ollama | mocked / live | respx every push; live opt-in |
| **Smoke** | End-to-end boot: app starts, `/ready` flips, CLI probe streams | none | nightly / pre-release |

The **shared provider contract suite** is the centerpiece: it asserts the
streaming/cancellation invariants and the error-taxonomy guarantee, and both Echo
and Ollama must pass it. Coverage is treated as a diagnostic, not a goal — `domain`
and `application` are at **100%**; the suite running green across two providers is
the more meaningful signal.

**Milestone 1 results:** 200 offline tests pass (+3 opt-in live), four dependency
contracts kept, `domain`/`application` at 100% coverage (96% overall). See the
[exit-criteria review](docs/milestone-1-exit-review.md).

## Project roadmap

The platform is built in milestones, each with a goal, deliverables, exit criteria,
risks, and dependencies. Full detail in **[ROADMAP.md](ROADMAP.md)**.

| Milestone | Theme | Status |
|-----------|-------|:------:|
| **M1** | Foundation — Clean Architecture, provider abstraction, streaming, contract testing, FastAPI + CLI | ✅ **Completed** (`v0.1.0-m1`) |
| **M2** | Conversation identity, message aggregate, repository pattern, memory, PostgreSQL swap | 🔜 Next |
| **M3** | RAG — vector DB, embeddings, PDF ingestion, semantic search | 🗓️ Planned |
| **M4** | Agents — tool calling, planning, multi-step reasoning, agent memory | 🗓️ Planned |
| **M5** | Integrations — ERPNext, WhatsApp, email, webhooks, background jobs | 🗓️ Planned |
| **M6** | Multi-tenancy — auth, RBAC, organizations, billing, SaaS | 🗓️ Planned |
| **M7** | Cloud providers — OpenAI, Claude, Gemini, DeepSeek, routing, cost optimization | 🗓️ Planned |

## Milestone status

**Milestone 1 — Foundation: complete and accepted (`v0.1.0-m1`).** All nine exit
criteria are met with mapped evidence; see the
[exit review](docs/milestone-1-exit-review.md) and
[retrospective](docs/milestone-1-retrospective.md). Validated in practice: the
dependency rule held across every sub-milestone, the port proved vendor-neutral
against two providers, and provider selection is config-only.

## Future vision

A self-hostable, provider-agnostic AI assistant platform where conversation memory,
retrieval-augmented generation, and tool-using agents are first-class — and where
the model vendor, the database, and the delivery channel are all swappable details
behind stable ports. The same discipline that made provider selection a config flag
in M1 is meant to make the PostgreSQL swap (M2), the RAG pipeline (M3), and the
cloud-provider routing (M7) equally low-risk, binding changes with the test suite
still green.

## Contributing

Contributions are welcome. Please read **[CONTRIBUTING.md](CONTRIBUTING.md)** for the
development setup, branch strategy, Conventional Commits convention, the PR
checklist, testing requirements, and coding standards. In short: branch off `main`,
keep PRs small and focused, use Conventional Commit messages, and make sure the four
CI gates (lint, type-check, dependency rule, tests) pass before requesting review.

The dependency rule is non-negotiable and enforced by `import-linter` — if you
introduce a cross-layer import, CI will fail by design. When in doubt, consult the
relevant ADR.

## License

Released under the [MIT License](LICENSE).
