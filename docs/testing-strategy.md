# Testing Strategy — Milestone 1

## Test taxonomy

| Type | Purpose | Speed | Network | Runs in CI |
|------|---------|-------|---------|------------|
| **Unit** | One module's logic in isolation (VOs, mapping, settings, logging context) | fast | none | every push |
| **Contract** | A behavioral spec every `LLMProvider` impl must satisfy; run against multiple impls | fast (Echo) | none (Echo) | every push (Echo) |
| **Integration** | Real adapter against real/simulated transport (Ollama via respx, and opt-in live) | medium | mocked or live | every push (respx); live = opt-in |
| **Smoke** | End-to-end boot: app starts, `/ready` flips, CLI probe streams via Echo | medium | none | nightly / pre-release |

Tooling: `pytest`, `pytest-asyncio` (async streams), `respx` (mock httpx for
Ollama), `import-linter` (dependency rule as a test gate).

---

## Per-file test requirements

| File | Unit | Contract | Integration | Smoke |
|------|:----:|:--------:|:-----------:|:-----:|
| `domain/llm/messages.py` (VOs, Role) | ✅ | — | — | — |
| `domain/llm/requests.py` | ✅ | — | — | — |
| `domain/llm/responses.py` | ✅ | — | — | — |
| `domain/llm/capabilities.py` | ✅ | — | — | — |
| `domain/llm/errors.py` (taxonomy, `retryable`) | ✅ | — | — | — |
| `domain/llm/ports.py` | — (interface; exercised via contract) | ✅ | — | — |
| `application/llm/provider_registry.py` | ✅ | — | — | — |
| `infrastructure/config/settings.py` | ✅ (fail-fast, layering, redaction) | — | — | — |
| `infrastructure/logging/context.py` | ✅ | — | — | — |
| `infrastructure/logging/setup.py` | ✅ (correlation field, redaction) | — | — | ✅ |
| `infrastructure/llm/echo/adapter.py` | ✅ | ✅ | — | ✅ |
| `infrastructure/llm/ollama/mapping.py` | ✅ (each error mapping) | — | — | — |
| `infrastructure/llm/ollama/adapter.py` | — | ✅ | ✅ (respx + opt-in live) | — |
| `composition/container.py` | ✅ (wiring, provider swap) | — | — | ✅ |
| `composition/bootstrap.py` | — | — | ✅ | ✅ |
| `interface/http/app.py` | — | — | ✅ (TestClient) | ✅ |
| `interface/http/routes/health.py` | ✅ | — | ✅ | ✅ |
| `interface/cli/probe.py` | — | — | ✅ (against Echo) | ✅ |

---

## The provider contract suite (the centerpiece)

A single parametrized suite in `tests/contract/provider_contract.py`, run against
**every** `LLMProvider` implementation. Asserts the ADR-0003 invariants:

1. A successful stream yields ≥1 chunk and terminates with exactly one `is_final=True`.
2. `complete_chat(req).text == "".join(c.delta for c in stream_chat(req))` for a
   deterministic request.
3. Each failure mode surfaces as the correct `LLMError` subtype; **no** transport-native
   exception escapes.
4. Cancelling mid-stream releases resources and raises nothing.
5. `capabilities()` performs no I/O and is internally consistent.

Echo runs this suite on every push (fast, offline). Ollama runs it with `respx`
mocks on every push and against a live Ollama under an opt-in marker
(`-m live`). **Both must pass the identical suite** — this is the executable
proof that the abstraction is real (ADR-0004).

---

## Coverage philosophy

- **`domain` and `application`:** high coverage (target ≥ 95%). They are pure and
  cheap to test; gaps here are unjustified.
- **`infrastructure` adapters:** cover all branches of error mapping and the
  streaming/cancellation paths; do not chase coverage on thin transport glue.
- **`interface`/`composition`:** covered by integration + smoke, not unit-coverage targets.
- Coverage is a **diagnostic, not a goal** — a green contract suite across two
  providers matters more than a coverage percentage.

## What we deliberately do NOT test in Milestone 1
Chat/memory/persistence behavior (later steps), live cloud providers (none exist
yet), load/performance (premature), and HTTP streaming transport/SSE (arrives at
roadmap Step 7).
