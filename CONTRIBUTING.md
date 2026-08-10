# Contributing

Thanks for your interest in contributing. This project is built with
production-grade discipline: the architecture's boundaries are enforced by a
machine, and contributions are expected to keep them intact. Please read this
guide and the relevant [ADRs](docs/adr/) before opening a pull request.

The authoritative branching/commit policy is [`docs/git-strategy.md`](docs/git-strategy.md);
this document is the contributor-facing summary.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating, you agree to uphold it.

## Development setup

Requirements: **Python 3.13**. For the live Ollama path, a running
[Ollama](https://ollama.com/) instance.

```bash
git clone https://github.com/kishorhari/ai-chatbot.git
cd ai-chatbot

python -m venv venv
source venv/bin/activate          # bash/zsh
# venv\Scripts\Activate.ps1        # Windows PowerShell

pip install -e ".[dev]"
cp .env.example .env               # then edit as needed
```

## Branch strategy

Trunk-based development with short-lived feature branches:

- **`main`** is always releasable and protected. No direct pushes.
- Each task gets a short-lived branch off `main`, merged within ~1–2 days via PR.
- Branches are deleted after merge.

**Branch naming:** `<type>/<scope>-<short-description>`

```
feat/llm-provider-port
feat/ollama-adapter
chore/ci-import-linter
docs/adr-streaming
test/provider-contract-suite
```

`type` ∈ `{feat, fix, refactor, test, docs, chore, ci, build, perf}`.

## Conventional Commits

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body — what & why, not how>

<footer — BREAKING CHANGE / refs>
```

- **type** ∈ `feat, fix, docs, refactor, test, chore, ci, build, perf`.
- **scope** = the module touched, e.g. `domain`, `ollama`, `config`, `logging`,
  `composition`, `http`, `cli`.
- **subject**: imperative mood, ≤ 72 chars, no trailing period.

Examples:

```
feat(domain): add LLMProvider port and value objects
feat(ollama): map transport failures to LLMError taxonomy
test(contract): add shared provider contract suite
chore(ci): enforce dependency rule with import-linter
```

This keeps history machine-readable and enables automated changelogs / semver.
Update [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]` for any user-visible
change.

## Coding standards

- **Honor the Dependency Rule.** Source dependencies point inward only; it is
  enforced by `import-linter` and a violation is a build failure. If you need a new
  cross-layer dependency, it is almost certainly a design discussion (and possibly
  a new ADR), not a quick import.
- **Ports in the inside, adapters on the outside.** Introduce a port only where a
  real second implementation is foreseeable. No vendor SDK or `httpx` import above
  the `infrastructure` layer.
- **No transport-native exception escapes an adapter.** Map failures to the domain
  `LLMError` taxonomy with the correct `retryable` disposition.
- **Type everything.** `mypy` runs in CI and is strict on `domain`/`application`
  (no untyped defs, no implicit `Any`).
- **Style is automated.** `ruff` handles lint + format (line length 100, Google
  docstring convention). Public modules/classes/functions in `src/` carry
  docstrings; tests are exempt.
- **Configuration is read only through `Settings`** — never `os.environ` scattered
  across the code. Secrets are `SecretStr` and must never be logged.
- **Record significant decisions as ADRs.** If a change alters a boundary, a
  contract, or a documented trade-off, add or amend an ADR under `docs/adr/`.

## Testing requirements

Tests follow the [testing strategy](docs/testing-strategy.md):

- **A change is not done until its tests pass.** Add unit tests for new module
  logic; if you add or change an `LLMProvider` implementation, it **must** pass the
  shared contract suite in `tests/contract/provider_contract.py`.
- `domain` and `application` are pure and cheap to test — keep them at high
  coverage (target ≥ 95%; currently 100%). Don't chase coverage on thin transport
  glue, but do cover every error-mapping and streaming/cancellation branch.
- Live Ollama tests are opt-in (`-m live`) and excluded from required CI; never make
  CI depend on external infrastructure.

Run the full local gate set before pushing — the same four checks CI runs:

```bash
ruff check . && ruff format --check .     # lint + format
mypy src                                  # type-check
lint-imports                              # dependency-rule contracts
pytest -m "not live" --cov=aiplatform     # unit + contract + respx integration
```

## Pull request workflow

1. Branch from the latest `main`.
2. Implement one focused task; keep the PR small.
3. Open a PR using the [template](.github/PULL_REQUEST_TEMPLATE.md).
4. Ensure **all four CI gates pass** (lint, type-check, dependency rule, tests).
5. Self-review against the relevant ADRs.
6. PRs are **squash-merged** into `main` (one clean commit per task → linear history).
7. The branch is deleted after merge.

### PR checklist

- [ ] Branched from latest `main`; small and focused.
- [ ] Commit messages follow Conventional Commits.
- [ ] `ruff check` and `ruff format --check` pass.
- [ ] `mypy src` passes.
- [ ] `lint-imports` passes (no dependency-rule violation).
- [ ] `pytest -m "not live"` passes; new logic is tested.
- [ ] New/changed `LLMProvider` implementations pass the contract suite.
- [ ] No secret, credential, or vendor exception leaks across a boundary.
- [ ] Docs/ADRs/CHANGELOG updated where behavior or decisions changed.

## Reporting bugs & requesting features

Use the [issue templates](https://github.com/kishorhari/ai-chatbot/issues/new/choose).
For anything security-sensitive, follow [SECURITY.md](SECURITY.md) instead of
opening a public issue.
