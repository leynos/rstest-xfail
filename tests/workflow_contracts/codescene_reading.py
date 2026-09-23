"""Read workflows for the CV-005 CodeScene coverage contract.

Every reader here errs towards seeing more. A workflow the contract cannot
see is a workflow it passes, so each place GitHub accepts more than one
spelling is read in all of them: both file extensions in either case, the
``on`` key as a string or as the boolean YAML 1.1 makes of it, a trigger
written as a scalar, a sequence or a mapping, and a reusable-workflow call
however its local path is prefixed.
"""

from __future__ import annotations

import typing as typ
from pathlib import Path

import yaml

WORKFLOW_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"
WORKFLOW_PREFIX = ".github/workflows/"
WORKFLOW_EXTENSIONS = (".yml", ".yaml")

# Events that run a workflow on behalf of a pull request. The review events
# and merge_group run pull-request code as surely as pull_request does, and
# workflow_run chains a workflow onto another run, which may be a pull
# request's. Every one seeds the closure.
PULL_REQUEST_EVENTS = frozenset(
    {
        "pull_request",
        "pull_request_target",
        "pull_request_review",
        "pull_request_review_comment",
        "merge_group",
        "workflow_run",
    }
)

Workflow = dict[typ.Any, typ.Any]
Step = dict[typ.Any, typ.Any]


class ContractError(ValueError):
    """A workflow the contract refuses to read."""


class StrictLoader(yaml.SafeLoader):
    """A SafeLoader that refuses a mapping declaring a key twice.

    PyYAML keeps the last duplicate and says nothing, so a lane could carry
    one ``runs-on`` or ``if:`` in the file and another in the parse.
    """

    def construct_mapping(
        self, node: yaml.MappingNode, deep: bool = False
    ) -> dict[typ.Any, typ.Any]:
        """Construct a mapping, raising on a repeated key."""
        seen: set[typ.Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise ContractError(f"duplicate key {key!r} {key_node.start_mark}")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def parse(name: str, text: str) -> Workflow:
    """Parse one workflow, refusing duplicate keys and a doubled trigger block.

    A root declaring both ``'on'`` and the boolean ``on`` is refused because
    GitHub merges the two blocks, and a reader that picks one is blind to the
    other.
    """
    try:
        parsed = yaml.load(text, Loader=StrictLoader)  # noqa: S506 - StrictLoader is a SafeLoader
    except yaml.YAMLError as error:
        raise ContractError(f"{name} is not valid YAML: {error}") from error
    if not isinstance(parsed, dict):
        raise ContractError(f"{name} is not a mapping")
    if "on" in parsed and True in parsed:
        raise ContractError(f"{name} declares its triggers under both 'on' and true")
    return parsed


def is_workflow(name: str) -> bool:
    """Return whether ``name`` is a workflow file, in either extension or case."""
    return name.lower().endswith(WORKFLOW_EXTENSIONS)


def workflows(directory: Path = WORKFLOW_DIR) -> dict[str, Workflow]:
    """Read every workflow in the directory, failing loudly on an empty one."""
    found = {
        path.name: parse(path.name, path.read_text(encoding="utf-8"))
        for path in sorted(directory.iterdir())
        if is_workflow(path.name)
    }
    if not found:
        raise ContractError(f"no workflows found under {directory}")
    return found


def _trigger_block(workflow: Workflow) -> object:
    """Return the trigger block, under the string or the boolean key."""
    return workflow.get("on", workflow.get(True))


def trigger_names(workflow: Workflow) -> list[str]:
    """Return the event names a workflow declares, in any of the three forms.

    A mapping-only reader stringifies ``on: [push, pull_request]`` into one
    key named after the whole list, and the workflow escapes every clause.
    """
    block = _trigger_block(workflow)
    if isinstance(block, str):
        return [block]
    if isinstance(block, list):
        return [name for name in block if isinstance(name, str)]
    if isinstance(block, dict):
        return [name for name in block if isinstance(name, str)]
    return []


def trigger(workflow: Workflow, event: str) -> object:
    """Return one trigger's configuration, when it is written as a mapping."""
    block = _trigger_block(workflow)
    return block.get(event) if isinstance(block, dict) else None


def starts_on_pull_request(workflow: Workflow) -> bool:
    """Return whether a workflow starts on behalf of a pull request."""
    return any(name in PULL_REQUEST_EVENTS for name in trigger_names(workflow))


def starts_on_push(workflow: Workflow) -> bool:
    """Return whether a workflow starts on a push, to any branch or tag."""
    return "push" in trigger_names(workflow)


def jobs(workflow: Workflow) -> list[tuple[str, dict[typ.Any, typ.Any]]]:
    """Return every job as ``(job id, job mapping)``."""
    block = workflow.get("jobs")
    if not isinstance(block, dict):
        return []
    return [(str(key), job) for key, job in block.items() if isinstance(job, dict)]


def job_steps(job: dict[typ.Any, typ.Any]) -> list[Step]:
    """Return the steps of one job, in order."""
    listed = job.get("steps")
    if not isinstance(listed, list):
        return []
    return [step for step in listed if isinstance(step, dict)]


def steps(workflow: Workflow) -> list[Step]:
    """Return every step of every job."""
    return [step for _, job in jobs(workflow) for step in job_steps(job)]


def uses(step: Step) -> str:
    """Return a step's ``uses`` reference, or the empty string."""
    reference = step.get("uses")
    return reference if isinstance(reference, str) else ""


LOCAL = "local"
REFUSED = "refused"
REMOTE = "remote"


def classify_call(reference: str) -> tuple[str, str]:
    """Classify a job-level ``uses`` reference as local, refused or remote.

    Matched by shape: a leading ``./`` or GitHub's documented ``$/`` is
    stripped, and what remains is local when it is a path under
    ``.github/workflows/``. A local-shaped reference carrying an ``@ref`` or
    naming a subdirectory is refused rather than read as remote: it resolves
    to no file here, so whatever it runs would escape the closure in silence.
    """
    path = reference
    for prefix in ("./", "$/"):
        if path.startswith(prefix):
            path = path[len(prefix) :]
            break
    if not path.startswith(WORKFLOW_PREFIX):
        return (REMOTE, "")
    file = path[len(WORKFLOW_PREFIX) :]
    return (LOCAL, file) if _names_one_file(file) else (REFUSED, "")


def _names_one_file(file: str) -> bool:
    """Return whether ``file`` names one workflow, with no directory or ``@ref``."""
    return bool(file) and not any(mark in file for mark in "/@")


def job_calls(workflow: Workflow) -> list[tuple[str, str]]:
    """Return each job's ``uses`` reference with the job's id."""
    return [
        (job_id, job["uses"])
        for job_id, job in jobs(workflow)
        if isinstance(job.get("uses"), str)
    ]


def closure(
    every: dict[str, Workflow], seeds: typ.Callable[[Workflow], bool]
) -> set[str]:
    """Return the workflows reachable from those ``seeds`` selects.

    A workflow declaring only ``workflow_call`` names no event of its own,
    yet it runs with whatever the caller hands it, including the caller's
    secrets under ``secrets: inherit``. So every clause about what an event
    can reach runs over this closure, never over the trigger list alone.
    """
    reached = {name for name, workflow in every.items() if seeds(workflow)}
    pending = list(reached)
    while pending:
        fresh = (_local_callees(every[pending.pop()]) & every.keys()) - reached
        reached |= fresh
        pending.extend(fresh)
    return reached


def _local_callees(workflow: Workflow) -> set[str]:
    """Return the local workflows ``workflow`` calls, by file name."""
    calls = (classify_call(reference) for _, reference in job_calls(workflow))
    return {callee for kind, callee in calls if kind == LOCAL}


def pull_request_closure(every: dict[str, Workflow]) -> set[str]:
    """Return the workflows a pull request can reach."""
    return closure(every, starts_on_pull_request)


def push_closure(every: dict[str, Workflow]) -> set[str]:
    """Return the workflows a push can reach."""
    return closure(every, starts_on_push)


def missing_callees(every: dict[str, Workflow], names: set[str]) -> list[str]:
    """Return each local call, from the named workflows, to a missing file."""
    return [
        f"{name} calls {reference!r}, which is not there"
        for name in sorted(names)
        for _, reference in job_calls(every[name])
        if classify_call(reference)[0] == LOCAL
        and classify_call(reference)[1] not in every
    ]


def rendered(value: object) -> str:
    """Return every key and scalar in a parsed value, one per line.

    Reading the parse rather than the file is deliberate: comments are gone,
    so prose explaining why the token is absent does not read as the token
    being present, while a block scalar's content, which Actions expands, is
    read in full. Keys carry their ``:`` so the computed-secret clause can
    tell a ``secrets:`` key from an expression.
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        return "".join(
            f"{rendered(key).rstrip()}:\n{rendered(item)}"
            for key, item in value.items()
        )
    if isinstance(value, list):
        return "".join(rendered(item) for item in value)
    if isinstance(value, bool):
        return f"{str(value).lower()}\n"
    return f"{value}\n"


def computes_a_secret(text: str) -> bool:
    """Return whether ``text`` reaches the ``secrets`` context other than by name.

    ``secrets['CS_' + ...]`` and ``toJSON(secrets)`` hand a step the token
    without spelling it. Every ``secrets`` word is judged by what follows: a
    ``.`` is a named reference, a ``:`` is a YAML key, and a following word
    is prose. Anything else is a computed or whole-context access.
    """
    start = text.find("secrets")
    while start != -1:
        before = text[start - 1] if start else ""
        following = text[start + len("secrets") :].lstrip()
        after = following[:1]
        is_word_start = not before or not (before.isalnum() or before in "_.")
        # A following word makes it prose ("keeps secrets out of logs").
        is_prose = after.isalnum() or after == "_"
        is_expression = after not in (".", ":", "") and not is_prose
        if is_word_start and is_expression:
            return True
        start = text.find("secrets", start + 1)
    return False
