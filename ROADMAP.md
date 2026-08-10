# Roadmap

The platform is built in sequential milestones. Each is a vertical slice that keeps
the architecture's boundaries intact and adds capability behind stable ports. The
ordering is dependency-driven: identity and persistence (M2) precede retrieval (M3),
which precedes agents (M4), and so on.

This document is the long-range plan. Per-milestone engineering detail (sub-tasks,
file order, test mapping) lives under [`docs/roadmap/`](docs/roadmap/) as each
milestone is started. Milestone 1's full closeout is in the
[exit review](docs/milestone-1-exit-review.md) and
[retrospective](docs/milestone-1-retrospective.md).

**Legend:** ✅ Completed · 🔜 Next · 🗓️ Planned

| Milestone | Theme | Status | Tag |
|-----------|-------|:------:|-----|
| [M1](#milestone-1--foundation-) | Foundation | ✅ Completed | `v0.1.0-m1` |
| [M2](#milestone-2--conversation--persistence) | Conversation & persistence | 🔜 Next | `v0.2.0-m2` |
| [M3](#milestone-3--retrieval-augmented-generation-rag) | RAG | 🗓️ Planned | `v0.3.0-m3` |
| [M4](#milestone-4--tool-calling--agents) | Agents | 🗓️ Planned | `v0.4.0-m4` |
| [M5](#milestone-5--integrations--channels) | Integrations | 🗓️ Planned | `v0.5.0-m5` |
| [M6](#milestone-6--multi-tenancy--saas) | Multi-tenancy & SaaS | 🗓️ Planned | `v0.6.0-m6` |
| [M7](#milestone-7--cloud-providers--routing) | Cloud providers & routing | 🗓️ Planned | `v0.7.0-m7` |

---

## Milestone 1 — Foundation ✅

**Status:** Completed and accepted (`v0.1.0-m1`).

### Goal
Establish a Clean-Architecture core in a modular monolith with a provably
vendor-neutral LLM provider abstraction, so that every later feature can be layered
on without disturbing the boundaries — and so that swapping the model provider is a
configuration change, not a rewrite.

### Deliverables
- Clean Architecture layering (domain / application / infrastructure / interface / composition).
- Streaming-first `LLMProvider` port with a derived non-streaming path.
- `EchoProvider` (deterministic reference) and `OllamaProvider` (real), both passing one shared contract suite.
- Provider-agnostic `LLMError` taxonomy with a `retryable` signal.
- `ProviderRegistry` with config-driven default + named lookup.
- Composition root as the single wiring point.
- FastAPI delivery (`/health`, `/ready`) and a CLI probe.
- Fail-fast pydantic settings; structured logging with per-request correlation IDs.
- Contract / unit / integration testing; `import-linter` dependency-rule enforcement in CI.

### Exit criteria
All nine met — see the [exit-criteria review](docs/milestone-1-exit-review.md).
Headline: dependency rule green in CI (4 contracts), both providers pass the
identical contract suite, config fails fast, provider swap is config-only, streaming
cancellation verified, every `LLMError` subtype provably produced, logs structured
and correlated with secrets redacted. 200 offline tests; `domain`/`application` 100%
coverage.

### Risks (retired or carried forward)
- *The port is secretly "Ollama-shaped."* **Mitigated** by the Echo provider + shared
  contract suite. Residual: not yet proven against a structurally different cloud
  provider (SSE, tool calls) — carried into M7.
- *Repository seam unexercised* (ADR-0005) — carried into M2.

### Dependencies
None — this is the base.

---

## Milestone 2 — Conversation & persistence

**Status:** 🔜 Next — architecture package ratified. See
[`docs/roadmap/milestone-2.md`](docs/roadmap/milestone-2.md) and
ADR-[0007](docs/adr/0007-conversation-message-aggregate.md) /
[0008](docs/adr/0008-persistence-repository-and-transactions.md) /
[0009](docs/adr/0009-context-window-and-prompt-assembly.md). Implementation not yet started.

### Goal
Introduce conversation identity and durable message history behind a repository
port, building and testing all memory logic against an in-memory implementation
first, then proving the abstraction by swapping in PostgreSQL with no change to
application or domain code (ADR-0005).

### Deliverables
- **Conversation identity** — a `Conversation` aggregate with stable identity and owner/principal.
- **Message aggregate** — ordered messages with roles, timestamps, and token accounting.
- **Repository pattern** — a `ConversationRepository` port in the inner layers; an in-memory implementation first.
- **Repository contract suite** — mirroring the provider contract suite, guarding ordering/concurrency assumptions.
- **Context window** — assembling a bounded message window within the model's context budget.
- **Prompt assembly** — composing system prompt + memory + user turn into a `CompletionRequest`.
- **Memory** — short-term conversational memory wired through the repository.
- **PostgreSQL swap** — a SQLAlchemy-backed repository swapped in at the composition root.

### Exit criteria
- A conversation can be created, appended to, retrieved, and replayed through the port.
- The in-memory and PostgreSQL repositories pass the **identical** repository contract suite.
- Swapping in-memory ↔ PostgreSQL is a composition-root/config change with all tests green.
- Context-window assembly respects the model's token budget and is unit-tested at the boundary.
- No application or domain module imports SQLAlchemy; the dependency rule still passes.

### Risks
- *In-memory repo encodes behavior PostgreSQL can't honor* (ordering, concurrency). **Mitigation:** repository contract tests written before the SQL impl.
- *Aggregate shape resists relational mapping.* **Mitigation:** design the aggregate for relational storage up front (ADR-0005); review before building memory on top.
- *Transaction boundaries / Unit of Work.* Deferred until real transactions exist (the PostgreSQL step), per ADR-0005 — avoid speculative UoW over in-memory storage.

### Dependencies
M1 (ports, composition root, contract-suite pattern).

---

## Milestone 3 — Retrieval-Augmented Generation (RAG)

**Status:** 🗓️ Planned.

### Goal
Add document grounding so the assistant can answer from a private corpus: ingest
documents, embed and store them in a vector database, retrieve semantically relevant
context at query time, and assemble it into the prompt — all behind ports, mirroring
the provider/repository abstraction.

### Deliverables
- **Embeddings** — an `Embedder` port with at least one adapter (local/Ollama embeddings first).
- **Vector database** — a `VectorStore` port with a concrete implementation (e.g. pgvector / Qdrant).
- **PDF ingestion** — a document-loading + chunking pipeline producing embeddable units.
- **Semantic search** — top-k retrieval with similarity scoring behind the `VectorStore` port.
- **RAG pipeline** — retrieve → rank → assemble context → generate, composed in the application layer.

### Exit criteria
- A PDF can be ingested, chunked, embedded, and stored end-to-end.
- A query retrieves relevant chunks and the assembled prompt includes cited context.
- Embedder and vector-store backends are swappable by configuration; the dependency rule holds.
- Retrieval quality is measured on a small fixed evaluation set (recall@k) and recorded.

### Risks
- *Chunking strategy quality* drives answer quality. **Mitigation:** make chunking a strategy behind a port; evaluate.
- *Embedding/model dimension coupling* to a specific provider. **Mitigation:** store embedding model + dimension as metadata; guard on mismatch.
- *Cost/latency of embedding large corpora.* **Mitigation:** batch + background ingestion (depends on M5 job infrastructure if scaled).

### Dependencies
M2 (persistence and the repository pattern; vector storage reuses the storage seam).

---

## Milestone 4 — Tool calling & agents

**Status:** 🗓️ Planned.

### Goal
Move from single-shot completion to goal-directed behavior: let the model call
tools, plan multi-step tasks, reason across steps, and retain agent-scoped memory —
with tool execution sandboxed behind a port and the agent loop owned by the
application layer.

### Deliverables
- **Tool calling** — a `Tool` abstraction and a provider-agnostic tool-call protocol on the port.
- **AI agents** — an agent loop (observe → decide → act → observe) in the application layer.
- **Planning** — task decomposition into ordered/conditional steps.
- **Multi-step reasoning** — iterative tool use with intermediate state.
- **Agent memory** — scratchpad / working memory distinct from conversation memory.

### Exit criteria
- The agent completes a multi-step task that requires ≥2 tool calls, end-to-end.
- Tool execution is isolated behind a port; adding a tool is an adapter + registration.
- Provider tool-call differences are normalized at the adapter boundary (no vendor shape leaks).
- The agent loop is bounded (max steps / budget) and cancellation-safe.

### Risks
- *Tool-call schemas differ sharply across providers* (and strain the port — the M1 retrospective's open question). **Mitigation:** introduce a third (cloud) provider early to re-prove the contract before building heavily on it.
- *Unbounded loops / runaway cost.* **Mitigation:** hard step and token budgets; observable per-step metrics.
- *Tool side effects / safety.* **Mitigation:** explicit allow-list and sandboxing of tool adapters.

### Dependencies
M2 (memory/persistence) and ideally an early M7 cloud provider to validate tool-call
framing.

---

## Milestone 5 — Integrations & channels

**Status:** 🗓️ Planned.

### Goal
Connect the assistant to real-world systems and channels — ERPNext as a business
data source/sink, and WhatsApp/email as conversational surfaces — with inbound
webhooks and durable background processing so slow or external work never blocks a
request.

### Deliverables
- **ERPNext integration** — a port + adapter for reading/writing ERPNext data.
- **WhatsApp** — an inbound/outbound messaging channel adapter.
- **Email** — an email channel adapter (inbound parsing + outbound send).
- **Webhooks** — verified inbound webhook handling at the interface layer.
- **Background jobs** — a task/queue abstraction for asynchronous and scheduled work.

### Exit criteria
- A message arriving via WhatsApp/email is processed and answered end-to-end.
- An ERPNext read/write round-trips through the integration port.
- Long-running work runs as a background job; the request path stays responsive.
- Correlation IDs propagate across the job boundary (the M1 retrospective's flagged item).

### Risks
- *Correlation context does not survive spawned tasks/workers* (flagged in M1). **Mitigation:** define and test propagation guarantees as part of the job abstraction.
- *Third-party API reliability / rate limits.* **Mitigation:** reuse the `retryable` error signal; add a retry policy in the application layer.
- *Webhook security* (spoofing/replay). **Mitigation:** signature verification + idempotency keys.

### Dependencies
M2 (persistence for job state and channel sessions); M4 if channels invoke agents.

---

## Milestone 6 — Multi-tenancy & SaaS

**Status:** 🗓️ Planned.

### Goal
Turn the single-tenant platform into a multi-tenant SaaS: authenticated users,
role-based access control, organizations as tenancy boundaries, usage-based billing,
and the operational features a hosted product requires.

### Deliverables
- **Authentication** — login/session/token issuance behind an auth port.
- **Multi-user** — user identity attached to conversations and resources.
- **RBAC** — roles and permissions enforced at the application boundary.
- **Organizations** — tenant isolation; data scoped per organization.
- **Billing** — usage metering and a billing-provider integration.
- **SaaS features** — quotas, plans, and per-tenant configuration.

### Exit criteria
- All resource access is authenticated and authorized; cross-tenant access is impossible by construction and tested.
- Usage is metered per tenant and reconciles with billing.
- Tenant isolation is verified by test (no data leakage across organizations).
- The dependency rule and contract suites still pass under the new identity model.

### Risks
- *Tenant data leakage* — the highest-severity risk in the roadmap. **Mitigation:** isolation enforced at the repository/query layer with explicit tests; default-deny.
- *Auth complexity creep.* **Mitigation:** keep auth behind a port; start with one provider.
- *Retrofitting tenancy onto existing aggregates.* **Mitigation:** design the M2 aggregates with an owner/principal field already present (done in ADR-0005).

### Dependencies
M2 (identity on aggregates) and M5 (background jobs for billing/metering).

---

## Milestone 7 — Cloud providers & routing

**Status:** 🗓️ Planned.

### Goal
Prove the provider abstraction against structurally different cloud models and add
intelligent routing: support OpenAI, Claude, Gemini, and DeepSeek behind the same
`LLMProvider` port, then route requests across them for cost and capability
optimization.

### Deliverables
- **OpenAI** adapter (SSE streaming, tool calls).
- **Claude (Anthropic)** adapter.
- **Gemini** adapter.
- **DeepSeek** adapter.
- **Provider routing** — a policy that selects a provider per request (capability, latency, availability).
- **Cost optimization** — routing and model selection informed by token cost and budgets.

### Exit criteria
- Each cloud adapter passes the **same** provider contract suite as Echo and Ollama (SSE framing and tool calls normalized at the boundary).
- A routing policy selects providers by configurable rules and is unit-tested.
- Per-request cost is recorded; routing can demonstrably reduce cost on a fixed workload.
- No vendor SSE/tool-call shape leaks above `infrastructure`; the dependency rule holds.

### Risks
- *SSE framing, typed events, and tool calls strain the port* (the central open question from the M1 retrospective). **Mitigation:** add capabilities additively (flags + optional methods); consider contract versioning so providers advertise the revision they satisfy.
- *Credential/secret management across many providers.* **Mitigation:** all keys via `SecretStr` settings; never logged (already enforced in M1).
- *Routing complexity and unpredictable cost.* **Mitigation:** start with a simple, explicit policy; measure before optimizing.

### Dependencies
M1 (the port and contract suite). Ideally a thin cloud adapter is introduced earlier
(during M4) to de-risk tool-call framing before the full provider matrix lands.

---

## Cross-cutting, deferred by design

Recorded so they are not mistaken for oversights (see the
[M1 retrospective](docs/milestone-1-retrospective.md)):

- **RetryPolicy service** — consumes the existing `retryable` / `retry_after` error
  data (backoff, max attempts, idempotency). Application layer; arrives when a real
  retry need exists (M5/M7).
- **Observability depth** — request duration, first-token latency, token counts,
  per-category failure metrics via an enrichment/metrics middleware.
- **Machine-readable error codes** — stable identifiers for REST/metrics, deferred
  until an external API needs them.
- **Connection pooling / HTTP-2 tuning** — deferred until concurrent load exists.
- **Contract versioning** — decided ahead of capability growth (tools/vision/embeddings).
