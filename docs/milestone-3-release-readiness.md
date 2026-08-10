# Milestone 3 — Release Readiness Review

**Proposed release:** `v0.3.0-m3` — Knowledge Retrieval (RAG).
**Prepared:** 2026-07-29 (M3.8 hardening). **Decision owner:** Principal Architect.

This review is the go/no-go gate between "M3 is code-complete" and "M3 is tagged".
It records the state of every quality gate, the risk posture, the known
limitations shipping *by design*, and the concrete release actions.

---

## 0. Addendum — first real CI run exposed defects (2026-08-10, M3.9)

**The original §1 recommendation below claimed the pgvector/PostgreSQL swap was
"proven in CI." That claim was premature and is corrected here — it is left in
place rather than rewritten, so the record is honest.**

When the M3 work was finally placed on a ref the CI workflow triggers on (PR
`feat/chat-service → main`, #1), the mandatory production-persistence suites ran
against the real `pgvector/pgvector:pg16` service for the **first time** — the
`main` branch had never advanced past M1, so this M2+M3 code had never actually
executed in CI. The run (`31383581550`) **failed**: `19 failed, 502 passed, 0
skipped`. The suites did *run* (not skip), which is the good news; they exposed
three genuine defects:

- **A — pgvector upsert** (`AttributeError: 'MetaData' object has no attribute
  '_bulk_update_tuples'`): the `on_conflict_do_update` was built against the ORM
  entity, so the `"metadata"` key was misresolved to SQLAlchemy's reserved
  declarative `.metadata`. **Fixed** by constructing the upsert at the Core-table
  level (keys resolve as column names); DB column name unchanged.
- **B — knowledge-repository FK ordering** (`asyncpg.ForeignKeyViolationError`):
  chunk INSERTs raced ahead of the parent document because the unit of work does
  not order the two mappers without a relationship. **Masked on SQLite**, which
  does not enforce foreign keys by default. **Fixed** by flushing the document
  before the chunks; the local SQLite contract fixture now enables
  `PRAGMA foreign_keys=ON` so this fault can no longer hide locally.
- **C — DSN fail-fast test isolation**: `test_pgvector_backend_without_dsn_fails_fast`
  and `test_postgres_backend_without_dsn_fails_fast` (the latter an **M2** test —
  confirming M2's PostgreSQL path had likewise never truly run green in CI)
  assumed no DSN, but CI exports `AIP__PERSISTENCE__POSTGRES__DSN`. **Fixed** in
  the tests (explicit `monkeypatch.delenv`); production fail-fast behaviour is
  unchanged.

All three are fixed on branch `fix/m3-postgres-release-hardening`; local gates are
green and A/B/C were each reproduced locally before fixing. **The M3 release gate
remains OPEN until a corrected CI run shows both mandatory suites RUN and PASS
(not skipped).** `v0.3.0-m3` must not be tagged/released against `45dfdb7`; the
release will move to the corrected commit once CI is green.

---

## 1. Recommendation

> ⚠️ **Superseded by §0 (2026-08-10).** The "proven in CI" claim below was premature;
> the first real CI run failed and the gate is now OPEN pending a corrected run.

**GO — tag `v0.3.0-m3`.** Every Milestone 3 exit criterion is met with mapped
evidence (see the [exit review](milestone-3-exit-review.md)); all local gates are
green; the swap-critical claims (pgvector, PostgreSQL) are proven in CI, not
asserted; and RAG is off by default, so the release is behaviourally identical to
`v0.2.0-m2` for any deployment that does not opt in via `AIP__KNOWLEDGE__ENABLED`.

Semantic version rationale: a **minor** bump (`0.2 → 0.3`) — new, backward-compatible
functionality. No public port changed; the M1 `LLMProvider`/`CompletionRequest` and
M2 `ConversationRepository`/`Conversation` are frozen and untouched.

## 2. Gate status

| Gate | Command | Result |
|------|---------|:------:|
| Lint + format | `ruff check . && ruff format --check .` | ✅ clean |
| Type-check | `mypy src` | ✅ 102 files, no issues |
| Dependency rule | `lint-imports` | ✅ **6 kept / 0 broken** |
| Tests (offline) | `pytest -m "not live"` | ✅ **489 passed, 22 skipped, 3 deselected** |
| Core coverage | `--cov=aiplatform.domain --cov=aiplatform.application` | ✅ **99%** (target ≥ 95%) |
| Retrieval quality | `pytest tests/eval/` | ✅ recall@1 = recall@3 = **1.0**, MRR = **1.0** |
| Migration (offline) | `alembic upgrade head --sql` / `downgrade 0002:0001 --sql` | ✅ upgrade + downgrade DDL render |

The 22 local skips are the PostgreSQL knowledge-repository suite and the pgvector
vector-store suite — CI-only, gated on `AIP__TEST_POSTGRES_DSN` and (for pgvector)
`importorskip`. The 3 deselected are the opt-in live Ollama tests.

## 3. CI must-pass before tagging

The authoritative proof of the vector/knowledge swap runs only in CI (this
sandbox has no Docker/PostgreSQL and cannot install `pgvector`). Before applying
the tag, confirm the CI run on the release commit is green, specifically:

- `pip install -e ".[dev,postgres]"` resolves (incl. `pgvector>=0.3`).
- `alembic upgrade head` applies against `pgvector/pgvector:pg16` (creates the
  `vector` extension + knowledge tables).
- `test_pgvector_vector_store_contract.py` **runs** (not skips) and passes.
- `test_postgres_knowledge_repository_contract.py` **runs** and passes.
- The full suite is green with the Postgres DSN set.

If any pgvector/PostgreSQL suite *skips* in CI, that is a **no-go** — it means the
swap was asserted, not proven, for this release.

## 4. Risk posture

| Risk | Status at release | Residual |
|------|-------------------|----------|
| Embedding non-determinism makes RAG untestable | **Mitigated** — deterministic `FakeEmbeddingProvider`; offline path reproducible (`test_a_fresh_index_reproduces_the_same_ranking`). | None for the test path; real embedding quality is unmeasured by design. |
| Vector-store semantics differ across backends | **Mitigated** — cosine + ordering fixed in the contract; one suite over in-memory + pgvector-in-CI. | Depends on the CI pgvector run being green (§3). |
| Retrieved context overflows the token budget | **Mitigated** — pure, budget-aware `PromptEnricher`; verified (`test_max_context_tokens_caps_injection`, `test_zero_budget_injects_nothing`). | None. |
| Embedding model change invalidates stored vectors | **Partially mitigated** — dimension mismatch fails fast; model/dimension recorded. | Re-embedding an existing corpus is a **deferred** manual operation (§6). |
| RAG accretes responsibility onto `ChatService` | **Mitigated** — one `ContextProvider` collaborator, no flag in `ChatService`; enforced by review + the seam design. | None structurally. |
| pgvector operational surface (extension, index) | **Accepted** — exact/flat baseline reusing the M2 engine. | ANN index tuning deferred; not needed at M3 scale. |
| Cross-store partial indexing | **Mitigated** — compensation (record+vector cleanup) verified (`test_vector_failure_rolls_back_the_record`, `..._triggers_vector_cleanup`). | True two-store atomicity deferred; compensation is best-effort. |

No open **high** risk blocks the release. Every residual is a documented,
deliberate deferral, not an unknown.

## 5. Security & configuration

- No secret is logged; the Postgres DSN and any embedding API key are read only
  through `Settings` (`SecretStr`), consistent with M1/M2.
- RAG is **opt-in**: `AIP__KNOWLEDGE__ENABLED` defaults to off. A default
  deployment gains no new network calls, no new required config, and no new
  storage — it behaves exactly as `v0.2.0-m2`.
- Selecting `vector=pgvector` fails fast with a clear message if
  `AIP__PERSISTENCE__POSTGRES__DSN` is unset, *before* the driver is imported
  (`test_pgvector_backend_without_dsn_fails_fast`).
- New optional dependencies (`pgvector`, `asyncpg`) live in the `postgres` extra;
  driverless installs are unaffected.

## 6. Known limitations shipping by design

These are **not** defects; they are the roadmap's explicit deferrals (§13) and are
documented so operators are not surprised:

- **No re-embedding on model change.** Changing the embedding model/dimension
  requires an explicit, not-yet-built re-index of the corpus; the store fails fast
  on a dimension mismatch rather than silently mixing spaces.
- **Similarity-only retrieval** (cosine top-k + equality metadata filter). No
  hybrid search, no reranking.
- **Token-aware fixed-size chunking only.** No semantic chunking.
- **Plain text / markdown ingestion.** No PDF/OCR/table extraction.
- **No cross-store distributed transaction.** Ingestion consistency is by
  compensation.
- **Knowledge is not tenant-scoped.** Per-user permissions land with M6 auth/RBAC.
- **The offline retrieval gate measures the mechanism, not semantic quality.** The
  fake embedding is lexical; real quality is a separate, future measurement.

## 7. Release actions (post-approval)

In order, on a release commit off `feat/chat-service` → `main`:

1. **Recommended:** bump `pyproject.toml` `version` to `0.3.0` (currently `0.1.0`;
   it was not bumped for M2 either — flagged here for the architect's decision, as
   the tag, not the package version, has carried the milestone to date).
2. Confirm the CI run is green on the release commit, including the pgvector /
   PostgreSQL suites **running** (§3).
3. Move the CHANGELOG `[Unreleased]` section to `[0.3.0-m3] - <release date>` and
   refresh the compare links.
4. Tag `v0.3.0-m3` (annotated) on the merge commit; sole authorship
   (no `Co-Authored-By` trailer), per the project git strategy.
5. Do **not** push until the architect approves the release (established workflow).

## 8. Rollback

Low-risk by construction. If a problem surfaces post-release:

- **Feature-level:** set `AIP__KNOWLEDGE__ENABLED=off` — the deployment reverts to
  M2 behaviour with no redeploy of code, since the toggle is pure composition.
- **Schema-level:** `alembic downgrade 0002:0001` drops the knowledge tables (the
  `vector` extension is intentionally left in place — dropping a shared extension is
  unsafe); the conversation schema (`0001`) is untouched.
- **Release-level:** `v0.2.0-m2` remains a valid, self-contained release; nothing
  in M3 mutated M1/M2 code or schema.

## 9. Verdict

**Release-ready.** Recommend tagging **`v0.3.0-m3`** once the CI run on the release
commit is confirmed green with the pgvector and PostgreSQL contract suites
executing. The release is additive, off by default, and reversible at the flip of
one configuration key.
