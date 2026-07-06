## What

<!-- One-paragraph summary of the change. -->

## Why

<!-- Link to the ADR / roadmap milestone / issue this addresses. -->

## How verified

- [ ] unit
- [ ] contract suite (Echo)
- [ ] integration (respx)
- [ ] dependency-rule check (`lint-imports`)
- [ ] manual (CLI probe / live Ollama, if applicable)

## Checklist

- [ ] Branched from latest `main`; small and focused.
- [ ] Commit messages follow Conventional Commits.
- [ ] `ruff check` + `ruff format --check` pass.
- [ ] `mypy src` passes.
- [ ] `lint-imports` passes (no dependency-rule violation).
- [ ] `pytest -m "not live"` passes; new logic is tested.
- [ ] New/changed `LLMProvider` implementations pass the contract suite.
- [ ] No secret or vendor exception leaks across a boundary.
- [ ] Docs / ADRs / CHANGELOG updated where behavior or decisions changed.

## Notes / trade-offs

<!-- Anything reviewers should know: deferred work, alternatives considered, risks. -->
