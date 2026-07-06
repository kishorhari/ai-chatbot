# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Pre-1.0 releases are tagged per milestone as `vMAJOR.MINOR.PATCH-mN`.

## [Unreleased]

### Changed
- Relicensed the project under the **MIT License** (previously marked
  `Proprietary` in package metadata) to prepare it as an open-source portfolio
  project; added a top-level `LICENSE`.
- Expanded `README.md` into full project documentation (overview, motivation,
  architecture, folder structure, tech stack, design principles, ADR index,
  supported providers, testing strategy, roadmap, and milestone status).

### Added
- `ROADMAP.md` — long-range plan (M1–M7) with goal, deliverables, exit criteria,
  risks, and dependencies per milestone.
- `CONTRIBUTING.md` — development setup, branch strategy, Conventional Commits,
  PR checklist, testing requirements, and coding standards.
- `CHANGELOG.md` — this file.
- `SECURITY.md` — vulnerability reporting policy.
- `CODE_OF_CONDUCT.md` — Contributor Covenant.
- GitHub issue forms (bug report, feature request) and a pull request template.

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

[Unreleased]: https://github.com/kishorhari/ai-chatbot/compare/v0.1.0-m1...HEAD
[0.1.0-m1]: https://github.com/kishorhari/ai-chatbot/releases/tag/v0.1.0-m1
