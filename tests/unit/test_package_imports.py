"""Bootstrap smoke test (M1.0).

Verifies the approved package skeleton is installed and every layer's package is
importable. This is the Definition-of-Done evidence for the project-bootstrap
step: the structure exists and the package is wired into the environment before
any logic is added.
"""

from __future__ import annotations

import importlib

import pytest

import aiplatform

# Every package in the approved folder structure (file-dependency-matrix).
# Modules with logic are added in M1.1+; here we assert the skeleton only.
_EXPECTED_PACKAGES = [
    "aiplatform.domain",
    "aiplatform.domain.llm",
    "aiplatform.application",
    "aiplatform.application.llm",
    "aiplatform.infrastructure",
    "aiplatform.infrastructure.config",
    "aiplatform.infrastructure.logging",
    "aiplatform.infrastructure.llm",
    "aiplatform.infrastructure.llm.echo",
    "aiplatform.infrastructure.llm.ollama",
    "aiplatform.composition",
    "aiplatform.interface",
    "aiplatform.interface.http",
    "aiplatform.interface.http.routes",
    "aiplatform.interface.cli",
]


def test_root_package_exposes_version() -> None:
    """The distributable package declares a version string."""
    assert isinstance(aiplatform.__version__, str)
    assert aiplatform.__version__


@pytest.mark.parametrize("module_name", _EXPECTED_PACKAGES)
def test_layer_package_is_importable(module_name: str) -> None:
    """Each layer package in the approved structure imports cleanly."""
    module = importlib.import_module(module_name)
    assert module.__name__ == module_name
