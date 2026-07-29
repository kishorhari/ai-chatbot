# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Pre-1.0 releases are tagged per milestone as `vMAJOR.MINOR.PATCH-mN`.

## [Unreleased]

Milestone 3 — **Knowledge Retrieval (RAG)**. Slated for release as `v0.3.0-m3`.
Retrieval-Augmented Generation added as replaceable infrastructure behind ports
proven by contract suites, with an additive, config-toggled `ContextProvider`
seam that leaves the M2 chat turn unchanged when RAG is disabled. All ten
Milestone 3 exit criteria met; six `import-linter` contracts kept; `domain` +
`application` at 99% coverage; the frozen M1/M2 ports are unchanged.

### Added

**Knowledge domain (M3.0)** — `domain/knowledge`
- `KnowledgeDocument` aggregate + `KnowledgeChunk`, domain-generated type-distinct
  `KnowledgeDocumentId`/`KnowledgeChunkId`, `IngestionStatus`, an `EmbeddingVector`
  value object (dimension + cosine similarity), `Metadata`/`MetadataFilter` scalar
  VOs, `RetrievedChunk`/`RetrievedContext` (descending-score invariant), a
  knowledge error taxonomy, and the domain ports `EmbeddingProvider`,
  `VectorStore`, `KnowledgeRepository` (ADR-0011).

**Embedding provider (M3.1)** — `EmbeddingProvider` port + shared embedding
contract suite; a deterministic offline `FakeEmbeddingProvider` (hashing
bag-of-words) and a real `OllamaEmbeddingProvider` over `httpx`, both passing the
identical suite (ADR-0012).

**Vector store (M3.2)** — `VectorStore` port + shared vector-store contract suite;
`InMemoryVectorStore` (cosine top-k, upsert, delete-by-document, metadata filter,
fixed-dimension enforcement) passing it (ADR-0013).

**Chunking, knowledge repository, indexing (M3.3)** — a `ChunkingStrategy` port
with a token-aware default reusing the M2 `TokenEstimator`; `KnowledgeRepository`
in-memory implementation + shared contract suite; `IndexingService` orchestrating
chunk → embed → persist record → persist vectors with compensation so partial
indexing cannot leave inconsistent state (ADR-0014, ADR-0016).

**Retrieval (M3.4)** — `Retriever` port, `SemanticRetriever` (embed query → vector
search), and `RetrievalService` applying default-`k` and a similarity threshold,
producing a `RetrievedContext` with metadata filtering at the store (ADR-0015).

**Context-provider seam & enrichment (M3.5)** — a pure, budget-aware,
single-leading-system-safe `PromptEnricher`; a `ContextProvider` port with a
`NullContextProvider` (RAG off) and a `KnowledgeContextProvider` (composing
retrieval + enrichment). `ChatService` delegates context acquisition to the single
`ContextProvider` collaborator — additively — so every M2 chat test passes
unchanged when RAG is disabled (ADR-0015).

**Delivery & composition (M3.6)** — knowledge HTTP endpoints (ingest / list /
delete / debug-search) and a CLI ingest/query command; the composition root wires
embedding / vector / knowledge backends and selects `NullContextProvider` vs
`KnowledgeContextProvider` entirely through configuration
(`AIP__KNOWLEDGE__ENABLED`), keeping `ChatService` free of feature-toggle logic.

**PostgreSQL / pgvector persistence (M3.7)** — `PgVectorStore` (dimensionless
`vector` column, cosine distance) and `SqlAlchemyKnowledgeRepository` with an
explicit domain↔ORM mapping, reusing the M2 async `SessionProvider`; an Alembic
migration enabling the `vector` extension and creating the knowledge tables. The
identical vector-store and knowledge-repository contract suites run against real
PostgreSQL + pgvector in CI (`pgvector/pgvector:pg16` service container).

**Hardening & gates (M3.8)**
- A deterministic golden-dataset **retrieval evaluation harness** (`tests/eval/`):
  a committed six-topic corpus + labelled queries, pure recall@k / hit-rate / MRR
  metrics, and an acceptance test that gates retrieval quality on the offline path
  (recall@1 = recall@3 = 1.0, MRR = 1.0), plus retrieval-correctness, metadata
  filtering, and determinism checks.
- A sixth `import-linter` contract — `core-vector-agnostic` — forbidding `domain`
  and `application` from importing a vector/embedding SDK (`pgvector`, `numpy`),
  the M3 analogue of the persistence-agnostic contract.
- `docs/milestone-3-exit-review.md`, `docs/milestone-3-retrospective.md`, and
  `docs/milestone-3-release-readiness.md`; README, docs index, and ADR statuses
  updated to reflect the shipped M3 code.

### Changed
- `pgvector>=0.3` added to the `dev` and `postgres` optional-dependency extras; a
  mypy override ignores its missing type stubs. The CI PostgreSQL service image is
  `pgvector/pgvector:pg16` so the vector extension is available.

## [0.2.0-m2] - 2026-07-29

Milestone 2 — **Conversation & Persistence**. Conversation identity and durable
message history behind a domain-owned `ConversationRepository` port, a
budget-aware prompt pipeline feeding the unchanged M1 provider port, and an atomic
chat use case coordinated by a thin application service. The repository is proven
equivalent across in-memory, SQLite, and real PostgreSQL (the last in CI) by one
contract suite; the chat turn's atomicity is verified to a real database rollback.
All nine M2 exit criteria met; five `import-linter` contracts kept;
`domain`/`application` at 100% coverage.

### Added
- **Conversation aggregate** (`domain/conversation`): domain-generated,
  type-distinct `ConversationId`/`MessageId`; an immutable, append-only `Message`
  entity (explicit sequence, injected timezone-aware timestamps) distinct from the
  transport `ChatMessage`; and the `Conversation` aggregate root enforcing
  sequence contiguity, the single-leading-system-message rule, and a non-empty
  owner, with `start()`/`reconstitute()` running identical invariant checks
  (ADR-0007).
- **`ConversationRepository` port + shared contract suite** (11 invariants) with an
  in-memory implementation, a SQLAlchemy implementation exercised over SQLite
  locally, and real PostgreSQL in CI; snapshot independence is part of the contract
  (ADR-0008).
- **Persistence infrastructure**: async SQLAlchemy repository + `SessionProvider`,
  a pure domain↔ORM mapping layer, an application-owned `TransactionBoundary` port
  with `atomic()` (in-memory + SQLAlchemy implementations), and an Alembic
  migration for the conversation schema; backend selected by
  `AIP__PERSISTENCE__BACKEND` (`asyncpg` in a `postgres` optional-extra).
- **Prompt pipeline**: a deterministic `ContextWindowPolicy` (retain system,
  most-recent-first, drop oldest, reserve room for the reply) over a
  `TokenEstimator` seam (conservative heuristic default), and a **pure**
  `PromptAssembler` producing the frozen M1 `CompletionRequest` (ADR-0009).
- **Application service layer** (ADR-0010): `ChatService` (recall → append →
  window → assemble → generate → append → persist atomically) and
  `ConversationService` (lifecycle/query); a `Clock` port seam so use cases stay
  deterministic. HTTP conversation routes and a multi-turn CLI chat.
- **Milestone 2 architecture package**: ADR-0007..0010 and
  `docs/roadmap/milestone-2.md`; the M2 exit review and retrospective.
- Project scaffolding: `ROADMAP.md` (M1–M7), `CONTRIBUTING.md`, `CHANGELOG.md`,
  `SECURITY.md`, `CODE_OF_CONDUCT.md`, GitHub issue forms, and a PR template.

### Changed
- Relicensed the project under the **MIT License** (previously marked
  `Proprietary` in package metadata) to prepare it as an open-source portfolio
  project; added a top-level `LICENSE`.
- Expanded `README.md` into full project documentation (overview, motivation,
  architecture, folder structure, tech stack, design principles, ADR index,
  supported providers, testing strategy, roadmap, and milestone status).
- Extended the dependency-rule gate to five `import-linter` contracts (adding the
  persistence-agnostic-core contract forbidding SQLAlchemy/asyncpg/Alembic in
  `domain`/`application`).

### Removed
- Legacy pre-architecture prototype `app/` (`chatbot.py`, `main.py`, `config.py`)
  and the stale top-level `requirements.txt`, both superseded by the
  `src/aiplatform` package and `pyproject.toml`. The `app/` ruff exclusion was
  dropped accordingly.

## [0.1.0-m1] - 2026-06-30

Milestone 1 — **Foundation**. The Clean-Architecture core and a provably
vendor-neutral LLM provider abstraction. All nine milestone exit criteria met;
200 offline tests pass (+3 opt-in live), `domain`/`application` at 100% coverage
(96% overall), four `import-linter` contracts kept.

### Added

**Architecture & enforcement**
- Clean Architecture layering in a modular monolith: `domain`, `application`,
  `infrastructure`, `interface`, and a `composition` root (ADR-0001).
- Four `import-linter` contracts enforcing the Dependency Rule in CI: core
  layering, inner purity, the interface adapter ban, and a log-free settings rule
  (ADR-0006).
- `src/` layout, Hatchling build, and pinned tooling in `pyproject.toml`.

**Domain (LLM)**
- Value objects: `ChatMessage`/`Role`, `CompletionRequest`, `CompletionChunk`,
  `CompletionResult`, `TokenUsage`, `ProviderCapabilities`.
- Streaming-first `LLMProvider` port: `stream_chat` is canonical, `complete_chat`
  is derived via `CompletionResult.from_chunks`, `capabilities()` performs no I/O
  (ADR-0003). Model identity lives on `ProviderCapabilities`.
- Provider-agnostic `LLMError` taxonomy — `LLMTransportError`, `LLMTimeoutError`,
  `LLMProtocolError`, `LLMAuthenticationError`, `LLMRateLimitError` (with
  `retry_after`), `LLMModelError` — each carrying a `retryable` disposition and
  preserving the original `cause` without importing any vendor type (ADR-0002).

**Application**
- `ProviderRegistry` port: resolve a provider by name or return the configured
  default.

**Infrastructure**
- `EchoProvider` — deterministic, network-free reference implementation that
  streams the last user message token-by-token (ADR-0004).
- `OllamaProvider` — real provider over `httpx`, with a mapping module translating
  every transport/HTTP/JSON failure into the domain `LLMError` taxonomy; separate
  connect vs. total timeouts; connect-phase retries that never replay a partial
  stream.
- Fail-fast `pydantic-settings` configuration (`AIP__` prefix, `__` nesting);
  unknown keys rejected; `SecretStr` for credentials.
- Structured logging via `structlog` (console/JSON) with a correlation-id
  `contextvar` and secret redaction.

**Interface**
- FastAPI application factory with `/health` and `/ready` (ready returns 200 only
  after composition wiring completes).
- Correlation-id middleware propagating a single ID across a request's log records.
- CLI probe that streams a prompt through the wired provider.

**Composition**
- Composition root (`container`, `bootstrap`, registry wiring) as the single place
  concretes are bound to ports; provider selection is config-only.

**Tests**
- Shared provider **contract suite** (`tests/contract/provider_contract.py`) run
  against both Echo and Ollama, asserting the streaming/cancellation invariants
  and the error-taxonomy guarantee.
- Unit tests across domain value objects, error taxonomy, settings (fail-fast +
  redaction), logging, Ollama mapping, and composition wiring.
- Integration tests for the Ollama adapter via `respx`, plus an opt-in live suite
  (`-m live`) excluded from CI.

**Documentation**
- Six ADRs (0001–0006), the Milestone 1 roadmap, a file-dependency matrix, the
  testing strategy, the git strategy, and the Milestone 1 exit review and
  retrospective under `docs/`.

**CI**
- GitHub Actions workflow running, in order: ruff (lint + format), mypy,
  `import-linter` (dependency rule), and `pytest -m "not live"` with coverage.

[Unreleased]: https://github.com/kishorhari/ai-chatbot/compare/v0.2.0-m2...HEAD
[0.2.0-m2]: https://github.com/kishorhari/ai-chatbot/compare/v0.1.0-m1...v0.2.0-m2
[0.1.0-m1]: https://github.com/kishorhari/ai-chatbot/releases/tag/v0.1.0-m1
