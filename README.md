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

Milestone 1 (`v0.1.0-m1`) delivered a complete, tested vertical slice of that
foundation: configuration, structured logging, a streaming-first `LLMProvider`
port, two independent provider implementations proven against one shared contract
suite, the composition root that wires them, and HTTP + CLI delivery surfaces.
Milestone 2 (`v0.2.0-m2`) added conversation identity and durable history behind
a repository port proven across in-memory, SQLite, and real PostgreSQL, with an
atomic chat turn. Milestone 3 (`v0.3.0-m3`, proposed) adds Retrieval-Augmented
Generation as swappable infrastructure — embedding, vector-store, and
knowledge-repository ports (pgvector + PostgreSQL in CI), behind an additive,
config-toggled `ContextProvider` seam that leaves the M2 chat turn unchanged when
disabled.

Each capability is added **additively** on the load-bearing core — conversation
memory, RAG, and, next, agents and multi-tenancy — without disturbing the frozen
ports beneath it.

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
- **Durable conversations behind a repository port (M2).** A `Conversation`
  aggregate with append-only history sits behind a `ConversationRepository` port
  proven equivalent across in-memory, SQLite, and **real PostgreSQL** by one
  contract suite; the chat turn is atomic (verified to a real DB rollback).
- **Retrieval-Augmented Generation as swappable infrastructure (M3).** Embedding,
  vector-store, and knowledge-repository ports — each proven by a shared contract
  suite, with **pgvector** and **PostgreSQL** exercised in CI. RAG is an additive
  `ContextProvider` seam on `ChatService` (Null Object default), toggled by
  `AIP__KNOWLEDGE__ENABLED`; with RAG off, M2 behaviour is byte-for-byte identical.
  A deterministic golden-dataset harness gates retrieval quality (recall@k).
- **Mechanically enforced architecture.** Six `import-linter` contracts run in CI;
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
│   ├── domain/
│   │   ├── llm/               # LLM value objects, LLMProvider port, error taxonomy (pure)
│   │   ├── conversation/      # Conversation aggregate + Message, repository port (M2)
│   │   └── knowledge/         # KnowledgeDocument aggregate, EmbeddingVector, retrieval VOs,
│   │   │                      #   embedding/vector-store/knowledge-repository ports (M3)
│   ├── application/
│   │   ├── llm/               # ProviderRegistry port
│   │   ├── conversation/      # ChatService, ConversationService, prompt pipeline, ContextProvider
│   │   └── knowledge/         # Chunking, IndexingService, retriever, RetrievalService, enricher (M3)
│   ├── infrastructure/
│   │   ├── config/            # Fail-fast pydantic settings
│   │   ├── logging/           # structlog setup + correlation-id contextvar
│   │   ├── llm/               # echo/ (reference) + ollama/ (real) providers
│   │   ├── persistence/       # memory/ + sqlalchemy/ conversation repository & transactions (M2)
│   │   └── knowledge/         # embedding (fake, ollama), vector (memory, pgvector), repository (M3)
│   ├── composition/           # Composition root: container, bootstrap, registry wiring
│   └── interface/
│       ├── http/              # FastAPI app: /health /ready, conversations, knowledge routes
│       └── cli/               # Dev probe, chat, and ingest commands
├── migrations/                # Alembic: conversation schema + pgvector extension & knowledge tables
├── tests/
│   ├── unit/                  # Per-module logic in isolation
│   ├── contract/              # Shared contract suites (provider, repository, embedding, vector, knowledge)
│   ├── integration/           # Real adapters via respx + opt-in live (`-m live`)
│   └── eval/                  # Deterministic golden-dataset retrieval quality gate (M3.8)
├── docs/                      # ADRs, roadmap, dependency matrix, testing & git strategy
├── .github/workflows/ci.yml   # Lint → type-check → dependency rule → tests
├── .importlinter              # The six enforced dependency contracts
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
| [0007](docs/adr/0007-conversation-message-aggregate.md) | Conversation and Message aggregates | Accepted |
| [0008](docs/adr/0008-persistence-repository-and-transactions.md) | Persistence — repository contract, transaction boundary, relational mapping | Accepted |
| [0009](docs/adr/0009-context-window-and-prompt-assembly.md) | Context-window selection and prompt assembly | Accepted |
| [0010](docs/adr/0010-application-service-layer.md) | Application service layer (use-case orchestration) | Accepted |
| [0011](docs/adr/0011-knowledge-and-retrieval-architecture.md) | Knowledge & retrieval architecture (RAG) | Accepted |
| [0012](docs/adr/0012-embedding-provider-abstraction.md) | Embedding provider abstraction | Accepted |
| [0013](docs/adr/0013-vector-store-abstraction.md) | Vector store abstraction | Accepted |
| [0014](docs/adr/0014-chunking-strategy.md) | Chunking strategy | Accepted |
| [0015](docs/adr/0015-retrieval-and-prompt-enrichment.md) | Retrieval strategy & prompt enrichment (ContextProvider seam) | Accepted |
| [0016](docs/adr/0016-knowledge-metadata-ingestion-and-persistence.md) | Knowledge metadata, ingestion & persistence | Accepted |

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

The **shared contract suite** pattern is the centerpiece, now applied to five
abstractions: the LLM provider (Echo, Ollama), the conversation repository
(in-memory, SQLite, PostgreSQL), and the M3 embedding, vector-store, and
knowledge-repository ports (offline reference + real backend each, pgvector and
PostgreSQL in CI). Coverage is a diagnostic, not a goal — `domain` and
`application` sit at **99%**; the contract suites running green across every
implementation are the more meaningful signal. M3 adds a deterministic
golden-dataset **retrieval quality gate** (`tests/eval/`) proving recall@k on the
offline path.

**Current results (M3):** 489 offline tests pass (+ PostgreSQL/pgvector contract
suites in CI, opt-in live Ollama excluded), **six** dependency contracts kept,
`domain`/`application` at 99% coverage. See the
[M3 exit-criteria review](docs/milestone-3-exit-review.md).

## Project roadmap

The platform is built in milestones, each with a goal, deliverables, exit criteria,
risks, and dependencies. Full detail in **[ROADMAP.md](ROADMAP.md)**.

| Milestone | Theme | Status |
|-----------|-------|:------:|
| **M1** | Foundation — Clean Architecture, provider abstraction, streaming, contract testing, FastAPI + CLI | ✅ **Completed** (`v0.1.0-m1`) |
| **M2** | Conversation identity, message aggregate, repository pattern, memory, PostgreSQL swap | ✅ **Completed** (`v0.2.0-m2`) |
| **M3** | RAG — embeddings, vector store (pgvector), chunking, retrieval, prompt enrichment, semantic search | ✅ **Completed** (`v0.3.0-m3`, proposed) |
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

**Milestone 2 — Conversation & Persistence: complete and accepted (`v0.2.0-m2`).**
Conversation identity and durable history behind a `ConversationRepository` port,
proven equivalent across in-memory, SQLite, and real PostgreSQL by one contract
suite (PostgreSQL in CI); an atomic chat turn verified to a real database
rollback. See the [exit review](docs/milestone-2-exit-review.md) and
[retrospective](docs/milestone-2-retrospective.md).

**Milestone 3 — Knowledge Retrieval (RAG): complete, proposed for `v0.3.0-m3`.**
All ten exit criteria met with mapped evidence. Embedding, vector-store, and
knowledge-repository ports each proven by a shared contract suite (pgvector and
PostgreSQL in CI); RAG is an additive `ContextProvider` seam on `ChatService`
(Null Object default) toggled by config, so M2 behaviour is preserved unchanged
when disabled; a deterministic golden-dataset harness gates retrieval recall@k.
Six `import-linter` contracts enforce the dependency rule and the frozen M1/M2
ports. See the [exit review](docs/milestone-3-exit-review.md),
[retrospective](docs/milestone-3-retrospective.md), and
[release readiness review](docs/milestone-3-release-readiness.md).

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
