# Milestone 1 — Exit-Criteria Review

Maps each roadmap §5 exit criterion to its shipped evidence. All quality gates
pass: `ruff` (lint+format), `mypy` (37 files), `import-linter` (4 contracts), and
`pytest -m "not live"` (**200 passed**). Coverage: **domain 100%, application
100%**, 96% overall.

| # | Exit criterion | Status | Evidence |
|---|----------------|:------:|----------|
| 1 | **Dependency rule passes in CI** — domain imports nothing outward; only composition imports infrastructure; build fails on violation. | ✅ | `.importlinter` (4 contracts) run by `.github/workflows/ci.yml`; `lint-imports` → "4 kept, 0 broken". Refined per ADR-0006. |
| 2 | **Both providers pass the identical contract suite** — Echo (unit) and Ollama (respx). | ✅ | `tests/contract/provider_contract.py` run by `test_echo_contract.py` and `test_ollama_contract.py` (10 passed). |
| 3 | **Config fails fast** — invalid/missing required config aborts startup with a clear message. | ✅ | `tests/unit/config/test_settings.py::test_invalid_config_fails_fast_at_load` (8 cases) + `test_unknown_key_is_rejected`. |
| 4 | **`/ready` reflects composition** — 200 only after wiring completes. | ✅ | `tests/unit/interface/http/test_app.py::test_ready_returns_200_after_wiring` and `::test_ready_is_503_before_wiring`. |
| 5 | **Streaming + cancellation verified** — mid-stream cancellation releases the connection and raises nothing (Echo tested; Ollama confirmed). | ✅ | Echo/Ollama: contract `test_cancellation_midstream_raises_nothing`; Ollama `test_cancellation_midstream_closes_cleanly`; live `test_live_cancellation_midstream_raises_nothing` (opt-in). |
| 6 | **Every `LLMError` subtype provably produced** by a simulated failure; no transport-native exception escapes. | ✅ | `tests/unit/infrastructure/ollama/test_ollama_mapping.py` (status + transport mapping) and `test_ollama_adapter.py::test_http_status_maps_to_error`, `…read_timeout…`, `…connect_error…`, `…malformed_json…`. |
| 7 | **Provider swap is config-only** — `AIP__LLM__DEFAULT_PROVIDER=echo` switches providers with no code edit. | ✅ | `test_container.py::test_provider_swap_is_configuration_only` and `::test_default_provider_from_environment`; manually confirmed via the CLI probe. |
| 8 | **Logs are structured and correlated** — one `correlation_id` across a request; no secret logged. | ✅ | `test_setup.py` (correlation field, redaction), `test_middleware.py` (boundary propagation), `test_settings.py::test_secret_is_redacted`. |
| 9 | **Docs current** — ADRs, roadmap, dependency matrix, testing strategy reflect shipped code. | ✅ | ADR-0001..0006, this review, the retrospective, and the updated dependency matrix. |

## Live verification (opt-in)

`tests/integration/test_ollama_live.py` (marked `live`, excluded from CI) verifies
the structural contract against a real Ollama. Run with:

```bash
AIP__OLLAMA__BASE_URL=http://localhost:11434 AIP__OLLAMA__MODEL=llama3 pytest -m live
```

## Coverage notes

`domain` and `application` are at 100% (target ≥95%). The Ollama
adapter/mapping sit at 91–92%; the uncovered lines are error-message-extraction
fallbacks and the non-terminal retry branch — the testing strategy explicitly
deprioritizes chasing coverage on thin transport glue. A green two-provider
contract suite is the more meaningful signal.

## Verdict

All nine exit criteria are met. **Milestone 1 is complete.**
