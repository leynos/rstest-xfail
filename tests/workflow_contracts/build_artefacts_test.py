"""Contract that ``make build`` and ``make release`` still rebuild the facade.

The Makefile names the facade's artefact explicitly, because Cargo's
hyphen-to-underscore mapping is not obvious, and routes both targets through
one pattern rule whose only prerequisite is ``FORCE``. Cargo owns the
freshness decision, so that rule must never be satisfied by a file. A
``FORCE`` that stops being phony, or an artefact name that loses its
underscore, silently stops the build happening or builds the wrong library.

The recipes are exercised rather than described: ``make`` runs against a
scratch copy of the Makefile with a fake ``cargo`` on ``PATH``, so a
regression fails here instead of being re-read here.

Run via ``make test-workflow-contracts``.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
FACADE_MANIFEST = ROOT / "crates" / "rstest-xfail" / "Cargo.toml"
#: The prerequisite that hands the freshness decision to Cargo.
FORCE = "FORCE"

FAKE_CARGO = """\
#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$FAKE_CARGO_LOG"
"""


def _facade_artefact() -> str:
    """Return the artefact Cargo builds for the facade's library target.

    Derived from the manifest rather than hard-coded, so renaming the crate
    reports the ``TARGET`` line that needs the matching update.
    """
    manifest = tomllib.loads(FACADE_MANIFEST.read_text("utf-8"))
    name = manifest["package"]["name"]
    return f"lib{name.replace('-', '_')}.rlib"


def _prerequisites(database: str, goal: str) -> list[str]:
    """Return the prerequisites ``make`` recorded for one target."""
    found = re.search(rf"^{re.escape(goal)}:\s*(.*)$", database, re.MULTILINE)
    assert found is not None, f"the Makefile declares no rule for {goal!r}"
    return found.group(1).split()


def _database(*goals: str) -> str:
    """Return ``make``'s rule database for goals, running no recipe."""
    result = subprocess.run(
        ["make", "-p", "-n", "CARGO=/bin/true", *goals],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _invocations(tmp_path: Path, *goals: str) -> list[str]:
    """Run goals against a scratch Makefile and return the calls to cargo.

    The scratch directory pre-creates the artefact and an *older* file named
    ``FORCE``, which is the arrangement that catches a prerequisite Make can
    satisfy from the filesystem.
    """
    fake_cargo = tmp_path / "fake-cargo"
    fake_cargo.write_text(FAKE_CARGO, encoding="utf-8")
    fake_cargo.chmod(0o755)
    (tmp_path / "Makefile").write_text(MAKEFILE.read_text("utf-8"), encoding="utf-8")

    artefact = tmp_path / "target" / "debug" / _facade_artefact()
    artefact.parent.mkdir(parents=True)
    artefact.touch()
    stale_force = tmp_path / FORCE
    stale_force.touch()

    # Explicit times beat sleeping: the artefact must be the newer file, or
    # Make would rebuild for the ordinary timestamp reason and prove nothing.
    now = time.time()
    os.utime(stale_force, (now - 60, now - 60))
    os.utime(artefact, (now, now))

    log = tmp_path / "cargo.log"
    subprocess.run(
        ["make", *goals, f"CARGO={fake_cargo}"],
        cwd=tmp_path,
        env={**os.environ, "FAKE_CARGO_LOG": str(log)},
        capture_output=True,
        text=True,
        check=True,
    )
    return log.read_text("utf-8").splitlines() if log.exists() else []


@pytest.mark.parametrize(
    ("goal", "profile"), [("build", "debug"), ("release", "release")]
)
def test_build_goals_name_the_underscored_artefact(goal: str, profile: str) -> None:
    """A hyphen kept in the artefact name leaves Cargo nothing to build."""
    expected = f"target/{profile}/{_facade_artefact()}"
    assert _prerequisites(_database(goal), goal) == [expected]


@pytest.mark.parametrize("profile", ["debug", "release"])
def test_the_artefact_rule_is_forced(profile: str) -> None:
    """Cargo owns freshness, so the rule must never be satisfied by a file."""
    artefact = f"target/{profile}/{_facade_artefact()}"
    assert _prerequisites(_database(artefact), artefact) == [FORCE]


def test_a_stale_force_file_cannot_suppress_a_rebuild(tmp_path: Path) -> None:
    """An older ``FORCE`` file must not satisfy the prerequisite.

    Without ``.PHONY: FORCE``, Make compares that file's timestamp with the
    artefact's. A stray file named ``FORCE`` that is older than an existing
    artefact makes the target look up to date, and the recipe never runs.
    """
    invocations = _invocations(tmp_path, "build")
    assert any(call.split()[:1] == ["build"] for call in invocations), (
        f"a stale FORCE file suppressed the rebuild; cargo was called with {invocations}"
    )


@pytest.mark.parametrize(
    ("goal", "expected"), [("build", "build"), ("release", "build --release")]
)
def test_the_recipes_invoke_cargo_build(
    tmp_path: Path, goal: str, expected: str
) -> None:
    """The profile flag reaches Cargo, so each goal builds the profile it names."""
    invocations = [call.split() for call in _invocations(tmp_path, goal)]
    assert expected.split() in invocations, (
        f"`make {goal}` did not run `cargo {expected}`; it ran {invocations}"
    )
