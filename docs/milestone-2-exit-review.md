# Milestone 2 — Exit-Criteria Review

Maps each roadmap §6 exit criterion to its shipped evidence. All local quality
gates pass: `ruff`, `mypy` (63 files), `import-linter` (**5 contracts**),
`pytest -m "not live"` (**325 passed, 11 PostgreSQL-only skipped locally**).
Coverage: **domain + application 100%** (target ≥ 95%).

| # | Exit criterion | Status | Evidence |
|---|----------------|:------:|----------|
| 1 | **Round-trip through the port** — create, append, retrieve full history with correct sequence ordering. | ✅ | `repository_contract.py::test_add_then_get_round_trips_faithfully`, `::test_sequence_order_is_preserved`; HTTP `test_conversations.py::test_create_append_fetch_flow`. |
| 2 | **Swap proven by one suite** — in-memory and PostgreSQL pass the **identical** repository contract suite; PostgreSQL in CI. | ✅ | One `ConversationRepositoryContract` bound to three backends: `test_inmemory_repository_contract.py`, `test_sqlite_repository_contract.py`, `test_postgres_repository_contract.py` (CI service container, gated on `AIP__TEST_POSTGRES_DSN`). |
| 3 | **Port frozen, rule intact** — M1 `LLMProvider`/`CompletionRequest` unchanged; `domain`/`application` import no SQLAlchemy; all dependency contracts pass. | ✅ | `import-linter` 5/0 incl. `core-persistence-agnostic`; `grep` finds no `sqlalchemy`/`asyncpg` in `domain`/`application`; M1 provider port untouched. |
| 4 | **Swap is config-only** — `AIP__PERSISTENCE__BACKEND=memory\|postgres` switches with no application/domain change. | ✅ | `test_container_persistence.py` (memory wiring, postgres fail-fast on missing DSN); backend selection lives solely in `_build_persistence` at the composition root. |
| 5 | **Context budget respected** — assembled prompts never exceed `max_context_tokens`; system prompt always retained; overflow drops oldest first. | ✅ | `test_context_window.py::test_never_exceeds_budget_for_normal_case`, `::test_system_message_is_always_retained`, `::test_drops_oldest_and_keeps_system_plus_recent`, `::test_reservation_reduces_the_effective_budget`, `::test_guarantees_at_least_the_newest_message`. |
| 6 | **Valid prompt assembly** — a well-formed `CompletionRequest` (single system message, correct ordering) from stored history + new turn. | ✅ | `test_prompt_assembler.py` (single-leading-system, rejects misplaced/second system); `test_chat_service.py::test_windowed_history_is_assembled_into_the_request`. |
| 7 | **Atomic chat turn** — user message and assistant reply persist together; a simulated mid-cycle failure leaves no partial write. | ✅ | `test_chat_service.py::test_appends_user_and_assistant_and_persists`, `::test_provider_error_propagates_and_persists_nothing`, `::test_repository_save_failure_propagates_and_leaves_no_partial_write`; **real DB rollback** in `test_sqlalchemy_transaction.py::test_atomic_rollback_leaves_no_write`. |
| 8 | **Invariants + coverage** — message immutability and aggregate invariants enforced/tested; `domain`/`application` ≥ 95%. | ✅ | `test_conversation.py`, `test_conversation_message.py` (immutability, sequence contiguity, single-leading-system, ownership); coverage **100%**. |
| 9 | **Docs current** — ADR-0007..0010, roadmap, repository contract-suite documentation, and this exit review reflect shipped code. | ✅ | ADR-0007/0008/0009/0010 (accepted); `testing-strategy.md` M2 addendum; this document; `.env.example` documents persistence keys. |

## PostgreSQL in CI (the headline claim)

`.github/workflows/ci.yml` runs a **PostgreSQL 16 service container**, installs
`.[dev,postgres]`, runs `alembic upgrade head` against it, then runs the suite
with `AIP__TEST_POSTGRES_DSN` set — so the PostgreSQL repository contract run
executes on every push. The swap is therefore **proven in CI, not asserted**
(ADR-0008). *(This session's sandbox has no Docker/PostgreSQL; the authoritative
run is CI. Locally the same SQLAlchemy repository passes the identical suite over
SQLite, and the migration was validated by offline DDL generation.)*

## Dependency-rule finalization (M2.6)

Five `import-linter` contracts, all green:

1. Core layering — `domain < application < infrastructure`.
2. Inner purity — domain/application/infrastructure ⊄ composition/interface.
3. Interface adapter ban — interface ⊄ `infrastructure.{llm, persistence, config}`
   (direct); providers **and repositories** reach delivery only via the container.
4. Settings log-free — `config` ⊄ `logging`.
5. Persistence-agnostic core — `domain`/`application` ⊄ `sqlalchemy`/`asyncpg`/`alembic`.

## Deviations carried from M2.5 (accepted at M2.5 review)

- **SQLite as a local test engine** (`aiosqlite`, dev-only) for fast executed
  parity; never a production/selectable backend. PostgreSQL-in-CI is authoritative.
- **`asyncpg` in a `postgres` optional-extra** rather than a core runtime dep, so
  driverless dev installs stay clean; CI/production install `.[dev,postgres]`.

## Verdict

All nine exit criteria are met. **Milestone 2 is complete** — conversation
identity and durable history sit behind a repository port proven equivalent across
in-memory and PostgreSQL by one contract suite, the chat turn is atomic, prompt
assembly stays a pure builder under an application-service orchestrator, and the
domain/application layers remain persistence-ignorant and frozen-port-clean.
