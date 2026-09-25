"""Hold the CodeScene token's environment to the uploading job (CV-005).

The token lives in the ``codescene`` environment, whose deployment policy
admits ``main`` alone. So every job that invokes the uploader declares that
environment, no other job does, and no workflow a pull request can reach
declares it in any job: a declaration there would let branch code ask for the
token.
"""

from __future__ import annotations

import typing as typ

import codescene_reading as reading

ENVIRONMENT: typ.Final[str] = "codescene"
UPLOAD_ACTION: typ.Final[str] = "upload-codescene-coverage"
MISSING: typ.Final[str] = f"the uploading job must declare `environment: {ENVIRONMENT}`"
STRAY: typ.Final[str] = f"declares `{ENVIRONMENT}` but uploads nothing"
REACHABLE: typ.Final[str] = (
    f"is reachable from a pull request and declares `{ENVIRONMENT}`"
)


def environment_name(job: dict[typ.Any, typ.Any]) -> str | None:
    """Return the environment a job declares, from either accepted form.

    >>> environment_name({"environment": "codescene"})
    'codescene'
    >>> environment_name({"environment": {"name": "codescene", "url": "x"}})
    'codescene'
    >>> environment_name({}) is None
    True
    """
    match job.get("environment"):
        case str() as name:
            return name
        case {"name": str() as name}:
            return name
        case _:
            return None


def uploads(job: dict[typ.Any, typ.Any]) -> bool:
    """Return whether a job has a step invoking the uploader."""
    return any(UPLOAD_ACTION in reading.uses(step) for step in reading.job_steps(job))


def _placed(
    every: dict[str, reading.Workflow], names: typ.Iterable[str]
) -> list[tuple[str, dict[typ.Any, typ.Any]]]:
    """Return ``("workflow:job", job)`` for every job in the named workflows."""
    return [
        (f"{name}:{job_id}", job)
        for name in sorted(names)
        for job_id, job in reading.jobs(every[name])
    ]


def environment_violations(every: dict[str, reading.Workflow]) -> list[str]:
    """Report every departure from the ``codescene`` environment placement."""
    placed = _placed(every, every)
    uploading = [(where, job) for where, job in placed if uploads(job)]
    if not uploading:
        return ["no workflow job invokes the CodeScene uploader"]
    problems = [
        f"{where}: {MISSING}"
        for where, job in uploading
        if environment_name(job) != ENVIRONMENT
    ]
    problems.extend(
        f"{where} {STRAY}"
        for where, job in placed
        if not uploads(job) and environment_name(job) == ENVIRONMENT
    )
    problems.extend(
        f"{where} {REACHABLE}"
        for where, job in _placed(every, reading.pull_request_closure(every))
        if environment_name(job) == ENVIRONMENT
    )
    return problems
