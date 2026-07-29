# Milestone 3 — Final Retrospective

**Status:** Milestone 3 (Knowledge Retrieval / RAG) complete. This is the closing
engineering document for M3.

**Headline metrics:** 5 layers (unchanged) · 3 new ports (`EmbeddingProvider`,
`VectorStore`, `KnowledgeRepository`), each proven by 1 contract suite across an
offline reference + a real backend · one additive `ContextProvider` seam on
`ChatService` (M2 behaviour preserved when off) · 6 mechanically-enforced
dependency contracts (+1 over M2) · 6 new ADRs (0011–0016) · domain + application
coverage **99%** · **489** offline tests (+ PostgreSQL/pgvector suites in CI) · a
deterministic golden-dataset retrieval gate at **recall@k = 1.0, MRR = 1.0**.

---

## 1. Milestone objective

M2 gave the platform durable conversation memory: literal recent history, fitted
to a budget, behind a repository port. But the assistant still knew only what was
in the conversation — it could not answer from a corpus of external documents.

Milestone 3 set out to add **Retrieval-Augmented Generation** as a first-class,
*replaceable* infrastructure capability — exactly like the LLM provider (M1) and
persistence (M2) — behind ports proven by contract suites. The defining success
criterion was the same behavioural one used twice before: prove the vector index
and the knowledge store are swappable by running the *same* contract suites
against an offline reference and a real backend (pgvector / PostgreSQL in CI).

The harder, subtler objective was **backward compatibility**: bolt retrieval onto
the M2 chat turn without disturbing it. The bet — inherited from M2's "boundaries
absorb new capability additively" — was that a single Null-Object seam could carry
the entire RAG feature, so that with RAG disabled the M2 chat turn is byte-for-byte
unchanged and every M2 test passes verbatim.

## 2. Architectural concepts introduced

Each concept holds a specific boundary; none is speculative.

- **Knowledge aggregate** (`domain/knowledge`). A `KnowledgeDocument` root owning
  ordered `KnowledgeChunk` entities, with identity, ingestion status, and metadata.
  It exists so ingestion has one consistency boundary distinct from conversations
  (ADR-0011).
- **`EmbeddingVector` value object.** A fixed-dimension vector with cosine
  similarity, defined in the domain so the retriever and the store share one
  vocabulary and the inner layers never touch a numeric-array SDK (ADR-0012).
- **`EmbeddingProvider` port + contract suite.** Text → vector behind an
  interface, with a deterministic offline reference (`FakeEmbeddingProvider`) and a
  real adapter (Ollama). It exists to make embedding a swappable detail and the
  RAG test path offline (ADR-0012).
- **`VectorStore` port + contract suite.** Similarity search / upsert /
  delete-by-document / metadata filter behind an interface, with a fixed distance
  metric (cosine) in the *contract*. It exists so the vector index is replaceable
  and its semantics are guaranteed identical across backends (ADR-0013).
- **`KnowledgeRepository` port + contract suite.** The record store for documents +
  chunks + status, deliberately **separate** from the vector index so the two are
  independently replaceable (ADR-0016).
- **`ChunkingStrategy`** (application). Token-aware fixed-size chunking with
  overlap, reusing the M2 `TokenEstimator`. It exists as a pluggable seam for
  richer chunkers later, deterministic and cheap now (ADR-0014).
- **`IndexingService`** (application). The single ingestion orchestrator: chunk →
  embed → persist record → persist vectors, with compensation so a partial failure
  cannot leave a half-indexed document. It exists so ingestion consistency lives in
  one place (ADR-0016).
- **`Retriever` port + `SemanticRetriever` + `RetrievalService`.** Query → embed →
  search → `RetrievedContext`, with default-`k` and threshold policy in one place.
  It exists so the retrieval *strategy* is swappable behind a port (ADR-0015).
- **`PromptEnricher`** (application, pure). Injects retrieved context into the
  message list, budget-aware and single-leading-system-safe. It exists as a pure
  transformation so enrichment is unit-testable and cannot overflow the budget
  (ADR-0015).
- **`ContextProvider` port + Null/Knowledge implementations.** The single seam
  `ChatService` delegates "obtain-and-enrich context" to — `NullContextProvider`
  (no-op default) or `KnowledgeContextProvider` (retriever + enricher). It exists so
  RAG is one additive collaborator, not accumulated responsibility on `ChatService`
  (ADR-0015).
- **`PgVectorStore` + `SqlAlchemyKnowledgeRepository`** (infrastructure). The
  production backends over pgvector and SQLAlchemy, reusing the M2 async engine.
  They exist as the second implementations — the ones that prove the swap against a
  real database (ADR-0016).

## 3. ADR summary

**ADR-0011 — Knowledge & Retrieval Architecture (RAG).** *Problem:* add external
knowledge without letting an embedding SDK or a vector client leak into the
business logic, and without disturbing the frozen M1/M2 ports. *Decision:* a
`KnowledgeDocument` aggregate; three domain ports (embedding, vector store,
knowledge repository); retrieval and enrichment in the application layer; RAG
reaches the chat turn only through an additive seam. *Consequences:* RAG is
additive infrastructure, provable by the contract-suite device, at the cost of a
second storage concept (record store + vector index).

**ADR-0012 — Embedding Provider Abstraction.** *Problem:* embeddings are
model/vendor-specific and non-deterministic, which would make RAG untestable
offline. *Decision:* an `EmbeddingProvider` port speaking only in `EmbeddingVector`;
a deterministic hashing `FakeEmbeddingProvider` as the reference (the Echo
precedent); a shared contract suite. *Consequences:* the RAG path is offline and
reproducible; the fake is lexical, not semantic (an explicit, documented
trade-off).

**ADR-0013 — Vector Store Abstraction.** *Problem:* vector stores differ in
ordering, filtering, and distance metric; a leaky abstraction would make the swap a
lie. *Decision:* a `VectorStore` port with the distance metric (cosine) and result
ordering fixed *in the contract*; in-memory + pgvector implementations; pgvector in
CI. *Consequences:* the vector index is a genuine seam (Qdrant/others are a
config-only swap), proven not asserted; the cost is a dimensionless column + fresh
dimension enforcement to satisfy one unchanged suite.

**ADR-0014 — Chunking Strategy.** *Problem:* documents exceed embedding/context
limits and must be split deterministically. *Decision:* a `ChunkingStrategy` port
with a token-aware fixed-size + overlap default reusing the M2 `TokenEstimator`; no
semantic chunking yet. *Consequences:* deterministic, cheap, and reproducible;
semantic chunking is a later, behind-the-seam upgrade.

**ADR-0015 — Retrieval Strategy & Prompt Enrichment.** *Problem:* retrieval and
enrichment need a home, and neither `ChatService` nor the pure assembler may
accumulate it. *Decision:* a `Retriever` port + `SemanticRetriever`; a pure
`PromptEnricher`; a single `ContextProvider` port (Null default) that `ChatService`
delegates to — the *one* M2 touch-point, additive. *Consequences:* M2 behaviour is
preserved when RAG is off (verified); all RAG logic stays in `application/knowledge`;
the cost is one more port, justified by the backward-compatibility guarantee.

**ADR-0016 — Knowledge Metadata, Ingestion & Persistence.** *Problem:* ingestion
spans two independent stores, so partial failure risks inconsistency, and metadata
must support filtering. *Decision:* separate record store + vector index;
`IndexingService` with slow-work-first + record-before-vectors + compensation;
scalar metadata with an equality filter; pgvector + SQLAlchemy backends over the M2
engine; cross-store atomicity an explicit non-goal. *Consequences:* no half-indexed
document survives a failure; true two-store atomicity is deferred (compensation is
the mechanism), an honest, documented limit.

## 4. Major architectural decisions

- **Two knowledge stores, not one.** A relational `KnowledgeRepository` record and a
  `VectorStore` index are separate ports so the vector index is independently
  replaceable; the default pgvector backend co-locates both in one PostgreSQL.
  *Rejected:* a single store (couples record and index lifecycles and vendors).
- **RAG as one additive `ContextProvider` collaborator** (Null Object default) on
  `ChatService`, rather than a `Retriever` + `PromptEnricher` pair coordinated *by*
  `ChatService`, or a parallel `RagChatService`. One orchestrator, no accumulated
  retrieval responsibility, M2 behaviour preserved. *Rejected:* both alternatives
  (the first grows `ChatService`; the second duplicates the turn).
- **A deterministic fake embedding as the reference implementation.** An offline,
  network-free, reproducible RAG path — the Echo precedent applied to embeddings.
  *Rejected:* testing only against a live model (flaky, slow, non-reproducible).
- **Distance metric fixed in the port contract** (cosine, `score = 1 − distance`).
  Backends cannot disagree on similarity semantics. *Rejected:* leaving the metric
  to each store (the abstraction would leak).
- **Compensation, not distributed transactions**, for cross-store ingestion
  consistency. Slow work first (nothing to undo on embed failure), record before
  vectors, best-effort cleanup that never masks the cause. *Rejected:* a distributed
  transaction / 2PC (speculative machinery against an unproven need — the M2
  discipline).
- **Metadata filtering applied portably** (in Python for the record `list`; at the
  store for vector search) so SQLite and PostgreSQL behave identically for the
  record repository. *Rejected:* backend-specific JSON operators in the shared path
  (would break the one-suite guarantee).
- **A sixth dependency contract** (`core-vector-agnostic`) forbidding
  `pgvector`/`numpy` in domain/application, mechanizing the embedding/vector-SDK
  boundary the way M2 mechanized the persistence boundary. *Rejected:* trusting
  convention (rots silently).

## 5. Retrieval stack evolution

```
KnowledgeDocument (aggregate: source + ordered chunks + status + metadata)
        ↓ IndexingService: chunk → embed → persist record → persist vectors (compensated)
KnowledgeRepository (record)          VectorStore (index)
   in-memory / SQLAlchemy                in-memory / pgvector
        ↑ one KnowledgeRepositoryContract      ↑ one VectorStoreContract
          (in-memory, SQLite, PostgreSQL)        (in-memory local, pgvector CI)
        │                                    │
        └──────────── query time ────────────┘
SemanticRetriever: embed query (EmbeddingProvider) → VectorStore.search(k, filter)
        ↓ RetrievalService: default-k + threshold policy
RetrievedContext (ordered chunks + scores)
```

Why this demonstrates architectural correctness: the *ports and their behavioural
contracts were fixed before the real backends existed* (M3.1–M3.3 before M3.7).
Adding pgvector and the SQLAlchemy repository was therefore a binding change, not a
redesign — the identical suites the offline references pass are the acceptance
tests the real backends must also pass. Two implementations per port satisfying one
unchanged spec is executable proof the abstractions are real and that
`domain`/`application` are genuinely embedding/vector-ignorant (the
`core-vector-agnostic` contract guarantees no `pgvector`/`numpy` import).

## 6. The ChatService seam (the one M2 touch-point)

```
ChatService.send_message(...)                       ← M2 orchestration, unchanged
   recall → append user → ContextWindowPolicy.select (budget)
        ↓ delegates the whole "obtain-and-enrich" step to ONE collaborator
ContextProvider.enrich(windowed, query, max_context_tokens) → messages
   ├─ NullContextProvider   → returns the messages verbatim   (RAG off: M2 behaviour)
   └─ KnowledgeContextProvider
          RetrievalService.search(query)  →  RetrievedContext
          PromptEnricher.enrich(messages, context, budget)  →  augmented messages
        ↓ back into the unchanged pipeline (augmentation is request-only)
PromptAssembler → CompletionRequest → LLMProvider   ← frozen M1 seam
```

The seam is the whole story of M3's backward compatibility. `ChatService` gained
*one* collaborator and *one* delegation call — `context_provider.enrich(...)` on
the already-windowed messages; it holds no feature flag (the composition root
chooses Null vs Knowledge by `AIP__KNOWLEDGE__ENABLED`). With RAG off,
`NullContextProvider` returns the messages verbatim, no retrieval or enrichment
runs, and the M2 turn is identical — verified by every M2 `test_chat_service.py`
passing unchanged plus `test_rag_disabled_by_default_injects_nothing`. The
`PromptEnricher` is pure and budget-aware, so injected context participates in the
existing token budget and can never overflow `max_context_tokens` or break the
single-leading-system-message invariant.

## 7. Delivery layer

- **HTTP** (`interface/http/routes/knowledge.py`): ingest, list, delete, and a
  debug-search endpoint — each parses transport input, calls one application
  service resolved from the container, and maps a DTO to a wire model. Knowledge is
  additive to the M2 conversation routes.
- **CLI** (`interface/cli/ingest.py`): offline ingestion + query, the HTTP-free way
  to exercise the indexing and retrieval use cases (verified against the fake
  embedder + in-memory store).
- **Composition root**: the sole place that selects the embedding backend, the
  vector backend, and the knowledge backend by config, and chooses `NullContextProvider`
  vs `KnowledgeContextProvider` — the pgvector store and the SQLAlchemy repository
  share one engine (a disposable), reusing the M2 `SessionProvider`.

Delivery stays thin and the toggle stays out of `ChatService`: enabling RAG is a
configuration change at one composition root, not a code change anywhere else —
the same property M1 gave provider selection and M2 gave the persistence backend.

## 8. Testing strategy

- **Unit tests** — knowledge aggregate invariants, `EmbeddingVector` cosine,
  metadata/filter, chunking, indexing consistency (incl. both compensation arms),
  retriever/service policy, the pure enricher (budget, single-system, ranking), the
  ContextProvider seam, mapping round-trips, knowledge settings.
- **Contract tests** — three new shared suites: `EmbeddingContract` (fake +
  Ollama), `VectorStoreContract` (in-memory + pgvector-CI),
  `KnowledgeRepositoryContract` (in-memory + SQLite + PostgreSQL-CI) — alongside the
  M1 provider and M2 repository suites.
- **Evaluation harness** (`tests/eval/`) — a committed golden dataset scored by pure
  recall@k / hit-rate / MRR metrics; an acceptance test gating retrieval quality on
  the offline path, plus retrieval-correctness, metadata-filter, and determinism
  checks. This is the M3 analogue of the rollback test: it proves a behavioural
  guarantee (retrieval *works*) that coverage never could.
- **Coverage** — `domain` + `application` at **99%** (target ≥ 95%); a diagnostic.
- **import-linter** — six contracts (the five from M2 + `core-vector-agnostic`).
- **CI** — lint → type-check → dependency rule → `alembic upgrade head` against a
  **`pgvector/pgvector:pg16`** service container → the full suite with the Postgres
  DSN set, so the vector and knowledge-repository swaps are proven on every push.

Why this validates *architecture*: the contract suites assert behaviour a boundary
promises, independent of who implements it. Five abstractions now pass unchanged
suites across their implementations; `import-linter` proves the dependency
direction; the golden-dataset gate proves the retrieval mechanism actually
retrieves. Together they would catch a boundary regression (the domain importing
`pgvector`, a backend disagreeing on cosine ordering, RAG-off changing the M2 turn)
that a coverage number never would.

## 9. Risks deferred

All deferrals are deliberate, to keep M3 honest and small (roadmap §2, §13):

- **Cross-store atomicity** — two independent stores use compensation, not a
  distributed transaction; a shared PostgreSQL transaction is a later refinement.
- **Re-embedding on model change** — dimension mismatch fails fast; re-indexing an
  existing corpus into a new embedding space is an explicit, deferred operation.
- **Hybrid (keyword+vector) search and reranking** — similarity-only in M3; both
  slot behind the `Retriever` port later.
- **Semantic / LLM chunking** — the `ChunkingStrategy` seam exists; only the
  token-aware default ships.
- **ANN index tuning** (IVFFlat/HNSW parameters) — an exact baseline now; tuning is
  an operational concern behind the unchanged port.
- **Rich document parsing** (PDF tables, OCR, images) — a loader seam is noted;
  plain text / markdown only in M3.
- **Per-user knowledge permissions / tenancy** — the `owner` seam from M2 is where
  enforcement lands in M6; knowledge is not yet tenant-scoped.
- **Streaming retrieval and agent/tool-driven retrieval** — M4+ concerns behind the
  existing ports.

Each is deferred because building it now would be speculation against an unproven
need — the same discipline that kept ingestion on compensation rather than 2PC.

## 10. Lessons learned

- **The contract-suite pattern generalised a third time, unchanged.** What proved
  the provider (M1) and the repository (M2) proved embeddings, the vector store,
  and the knowledge repository with no new machinery — the pattern is now clearly a
  reusable tool, applied to five abstractions.
- **The Null-Object seam carried the entire backward-compatibility guarantee.** One
  additive collaborator with a no-op default meant "M2 is unchanged when RAG is off"
  was provable by *reusing every M2 test verbatim* — the cheapest possible proof.
- **Simpler than expected:** the pgvector swap. Because the `VectorStore` contract
  fixed cosine and ordering up front, the pgvector store was "implement the port +
  a migration," and the existing suite was its acceptance test.
- **Required more thought:** proving retrieval *quality* offline. A deterministic
  fake embedding makes the path reproducible but is lexical, not semantic — so the
  golden dataset had to be designed to be lexically separable, and the gate had to
  be honest that it measures the *mechanism*, not semantic quality. Conflating the
  two would have been the tempting mistake.
- **Principles that hardened:**
  - *Fix the contract before the implementation* — now proven three milestones
    running.
  - *A new capability should attach through one additive seam with a no-op default*,
    so the prior behaviour is preserved by construction and verified by the prior
    tests.
  - *Prove the mechanism, don't dress up the fake* — an offline reference earns a
    reproducible test path, not a claim of production quality; measure quality
    separately and say which you are measuring.
  - *Mechanize every new boundary* — each new class of infrastructure (persistence,
    then vector/embedding) earns its own `import-linter` contract.

## 11. Milestone outcome

Milestone 3 delivered Retrieval-Augmented Generation as replaceable infrastructure:
a `KnowledgeDocument` aggregate, an ingestion orchestrator with compensating
consistency, and three domain ports — embedding, vector store, knowledge repository
— each proven equivalent across an offline reference and a real backend by one
unchanged contract suite, with pgvector and PostgreSQL exercised in CI. RAG reaches
the chat turn through a single additive `ContextProvider` seam whose Null-Object
default leaves the M2 turn byte-for-byte identical when disabled — proven by every
M2 test still passing — and whose enrichment is pure and budget-bounded. Retrieval
quality is gated by a deterministic golden dataset, and the domain/application
layers remain embedding/vector-ignorant and frozen-port-clean, all mechanically
enforced by six `import-linter` contracts.

The platform now answers from an external corpus without any of its load-bearing
boundaries shifting. Knowledge joined the model provider and the database as a
swappable detail behind a stable port — built additively on the M1/M2 core, which
remains the structure the next milestones (agents, integrations, tenancy) will sit
on rather than rewrite. Recommended release tag: **`v0.3.0-m3`**.
