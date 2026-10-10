"""Contract tests for how the workflows provision clang, lld and mold.

``.cargo/config.toml`` links Linux builds with clang and mold, and coverage
links with lld, so the runner needs all three before any cargo command runs.
The CI and coverage-main workflows get them from ``setup-rust``'s
``install-mold`` and ``install-clang-lld`` inputs, and the mutation-testing
caller forwards the same inputs to ``mutation-cargo.yml``. A step that lost an
input, set it to anything but the string ``'true'`` (``setup-rust`` rejects
other values), or went back to a hand-rolled ``apt-get`` line would otherwise
surface only as a failed link on a runner.

Run via ``make test-workflow-contracts``.
"""

from __future__ import annotations

import re
import typing as typ
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
SETUP_RUST = re.compile(
    r"^leynos/shared-actions/\.github/actions/setup-rust@[0-9a-f]{40}$"
)
LINKER_INPUTS: dict[str, str] = {"install-mold": "true", "install-clang-lld": "true"}
PROVISIONING_WORKFLOWS = ["ci.yml", "coverage-main.yml"]
HAND_INSTALL = re.compile(r"apt-get\s+install[^\n]*\b(clang|lld|mold)\b")

pytestmark = pytest.mark.skipif(
    not WORKFLOWS.exists(),
    reason="workflow files not present in this working copy",
)


def _steps(workflow: str) -> list[dict[str, typ.Any]]:
    """Return every step of every job in *workflow*."""
    document = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))
    return [step for job in document["jobs"].values() for step in job.get("steps", [])]


def _setup_rust_steps(workflow: str) -> list[dict[str, typ.Any]]:
    """Return the ``setup-rust`` steps of *workflow*."""
    return [
        step
        for step in _steps(workflow)
        if SETUP_RUST.fullmatch(str(step.get("uses", "")))
    ]


@pytest.mark.parametrize("workflow", PROVISIONING_WORKFLOWS)
def test_setup_rust_installs_the_linkers(workflow: str) -> None:
    """Every ``setup-rust`` step installs mold, clang and lld, pinned by SHA."""
    steps = _setup_rust_steps(workflow)

    assert steps, f"{workflow} must run setup-rust pinned to a full commit SHA"
    for step in steps:
        inputs = step.get("with") or {}
        for name, expected in LINKER_INPUTS.items():
            assert inputs.get(name) == expected, (
                f"{workflow}: setup-rust must set {name}: '{expected}', "
                f"got {inputs.get(name)!r}"
            )


@pytest.mark.parametrize("workflow", PROVISIONING_WORKFLOWS)
def test_no_step_installs_the_linkers_by_hand(workflow: str) -> None:
    """No run step apt-installs clang, lld or mold alongside ``setup-rust``."""
    offenders = [
        str(step.get("name", step))
        for step in _steps(workflow)
        if HAND_INSTALL.search(str(step.get("run", "")))
    ]

    assert not offenders, f"{workflow} installs linkers by hand in {offenders!r}"
