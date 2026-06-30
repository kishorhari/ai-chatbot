# Implementation Checklist — Milestone 1

Sequential, small tasks for the implementation engineer (Chat 2). Each task is
independently reviewable and maps to a sub-milestone (M1.x) and a Conventional
Commit. **Do not implement a file before the inner files it imports exist.**

> Definition of Done per task: code + tests for that file pass, lint + type-check
> clean, dependency-rule check still green.

## M1.0 — Project bootstrap
- [ ] Initialize `pyproject.toml` (Python 3.13, `src/aiplatform` package, deps:
      fastapi, pydantic, pydantic-settings, structlog, httpx; dev: pytest,
      pytest-asyncio, respx, ruff, mypy, import-linter).
- [ ] Create `src/` layout and empty package `__init__.py` files per the folder structure.
- [ ] Add `.gitignore` (incl. `.env`, `venv/`, `__pycache__`, caches).
- [ ] Add `.env.example` with every planned setting key documented.
- [ ] Configure `ruff` (lint+format) and `mypy` (strict on `domain`/`application`).
- [ ] Add CI workflow skeleton (lint → type-check → import-linter → tests).
- [ ] Add `import-linter` layered contract (domain < application < {infra, interface} < composition).

## M1.1 — Configuration & logging
- [ ] `config/settings.py`: nested `AppSettings` (env, server, logging, llm, ollama),
      env prefix `AIP__`, nested delimiter `__`, `SecretStr` for future secrets.
- [ ] Verify **fail-fast**: invalid/missing required config raises at load, not at request.
- [ ] **Guard:** `settings.py` imports nothing from logging (loads first).
- [ ] `logging/context.py`: correlation-id `contextvar` + get/set helpers.
- [ ] `logging/setup.py`: structlog config; JSON in non-local, console in local;
      inject correlation id; redact `SecretStr`; stdout only.

## M1.2 — Domain contracts (pure; no I/O, no logging, no third-party except pydantic)
- [ ] `domain/llm/messages.py`: `Role` enum (SYSTEM/USER/ASSISTANT), `ChatMessage` VO.
- [ ] `domain/llm/requests.py`: `GenerationParams`, `CompletionRequest` (immutable).
- [ ] `domain/llm/responses.py`: `TokenUsage`, `CompletionChunk`, `CompletionResult`.
- [ ] `domain/llm/capabilities.py`: `ProviderCapabilities`.
- [ ] `domain/llm/errors.py`: full `LLMError` hierarchy with `retryable` + `cause`.
- [ ] `domain/llm/ports.py`: `LLMProvider` (stream_chat, complete_chat default, capabilities).
- [ ] `application/llm/provider_registry.py`: `ProviderRegistry` **port** only (get, default_name).
- [ ] **Guard:** confirm value objects import nothing from `ports`.

## M1.3 — Echo provider + contract suite
- [ ] `infrastructure/llm/echo/adapter.py`: `EchoProvider` implementing the port,
      deterministic token-by-token echo, stub capabilities/usage, no network.
- [ ] `tests/contract/provider_contract.py`: shared suite asserting the port
      invariants (terminal `is_final`, complete==joined deltas, error types,
      cancellation, pure `capabilities`).
- [ ] Run the contract suite against `EchoProvider` — green.

## M1.4 — Ollama adapter
- [ ] `infrastructure/llm/ollama/mapping.py`: domain→Ollama request, Ollama→chunk,
      transport/HTTP status → `LLMError` subtype mapping.
- [ ] `infrastructure/llm/ollama/adapter.py`: `OllamaProvider` over async httpx
      streaming; connect/total timeouts from settings; connect-phase retries only;
      cancellation releases the stream.
- [ ] Run the contract suite against `OllamaProvider` (integration, opt-in marker).
- [ ] Verify each `LLMError` subtype via simulated failures (respx).

## M1.5 — Composition + registry
- [ ] `composition/container.py`: load settings → configure logging → build
      providers (Ollama always; Echo in local/test) → build concrete registry.
- [ ] Concrete `ProviderRegistry` (dict-backed) selecting default by config.
- [ ] `composition/bootstrap.py`: lifecycle entry tying container into app + CLI.
- [ ] Verify provider swap by `AIP__LLM__DEFAULT_PROVIDER=echo` (no code change).

## M1.6 — Delivery surfaces
- [ ] `interface/http/lifespan.py`: build container on startup, dispose on shutdown.
- [ ] `interface/http/app.py`: FastAPI factory; correlation-id middleware; no business logic.
- [ ] `interface/http/routes/health.py`: `/health` (liveness, always 200),
      `/ready` (200 only after composition completes).
- [ ] `interface/cli/probe.py`: send one prompt to the default provider, print the
      stream as it arrives (dev validation of streaming + cancellation).

## M1.7 — Hardening & exit review
- [ ] Confirm `import-linter` passes in CI.
- [ ] Confirm coverage targets met on domain/application (see testing strategy).
- [ ] Smoke test: app boots, `/ready` flips to 200, CLI probe streams against Echo.
- [ ] Run Milestone 1 exit-criteria review (roadmap §5) and check off each item.
- [ ] Update docs cross-links; tag release `v0.1.0-m1`.
