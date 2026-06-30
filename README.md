# AI Platform

An enterprise-grade AI assistant platform built on **Clean Architecture** in a
modular monolith. The LLM provider and (later) storage backend are isolated
behind ports so they can be swapped by configuration, not rewrites.

> Milestone 1 status: **project skeleton + provider abstraction**. See
> [`docs/`](docs/README.md) for the ratified architecture package (ADRs,
> roadmap, dependency matrix, testing strategy).

## Architecture at a glance

Source dependencies point **inward only** (the Dependency Rule, ADR-0001),
enforced mechanically by `import-linter` in CI:

```
domain  <  application  <  { infrastructure, interface }  <  composition (root)
```

- **domain** — pure value objects, ports, errors. No framework, I/O, or logging.
- **application** — use cases; depends only on domain ports.
- **infrastructure** — adapters implementing ports (LLM providers, config, logging).
- **interface** — delivery surfaces (FastAPI HTTP, CLI probe).
- **composition** — the only place permitted to wire concretes to ports.

## Requirements

- Python **3.13**

## Setup

```bash
python -m venv venv
# Windows PowerShell
venv\Scripts\Activate.ps1
# bash
source venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env   # then edit as needed
```

## Quality gates (run locally; enforced in CI)

```bash
ruff check . && ruff format --check .          # lint + format
mypy src                                        # type-check (strict on domain/application)
lint-imports                                    # dependency-rule contracts
pytest -m "not live"                            # unit + contract + integration (respx)
pytest -m "not live" --cov=aiplatform           # with coverage
pytest -m live                                  # opt-in: requires a running Ollama
```

## Project layout

```
src/aiplatform/
  domain/llm/          value objects, LLMProvider port, error taxonomy
  application/llm/      provider registry port
  infrastructure/
    config/             settings (fail-fast)
    logging/            structured logging + correlation id
    llm/echo/           reference provider (no network)
    llm/ollama/         Ollama adapter
  composition/          composition root (wiring)
  interface/
    http/               FastAPI app + health routes
    cli/                dev probe
tests/                  unit / contract / integration
docs/                   ADRs, roadmap, dependency matrix, testing strategy
```
