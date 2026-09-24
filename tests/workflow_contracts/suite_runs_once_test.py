"""Contract that each pull request runs the Rust test suite once.

`make test` runs the suite with ``--all-targets --all-features`` and then the
doctests. The coverage step in ``ci.yml``'s ``build-test`` job runs the same
tests, since the crate declares no features and has no examples or benches,
but not the doctests, which ``build-test`` runs in a step of its own. The
repository used to carry an ``act-validation.yml`` workflow running
``make test WITH_ACT=1``; nothing reads ``WITH_ACT`` and no test is gated on
Act, so it ran the whole suite a second time and was removed.

These tests hold the split:

- no step in any workflow or local composite action runs the suite, in any
  spelling ``suite_commands`` recognizes, except the one doctest step;
- that doctest step is in ``build-test``, carries the flags ``make test``
  gives its doctest line, and neither the job nor the step has an ``if:``;
- ``build-test`` runs the coverage action in one unguarded step, with its
  doctests left off;
- the crate declares no feature, in ``[features]`` or through an optional
  dependency, which is what makes ``--all-features`` the coverage default.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import yaml
from suite_commands import runs_suite

ROOT = Path(__file__).resolve().parents[2]
GITHUB = ROOT / ".github"
DOCTEST_COMMAND = "cargo test --doc --workspace --all-features"
#: The Makefile's RUST_FLAGS, which `make test` gives its doctest line.
DOCTEST_ENV = {"RUSTFLAGS": "-D warnings"}
COVERAGE_ACTION = "leynos/shared-actions/.github/actions/generate-coverage@"
SUITE_JOB = ("workflows/ci.yml", "build-test")
DEPENDENCY_TABLES = ("dependencies", "dev-dependencies", "build-dependencies")


def _documents() -> dict[str, dict]:
    """Parse every workflow and local composite action, by relative path."""
    paths = [*GITHUB.glob("workflows/*.y*ml"), *GITHUB.glob("actions/**/action.y*ml")]
    return {
        str(path.relative_to(GITHUB)): yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(paths)
    }


def _document_steps(where: str, document: dict) -> list[tuple[tuple[str, str], dict]]:
    """Return one document's steps, labelled by job (``runs`` for an action)."""
    runs = document.get("runs")
    action_steps = (runs.get("steps") or []) if isinstance(runs, dict) else []
    found = [((where, "runs"), step) for step in action_steps]
    for name, job in (document.get("jobs") or {}).items():
        found.extend(((where, name), step) for step in job.get("steps") or [])
    return found


def _steps() -> list[tuple[tuple[str, str], dict]]:
    """Return every step, labelled by document and job (``runs`` for actions)."""
    return [
        labelled
        for where, document in _documents().items()
        for labelled in _document_steps(where, document)
    ]


def _suite_job() -> dict:
    """Return ``ci.yml``'s ``build-test`` job, refusing a conditional one."""
    workflow, name = SUITE_JOB
    job = (_documents()[workflow].get("jobs") or {}).get(name)
    assert job is not None, "ci.yml must define build-test"
    assert "if" not in job, "build-test must run on every pull request"
    return job


def _dependency_tables(manifest: dict) -> list[dict]:
    """Return a manifest's dependency tables, platform-specific ones included."""
    scopes = [manifest, *(manifest.get("target") or {}).values()]
    return [scope.get(name) or {} for scope in scopes for name in DEPENDENCY_TABLES]


def _optional_dependencies(manifest: dict) -> list[str]:
    """Return the names of a manifest's optional dependencies."""
    return [
        name
        for table in _dependency_tables(manifest)
        for name, spec in table.items()
        if isinstance(spec, dict) and spec.get("optional") is True
    ]


def _features(manifest: dict) -> list[str]:
    """Return a manifest's features, implicit ones from optional dependencies included.

    An optional dependency named anywhere as ``dep:<name>`` exposes no implicit
    feature, as Cargo documents, so it is left out.
    """
    features = dict(manifest.get("features") or {})
    values = [value for listed in features.values() for value in listed]
    suppressed = {
        value.removeprefix("dep:") for value in values if value.startswith("dep:")
    }
    implicit = [
        name for name in _optional_dependencies(manifest) if name not in suppressed
    ]
    return [*features, *implicit]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("make test", True),
        ("make test WITH_ACT=1", True),
        ("make -j2 test", True),
        ("make -C . test", True),
        ("make all", True),
        ("make", True),
        ("make coverage", True),
        ("make dev-test", True),
        ('make "test"', True),
        ("make lint&&make test", True),
        ("cargo test --all-features", True),
        ("cargo --config tools/dev-fast/config.toml test", True),
        ("cargo +nightly test", True),
        ("cargo nextest run --all-targets", True),
        ("cargo llvm-cov nextest --lcov", True),
        ("RUSTFLAGS='-D warnings' cargo test", True),
        ("make test-workflow-contracts", False),
        ("make lint", False),
        ("cargo build --all-targets", False),
        ("cargo run -- test", False),
        ("echo cargo test", False),
    ],
)
def test_the_suite_pattern(command: str, *, expected: bool) -> None:
    """Recognize every spelling of a suite run, and nothing longer."""
    assert runs_suite(command) is expected, command


def test_only_the_doctest_step_runs_the_suite_outside_coverage() -> None:
    """Refuse any suite run but one doctest run in ``build-test``."""
    runs = [
        (where, str(step.get("run", "")).strip())
        for where, step in _steps()
        if runs_suite(str(step.get("run", "")))
    ]
    doctests = [run for run in runs if run == (SUITE_JOB, DOCTEST_COMMAND)]
    repeated = [run for run in runs if run != (SUITE_JOB, DOCTEST_COMMAND)]
    assert not repeated, f"the suite runs outside coverage in {repeated!r}"
    assert len(doctests) == 1, "the doctests must run once, in build-test"


def test_build_test_runs_the_doctests_on_every_event() -> None:
    """Require one unconditional doctest step carrying `make test`'s flags."""
    steps = [
        step
        for step in _suite_job().get("steps") or []
        if str(step.get("run", "")).strip() == DOCTEST_COMMAND
    ]
    assert len(steps) == 1, "build-test must run the doctests once"
    assert "if" not in steps[0], "the doctest step must run on every event"
    assert steps[0].get("env") == DOCTEST_ENV, "the doctest step's flags drifted"


def test_build_test_runs_coverage_on_every_event() -> None:
    """Require one unconditional coverage step, with its doctests off."""
    steps = [
        step
        for step in _suite_job().get("steps") or []
        if str(step.get("uses", "")).startswith(COVERAGE_ACTION)
    ]
    assert len(steps) == 1, "build-test must run the coverage action once"
    assert "if" not in steps[0], "the coverage step must run on every event"
    doctests = str((steps[0].get("with") or {}).get("doctests", "false"))
    assert doctests.lower() == "false", "coverage would repeat the doctest step"


def test_the_crate_declares_no_features() -> None:
    """Refuse a feature, which would split ``--all-features`` from the default."""
    manifest = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))
    assert _features(manifest) == [], "recheck make test against the coverage run"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('[package]\nname = "x"\n', []),
        ("[features] # flags\nextra = []\n", ["extra"]),
        ('[dependencies]\nserde = { version = "1", optional\t=\ttrue }\n', ["serde"]),
        (
            (
                "[target.'cfg(unix)'.dependencies]\n"
                'libc = { version = "1", optional = true }\n'
            ),
            ["libc"],
        ),
        (
            (
                '[features]\nextra = ["dep:serde"]\n\n'
                '[dependencies]\nserde = { version = "1", optional = true }\n'
            ),
            ["extra"],
        ),
        ('[dependencies]\nserde = { version = "1" }\n', []),
    ],
)
def test_manifest_features_are_read(text: str, expected: list[str]) -> None:
    """Count declared features and optional dependencies, less ``dep:`` ones."""
    assert _features(tomllib.loads(text)) == expected
