"""End-to-end test of the CLI chat against Echo (M2.4)."""

from __future__ import annotations

import io
from typing import Any

import pytest

from aiplatform.interface.cli.chat import main


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__ENV", "local")
    monkeypatch.setenv("AIP__LLM__DEFAULT_PROVIDER", "echo")
    monkeypatch.setenv("AIP__LOGGING__LEVEL", "ERROR")


@pytest.fixture(autouse=True)
def _reset_structlog() -> Any:
    import structlog

    yield
    structlog.reset_defaults()


def test_chat_runs_each_turn_via_echo(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["hello", "second turn"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "hello" in out
    assert "second turn" in out
    assert "conversation" in out  # the conversation id line was printed


def test_chat_with_no_turns_returns_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert main([]) == 2
