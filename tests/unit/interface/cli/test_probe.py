"""End-to-end test of the CLI probe streaming against Echo (M1.6).

Validates that the probe boots the composition root, resolves the default
provider, and streams a prompt to completion — the offline smoke path from the
testing strategy (CLI probe streams via Echo).
"""

from __future__ import annotations

from typing import Any

import pytest

from aiplatform.interface.cli.probe import main


@pytest.fixture(autouse=True)
def _echo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP__ENV", "local")
    monkeypatch.setenv("AIP__LLM__DEFAULT_PROVIDER", "echo")
    monkeypatch.setenv("AIP__LOGGING__LEVEL", "ERROR")


@pytest.fixture(autouse=True)
def _reset_structlog() -> Any:
    import structlog

    yield
    structlog.reset_defaults()


def test_probe_streams_prompt_via_echo(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["hello", "world"])
    assert exit_code == 0
    assert "hello world" in capsys.readouterr().out


def test_probe_uses_default_prompt_when_no_args(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    assert exit_code == 0
    # Echo streams back the default prompt verbatim.
    assert "CLI probe" in capsys.readouterr().out
