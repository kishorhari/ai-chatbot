# Git Strategy

## Context

The project is currently **not** a git repository. Step zero for the
implementation engineer is `git init` and an initial commit of the documentation
and project skeleton. The team is small (effectively solo + AI pairing) and the
goal is learning with production-grade discipline. The strategy below favors
**simplicity and a fast feedback loop** over heavyweight release management.

## Branching model — Trunk-Based with short-lived feature branches

- **`main`** is always releasable and protected. No direct pushes.
- Each task (roughly one Implementation Checklist item or sub-milestone) gets a
  **short-lived branch** off `main`, merged within ~1–2 days via PR.
- Branches are deleted after merge.

**Rejected: Git Flow.** Its `develop` + `release` + `hotfix` branch ceremony is
designed for scheduled, versioned releases by larger teams. It would be pure
overhead at this stage — the same overengineering we avoid in the architecture.

### Branch naming

```
<type>/<scope>-<short-description>
```
Examples: `feat/llm-provider-port`, `feat/ollama-adapter`,
`chore/ci-import-linter`, `docs/adr-streaming`, `test/provider-contract-suite`.

`type` ∈ {feat, fix, refactor, test, docs, chore, ci, build}.

## Commit conventions — Conventional Commits

```
<type>(<scope>): <subject>

<body — what & why, not how>

<footer — BREAKING CHANGE / refs>
```

- **type** ∈ feat, fix, docs, refactor, test, chore, ci, build, perf.
- **scope** = the module touched, e.g. `domain`, `ollama`, `config`, `logging`,
  `composition`, `http`, `cli`.
- Subject: imperative mood, ≤ 72 chars, no trailing period.
- Examples:
  - `feat(domain): add LLMProvider port and value objects`
  - `feat(ollama): map transport failures to LLMError taxonomy`
  - `test(contract): add shared provider contract suite`
  - `chore(ci): enforce dependency rule with import-linter`

Conventional Commits keep history machine-readable and enable automated
changelogs / semver later if needed.

## Pull Request workflow

1. Branch from latest `main`.
2. Implement one checklist item / sub-milestone; keep the PR small and focused.
3. Open a PR using the template below.
4. **CI gates must pass** before merge: `ruff` (lint+format), `mypy`,
   `import-linter` (dependency rule), `pytest` (unit + contract + respx
   integration). Live Ollama tests are opt-in and not required for merge.
5. Self-review against the relevant ADRs and the Implementation Checklist DoD.
6. **Squash-merge** into `main` (one clean commit per task → linear history).
7. Delete the branch.

### PR description template

```
## What
<one-paragraph summary>

## Why
<link to ADR / roadmap sub-milestone / checklist item>

## How verified
- [ ] unit
- [ ] contract suite (Echo)
- [ ] integration (respx)
- [ ] dependency-rule check
- [ ] manual (CLI probe / live Ollama, if applicable)

## Notes / trade-offs
```

## Tagging & milestones

- Tag the Milestone 1 exit as **`v0.1.0-m1`** once all roadmap §5 exit criteria pass.
- One tag per completed milestone going forward (`v0.2.0-m2`, …).

## Repository hygiene

- `.gitignore` excludes `venv/`, `.env`, `__pycache__/`, `.pytest_cache/`,
  `.mypy_cache/`, `.ruff_cache/`, build artifacts.
- `.env.example` is committed; `.env` never is.
- `main` branch protection: require PR + green CI; no force-push.
- Commit the docs (`docs/`) and skeleton in the initial commit so history starts
  from the ratified design.
