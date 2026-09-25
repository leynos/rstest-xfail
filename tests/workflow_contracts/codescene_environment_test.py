"""Prove the ``codescene`` environment sits on the uploading job alone.

Each test mutates a copy of this repository's workflows the way a later edit
could, and asserts the clause meant to catch it does. The check step, the ref
guard and ``access-token:`` stay held by the CV-005 coverage contract.

Run via ``make test-workflow-contracts``.
"""

from __future__ import annotations

import copy
import typing as typ

import codescene_environment as environment
import codescene_reading as reading
import pytest

PUBLISHER = "coverage-main.yml"
LANE = "ci.yml"


@pytest.fixture
def every() -> dict[str, reading.Workflow]:
    """Return a private copy of the repository's workflows to mutate."""
    return copy.deepcopy(reading.workflows(reading.WORKFLOW_DIR))


def _first_job(every: dict[str, reading.Workflow], name: str) -> dict[typ.Any, typ.Any]:
    """Return one workflow's first job, for mutation in place."""
    return reading.jobs(every[name])[0][1]


def _reports(every: dict[str, reading.Workflow], fragment: str) -> None:
    """Fail unless the rule reports a violation containing ``fragment``."""
    found = environment.environment_violations(every)
    assert any(fragment in problem for problem in found), (
        f"expected a violation naming {fragment!r}, got {found}"
    )


def test_repository_places_the_environment(every: dict[str, reading.Workflow]) -> None:
    """The publisher declares the environment and nothing else does."""
    found = environment.environment_violations(every)
    assert not found, f"expected no violations, got {found}"


def test_publisher_cannot_drop_the_environment(
    every: dict[str, reading.Workflow],
) -> None:
    """Without it the moved token never reaches the upload, which then skips."""
    del _first_job(every, PUBLISHER)["environment"]
    _reports(every, environment.MISSING)


def test_publisher_cannot_name_another_environment(
    every: dict[str, reading.Workflow],
) -> None:
    """Another environment holds no CodeScene token."""
    _first_job(every, PUBLISHER)["environment"] = "production"
    _reports(every, environment.MISSING)


def test_mapping_form_is_accepted(every: dict[str, reading.Workflow]) -> None:
    """``{name: codescene}`` is the same declaration as the bare string."""
    _first_job(every, PUBLISHER)["environment"] = {"name": "codescene"}
    found = environment.environment_violations(every)
    assert not found, f"the mapping form must be accepted, got {found}"


def test_no_other_job_may_declare_it(every: dict[str, reading.Workflow]) -> None:
    """A second holder of the token widens what can read it."""
    every[PUBLISHER]["jobs"]["other"] = {
        "runs-on": "ubuntu-latest",
        "environment": "codescene",
        "steps": [{"run": "true"}],
    }
    _reports(every, environment.STRAY)


def test_no_pull_request_job_may_declare_it(every: dict[str, reading.Workflow]) -> None:
    """A pull request's own code must never be able to request the token."""
    _first_job(every, LANE)["environment"] = {"name": "codescene"}
    _reports(every, environment.REACHABLE)


def test_an_empty_reading_is_refused(every: dict[str, reading.Workflow]) -> None:
    """With no uploader left the rule says so rather than passing."""
    job = _first_job(every, PUBLISHER)
    job["steps"] = [
        step for step in job["steps"] if environment.UPLOAD_ACTION not in str(step)
    ]
    _reports(every, "no workflow job invokes")
