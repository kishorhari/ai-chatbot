# Engineering Documentation Index

Design history and engineering artifacts for the AI assistant platform. Read in
this order before implementing.

## Architecture Decision Records (`adr/`)
- [ADR-0001: Clean Architecture in a Modular Monolith](adr/0001-clean-architecture.md)
- [ADR-0002: LLM Provider Abstraction](adr/0002-llm-provider-abstraction.md)
- [ADR-0003: Streaming-First Provider Design](adr/0003-streaming-first-provider-design.md)
- [ADR-0004: Echo Provider as Reference Implementation](adr/0004-echo-provider.md)
- [ADR-0005: Repository Strategy (In-Memory First)](adr/0005-repository-strategy.md)
- [ADR-0006: Logging/Correlation as a Cross-Cutting Kernel](adr/0006-logging-cross-cutting-kernel.md)

## Milestone 1 — Project Skeleton + LLM Provider
- [Development Roadmap](roadmap/milestone-1.md) — sub-milestones, file order, exit criteria
- [File Dependency Matrix](file-dependency-matrix.md) — dependency graph + circular-risk analysis
- [Implementation Checklist](implementation-checklist.md) — sequential tasks for the engineer
- [Testing Strategy](testing-strategy.md) — unit / contract / integration / smoke per file
- [Git Strategy](git-strategy.md) — branching, commits, PR workflow

## Milestone 1 — closeout (M1.7)
- [Exit-Criteria Review](milestone-1-exit-review.md) — each §5 criterion mapped to evidence
- [Retrospective](milestone-1-retrospective.md) — what shipped, decisions, deferred items

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
