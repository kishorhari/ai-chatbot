"""End-to-end test of the knowledge CLI (ingest + query) against the offline path (M3.6)."""

from __future__ import annotations

from typing import Any

import pytest

from aiplatform.interface.cli.ingest import main


@pytest.fixture(autouse=True)
def _reset_structlog() -> Any:
    import structlog

    yield
    structlog.reset_defaults()


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__ENV", "local")
    monkeypatch.setenv("AIP__LLM__DEFAULT_PROVIDER", "echo")
    monkeypatch.setenv("AIP__LOGGING__LEVEL", "ERROR")
    monkeypatch.setenv("AIP__KNOWLEDGE__ENABLED", "true")
    monkeypatch.setenv("AIP__KNOWLEDGE__EMBEDDING__BACKEND", "fake")
    monkeypatch.setenv("AIP__KNOWLEDGE__VECTOR__BACKEND", "memory")


def test_ingest_then_query_prints_relevant_chunk(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _enable(monkeypatch)
    exit_code = main(["faq.md", "The capital of France is Paris.", "capital of France"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "indexed" in out
    assert "Paris" in out


def test_disabled_reports_and_exits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AIP__ENV", "local")
    monkeypatch.setenv("AIP__LLM__DEFAULT_PROVIDER", "echo")
    monkeypatch.setenv("AIP__LOGGING__LEVEL", "ERROR")
    # knowledge disabled (default)
    exit_code = main(["faq.md", "text", "query"])
    assert exit_code == 2
    assert "disabled" in capsys.readouterr().err


def test_wrong_arity_is_misuse(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["only-one-arg"]) == 2
    assert "usage" in capsys.readouterr().err
