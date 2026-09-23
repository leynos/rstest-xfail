"""The CV-005 judgements, each returning the reasons a workflow fails.

An empty list means the workflow complies. Returning reasons rather than a
boolean lets the fixture cases assert *which* clause fired, so a rule that
fails for the wrong reason cannot pass as one that works.

The publisher uploads behind two conjuncts: a ref guard confining it to
``main``, and the output of a check step reporting whether the token is set.
The token travels only as the upload action's ``access-token`` input and
inside the check step's one exact command. It sits in no ``env`` at any
scope, because the upload action is composite and hands its step's ``env``
to the nested artefact and cache steps it runs.
"""

from __future__ import annotations

import copy
import itertools
import re
import typing as typ

import codescene_reading as reading

UPLOAD_ACTION = "leynos/shared-actions/.github/actions/upload-codescene-coverage"
COVERAGE_ACTION = "leynos/shared-actions/.github/actions/generate-coverage"
# Upper-cased: GitHub resolves secret names without regard to case.
ACCESS_TOKEN = "CS_ACCESS_TOKEN"
SECRET_REFERENCE = "SECRETS.CS_ACCESS_TOKEN"
COVERAGE_CLI = "cs-coverage"
CODESCENE_HOST = "codescene.io"
MAIN_REF_GUARD = "github.ref == 'refs/heads/main'"
# The token check's sole command. The expression evaluates to true or false
# before the shell runs, so the step binds nothing and holds no shell
# conditional that could skip the write.
CHECK_COMMAND = (
    'echo "available=${{ secrets.CS_ACCESS_TOKEN != \'\' }}" >> "$GITHUB_OUTPUT"'
)
TOKEN_INPUT = "${{ secrets.CS_ACCESS_TOKEN }}"
# One group per ref, never per event: keyed on the event, an earlier dispatch
# could finish after a newer push and upload older coverage last.
CONCURRENCY_GROUP = "${{ github.workflow }}-${{ github.ref }}"
CHECK_KEYS = frozenset({"name", "id", "run"})
_QUOTED = re.compile(r"('[^']*')")


def mentions_the_token(text: str) -> bool:
    """Return whether ``text`` names the token, in any case."""
    return ACCESS_TOKEN in text.upper()


def references_the_secret(text: str) -> bool:
    """Return whether ``text`` references the secret itself, in any case."""
    return SECRET_REFERENCE in text.upper()


def step_input(step: reading.Step, key: str) -> object:
    """Return a step's ``with`` input, or ``None``."""
    with_block = step.get("with")
    return with_block.get(key) if isinstance(with_block, dict) else None


def input_is(step: reading.Step, key: str, *, expected: bool) -> bool:
    """Read a step input as a boolean, accepting the string and native forms."""
    value = step_input(step, key)
    return value is expected or value == str(expected).lower()


def is_coverage(step: reading.Step) -> bool:
    """Return whether a step runs the shared coverage action."""
    return reading.uses(step).startswith(COVERAGE_ACTION)


def is_ratcheted_coverage(step: reading.Step) -> bool:
    """Return whether a step runs the coverage action with the ratchet on."""
    return is_coverage(step) and input_is(step, "with-ratchet", expected=True)


def is_upload_action(step: reading.Step) -> bool:
    """Return whether a step runs the shared upload action, in any mode."""
    return reading.uses(step).startswith(UPLOAD_ACTION)


def _runs_cli_upload(run: str) -> bool:
    r"""Return whether a ``run`` body invokes ``cs-coverage upload``.

    A backslash-newline continuation joins ``cs-coverage \`` and ``upload``
    into one command, so the body is read as words, not contiguous text.
    """
    words = run.replace("\\\r\n", " ").replace("\\\n", " ").split()
    return any(
        (first == COVERAGE_CLI or first.endswith(f"/{COVERAGE_CLI}"))
        and second == "upload"
        for first, second in itertools.pairwise(words)
    )


def is_upload(step: reading.Step) -> bool:
    """Return whether a step uploads to CodeScene, by the action or the CLI.

    Only the literal ``check`` mode is not one: an absent mode (the default is
    ``upload``) and an expression both count, so an unreadable upload is judged.
    """
    mode = step_input(step, "mode")
    action = is_upload_action(step) and mode != "check"
    run = step.get("run")
    return action or (isinstance(run, str) and _runs_cli_upload(run))


def pull_request_findings(workflow: reading.Workflow) -> list[str]:
    """Return the reasons a workflow a pull request can reach breaches CV-005."""
    findings = _text_findings(workflow) + _call_findings(workflow)
    for step in reading.steps(workflow):
        findings.extend(_pull_request_step_findings(step))
    return findings


def _text_findings(workflow: reading.Workflow) -> list[str]:
    """Return the reasons found by reading the whole workflow as text.

    The token and host clauses read every scalar, case-folded for the host,
    so a workflow-level ``defaults.run.shell`` or a callee's
    ``workflow_call`` secret declaration cannot pass unseen.
    """
    text = reading.rendered(workflow)
    checks = (
        (mentions_the_token(text), f"a pull-request lane receives {ACCESS_TOKEN}"),
        (
            reading.computes_a_secret(text),
            "a pull-request lane reaches a secret by a computed name",
        ),
        (
            CODESCENE_HOST in text.lower(),
            f"a pull-request lane contacts {CODESCENE_HOST}",
        ),
    )
    return [finding for failed, finding in checks if failed]


def _call_findings(workflow: reading.Workflow) -> list[str]:
    """Return the reasons found in the workflow's job-level calls."""
    inherits = [
        f"job {job_id} forwards every secret with secrets: inherit"
        for job_id, job in reading.jobs(workflow)
        if job.get("secrets") == "inherit"
    ]
    refused = [
        f"job {job_id} calls {reference!r}, which resolves to no workflow here"
        for job_id, reference in reading.job_calls(workflow)
        if reading.classify_call(reference)[0] == reading.REFUSED
    ]
    return inherits + refused


def _pull_request_step_findings(step: reading.Step) -> list[str]:
    """Return the reasons one pull-request step breaches CV-005."""
    findings = []
    if is_upload_action(step):
        findings.append(f"a pull-request lane invokes {UPLOAD_ACTION}")
    run = step.get("run")
    if isinstance(run, str) and COVERAGE_CLI in run:
        findings.append(f"a pull-request lane runs {COVERAGE_CLI} directly")
    if is_coverage(step) and not input_is(step, "with-ratchet", expected=True):
        findings.append("a pull-request coverage step does not set with-ratchet")
    if is_coverage(step) and not input_is(step, "publish-artefact", expected=False):
        findings.append("a pull-request coverage step publishes its report")
    return findings


def publishes_from_main(workflow: reading.Workflow) -> bool:
    """Return whether a workflow is triggered by a push restricted to ``main``.

    An unfiltered push, a tag filter and a glob such as ``'**'`` all fail:
    the baseline written would be whichever branch pushed last.
    """
    push = reading.trigger(workflow, "push")
    branches = push.get("branches") if isinstance(push, dict) else None
    return (
        isinstance(branches, list)
        and bool(branches)
        and all(branch == "main" for branch in branches)
    )


def _unwrap(condition: str) -> str:
    """Return a condition without its ``${{ }}`` wrapper, if it has one."""
    body = condition.strip()
    if body.startswith("${{") and body.endswith("}}"):
        return body[3:-2]
    return body


def conjuncts(condition: str) -> list[str] | None:
    """Return the conjuncts of an ``if:`` condition, or ``None`` if it has ``||``.

    Quoted literals are respected, so a ``||`` inside a string does not count
    and an ``&&`` inside one does not split. A disjunction anywhere makes
    every conjunct optional, which is why it is refused rather than parsed.
    """
    # Splitting on a captured group alternates unquoted and quoted segments.
    segments = _QUOTED.split(_unwrap(condition))
    if any("||" in segment for segment in segments[::2]):
        return None
    parts = [""]
    for index, segment in enumerate(segments):
        pieces = segment.split("&&") if index % 2 == 0 else [segment]
        parts[-1] += pieces[0]
        parts.extend(pieces[1:])
    return [" ".join(part.split()) for part in parts]


def _token_check_id(step: reading.Step) -> str | None:
    """Return the check step's id when ``step`` is the token check exactly.

    The command is compared whole, as the step's sole command, because a step
    that merely contains it (``false && ...``) never writes the output.
    """
    run = step.get("run")
    step_id = step.get("id")
    if not isinstance(run, str) or not set(step) <= CHECK_KEYS:
        return None
    is_exact = run.strip() == CHECK_COMMAND
    return step_id if is_exact and isinstance(step_id, str) else None


def _guard_findings(upload: reading.Step, earlier: list[reading.Step]) -> list[str]:
    """Return the reasons an upload's condition does not confine it."""
    condition = upload.get("if")
    parts = conjuncts(condition) if isinstance(condition, str) else None
    if parts is None:
        return ["an upload step has no condition, or one with ||"]
    findings = []
    if MAIN_REF_GUARD not in parts:
        findings.append(f"an upload step is not guarded by {MAIN_REF_GUARD!r}")
    ids = [_token_check_id(step) for step in earlier]
    wanted = {
        f"steps.{step_id}.outputs.available == 'true'" for step_id in ids if step_id
    }
    if not wanted.intersection(parts):
        findings.append("an upload step is not guarded by an earlier token check")
    return findings


def _rendered_outside_allowance(step: reading.Step) -> str:
    """Render a step without the one place it may name the token, if any."""
    remainder = copy.deepcopy(step)
    if _token_check_id(step) is not None:
        remainder.pop("run", None)
    if is_upload_action(step) and isinstance(remainder.get("with"), dict):
        remainder["with"].pop("access-token", None)
    return reading.rendered(remainder)


def _env_blocks(workflow: reading.Workflow) -> list[tuple[str, object]]:
    """Return each ``env`` block in the workflow, named by its scope."""
    blocks: list[tuple[str, object]] = [("the workflow", workflow.get("env"))]
    for job_id, job in reading.jobs(workflow):
        blocks.append((f"job {job_id}", job.get("env")))
        blocks.extend(
            (f"a step of job {job_id}", step.get("env"))
            for step in reading.job_steps(job)
        )
    return [(scope, env) for scope, env in blocks if env is not None]


def _forwards_the_token(job: dict[typ.Any, typ.Any]) -> bool:
    """Return whether a job calling a reusable workflow hands it the token."""
    if "uses" not in job:
        return False
    names_it = any(
        references_the_secret(reading.rendered(job.get(key)))
        for key in ("with", "secrets")
    )
    return job.get("secrets") == "inherit" or names_it


def _token_findings(workflow: reading.Workflow) -> list[str]:
    """Return the reasons the token reaches anywhere but its allowed places."""
    findings = [
        f"{scope} binds {ACCESS_TOKEN} in its env"
        for scope, env in _env_blocks(workflow)
        if mentions_the_token(reading.rendered(env))
    ]
    findings.extend(
        f"job {job_id} forwards {ACCESS_TOKEN} to a reusable workflow"
        for job_id, job in reading.jobs(workflow)
        if _forwards_the_token(job)
    )
    if reading.computes_a_secret(reading.rendered(workflow)):
        findings.append("the publisher reaches a secret by a computed name")
    if any(
        references_the_secret(_rendered_outside_allowance(step))
        for step in reading.steps(workflow)
    ):
        findings.append(
            f"{ACCESS_TOKEN} is referenced outside the token check and the "
            "upload's access-token"
        )
    return findings


def _may_cancel(concurrency: object) -> bool:
    """Return whether a concurrency block could cancel a run in progress."""
    if not isinstance(concurrency, dict) or "cancel-in-progress" not in concurrency:
        return False
    return concurrency["cancel-in-progress"] is not False


def _concurrency_findings(workflow: reading.Workflow) -> list[str]:
    """Return the reasons the publisher's runs could cancel or reorder uploads."""
    root = workflow.get("concurrency")
    group = root.get("group") if isinstance(root, dict) else None
    findings = []
    if group != CONCURRENCY_GROUP:
        findings.append(
            f"the publisher's concurrency group is {group!r}, not {CONCURRENCY_GROUP!r}"
        )
    blocks = [root] + [job.get("concurrency") for _, job in reading.jobs(workflow)]
    if any(_may_cancel(block) for block in blocks):
        findings.append("the publisher may cancel a run in progress")
    return findings


def _every_guard_finding(workflow: reading.Workflow) -> list[str]:
    """Return the reasons any upload in the publisher is unguarded.

    Each upload is judged against the steps before it in its own job, since
    a step's outputs are visible only to later steps.
    """
    return [
        finding
        for _, job in reading.jobs(workflow)
        for position, step in enumerate(reading.job_steps(job))
        if is_upload(step)
        for finding in _guard_findings(step, reading.job_steps(job)[:position])
    ]


def publisher_findings(workflow: reading.Workflow) -> list[str]:
    """Return the reasons a main publisher fails to publish as CV-005 requires."""
    every_step = reading.steps(workflow)
    findings = []
    if not any(is_ratcheted_coverage(step) for step in every_step):
        findings.append("the main publisher generates no ratcheted coverage")
    if not any(is_upload(step) for step in every_step):
        findings.append("the main publisher uploads nothing to CodeScene")
    findings.extend(_every_guard_finding(workflow))
    findings.extend(_token_findings(workflow))
    findings.extend(_concurrency_findings(workflow))
    return findings


def _normalized_input(step: reading.Step, key: str) -> str | None:
    """Return a string input with its whitespace normalized."""
    value = step_input(step, key)
    return " ".join(value.split()) if isinstance(value, str) else None


def wiring_findings(workflow: reading.Workflow) -> list[str]:
    """Return the reasons the upload would not send what was measured.

    Each upload must read the file, in the format, that a coverage step
    writes, and must pass the token as its ``access-token``.
    """
    every_step = reading.steps(workflow)
    written = [
        (_normalized_input(step, "output-path"), _normalized_input(step, "format"))
        for step in every_step
        if is_ratcheted_coverage(step)
    ]
    findings = []
    for upload in filter(is_upload_action, every_step):
        read = (_normalized_input(upload, "path"), _normalized_input(upload, "format"))
        if read not in written:
            findings.append(
                f"the upload reads {read!r}, which no coverage step writes; "
                f"written: {written!r}"
            )
        token = _normalized_input(upload, "access-token")
        if token != TOKEN_INPUT:
            findings.append(
                f"the upload's access-token is {token!r}, not {TOKEN_INPUT!r}"
            )
    return findings


def baseline_writers(every: dict[str, reading.Workflow]) -> list[str]:
    """Return the workflow of every ratcheted coverage step a push can reach.

    ``generate-coverage`` saves the baseline on a push to ``main``, so each
    entry is a baseline writer, one per step. Reached through the push
    closure, a called workflow that ratchets is a writer as surely as its
    caller.
    """
    return [
        name
        for name in sorted(reading.push_closure(every))
        for step in reading.steps(every[name])
        if is_ratcheted_coverage(step)
    ]
