# Engineering Documentation Index

Design history and engineering artifacts for the AI assistant platform. Read in
this order before implementing.

## Architecture Decision Records (`adr/`)

Milestone 1 (foundation):
- [ADR-0001: Clean Architecture in a Modular Monolith](adr/0001-clean-architecture.md)
- [ADR-0002: LLM Provider Abstraction](adr/0002-llm-provider-abstraction.md)
- [ADR-0003: Streaming-First Provider Design](adr/0003-streaming-first-provider-design.md)
- [ADR-0004: Echo Provider as Reference Implementation](adr/0004-echo-provider.md)
- [ADR-0005: Repository Strategy (In-Memory First)](adr/0005-repository-strategy.md)
- [ADR-0006: Logging/Correlation as a Cross-Cutting Kernel](adr/0006-logging-cross-cutting-kernel.md)

Milestone 2 (conversation & persistence):
- [ADR-0007: Conversation and Message Aggregates](adr/0007-conversation-message-aggregate.md)
- [ADR-0008: Persistence — Repository Contract, Transaction Boundary, and Relational Mapping](adr/0008-persistence-repository-and-transactions.md)
- [ADR-0009: Context-Window Selection and Prompt Assembly](adr/0009-context-window-and-prompt-assembly.md)
- [ADR-0010: Application Service Layer (Use-Case Orchestration)](adr/0010-application-service-layer.md)

Milestone 3 (knowledge retrieval / RAG) — **Accepted** (implementation begun, M3.0):
- [ADR-0011: Knowledge & Retrieval Architecture (RAG)](adr/0011-knowledge-and-retrieval-architecture.md)
- [ADR-0012: Embedding Provider Abstraction](adr/0012-embedding-provider-abstraction.md)
- [ADR-0013: Vector Store Abstraction](adr/0013-vector-store-abstraction.md)
- [ADR-0014: Chunking Strategy](adr/0014-chunking-strategy.md)
- [ADR-0015: Retrieval Strategy & Prompt Enrichment](adr/0015-retrieval-and-prompt-enrichment.md)
- [ADR-0016: Knowledge Metadata, Ingestion & Persistence](adr/0016-knowledge-metadata-ingestion-and-persistence.md)

## Milestone 1 — Project Skeleton + LLM Provider
- [Development Roadmap](roadmap/milestone-1.md) — sub-milestones, file order, exit criteria
- [File Dependency Matrix](file-dependency-matrix.md) — dependency graph + circular-risk analysis
- [Implementation Checklist](implementation-checklist.md) — sequential tasks for the engineer
- [Testing Strategy](testing-strategy.md) — unit / contract / integration / smoke per file
- [Git Strategy](git-strategy.md) — branching, commits, PR workflow

## Milestone 1 — closeout (M1.7)
- [Exit-Criteria Review](milestone-1-exit-review.md) — each §5 criterion mapped to evidence
- [Retrospective](milestone-1-retrospective.md) — what shipped, decisions, deferred items

## Milestone 2 — Conversation & Persistence
- [Development Roadmap](roadmap/milestone-2.md) — sub-milestones, file order, dependency graph, DoD, exit criteria, risks, trade-offs
- [Exit-Criteria Review](milestone-2-exit-review.md) — each §6 criterion mapped to evidence (M2.6)
- [Retrospective](milestone-2-retrospective.md) — objective, concepts, ADRs, decisions, lessons
- Governed by ADR-0007 (aggregate), ADR-0008 (persistence), ADR-0009 (memory/assembly), ADR-0010 (application-service layer).

## Milestone 3 — Knowledge Retrieval / RAG (in design)
- [Development Roadmap](roadmap/milestone-3.md) — scope, sub-milestones (M3.0–M3.8), file order, dependency graph, DoD, exit criteria, risks, trade-offs
- Governed by proposed ADR-0011 (knowledge/retrieval), 0012 (embeddings), 0013 (vector store), 0014 (chunking), 0015 (retrieval & enrichment), 0016 (metadata/ingestion).

## Status
Milestone 1 is **implemented and accepted** — all nine exit criteria met (see the
exit review). The codebase ships a vertically-sliced foundation: config/logging,
domain contracts, two providers behind one contract suite, composition wiring,
and HTTP + CLI delivery. Architecture remains ratified and unchanged; M1.7 added
only validation and documentation.

## How to use this package (implementation engineer)
1. Read all five ADRs, then the roadmap.
2. Implement strictly in the order of the Implementation Checklist (inner layers
   before outer; Echo before Ollama).
3. Honor the Dependency Rule — it is enforced in CI via `import-linter`.
4. A change is not done until its tests pass per the Testing Strategy.
