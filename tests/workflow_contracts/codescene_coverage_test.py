"""Hold CodeScene coverage publication on ``main``, per concordat's CV-005.

The rule has four clauses, and this file asserts each of them against the
repository's own workflows:

1. no workflow a pull request can reach invokes a CodeScene action, runs
   ``cs-coverage``, contacts ``codescene.io``, receives ``CS_ACCESS_TOKEN``,
   forwards every secret with ``secrets: inherit``, or publishes its report;
2. every ``generate-coverage`` step such a workflow runs ratchets, reading
   the baseline the publisher writes;
3. exactly one workflow triggered by a push restricted to ``main`` generates
   ratcheted coverage and uploads it, behind ``github.ref ==
   'refs/heads/main'`` and an earlier token check, passing the token only as
   ``access-token``, in a concurrency group keyed on the ref that never
   cancels;
4. no other workflow a push can reach writes the ratchet baseline.

CodeScene accepts an upload only for a branch it analyses, which a pull
request head is not, and its check mode fails on every project whose
coverage gates are off. What CV-005 moves off the pull request is the call
to the service; the artefact it downloads is already pinned by digest.

The judgements live in ``codescene_rules`` and are driven against breaching
fixtures in the ``codescene_*_cases_test`` modules, because a rule exercised
only over correct workflows passes whether or not it detects anything.

Run via ``make test-workflow-contracts``.
"""

from __future__ import annotations

import codescene_reading as reading
import codescene_rules as rules

# Workflows a pull request is known to start. The closure is computed from
# the directory, so a new workflow is covered the day it lands; this is the
# floor it must still reach, so a closure that emptied cannot pass.
KNOWN_PULL_REQUEST_WORKFLOWS = frozenset(
    {
        "act-validation.yml",
        "ci.yml",
        "dependabot-automerge.yml",
    }
)
PUBLISHER = "coverage-main.yml"


def test_no_workflow_a_pull_request_reaches_touches_codescene() -> None:
    """Every workflow in the pull-request closure keeps clear of CodeScene."""
    every = reading.workflows()
    closure = reading.pull_request_closure(every)
    missing = KNOWN_PULL_REQUEST_WORKFLOWS - closure
    assert not missing, f"{sorted(missing)} fell out of the closure {sorted(closure)}"
    breaches = [
        f"{name}: {finding}"
        for name in sorted(closure)
        for finding in rules.pull_request_findings(every[name])
    ]
    breaches.extend(reading.missing_callees(every, closure))
    assert not breaches, f"CV-005 breaches: {breaches}"


def test_exactly_one_main_publisher_uploads_ratcheted_coverage() -> None:
    """One push-to-main publisher uploads what it measured, as clause 3 says.

    Without this, the first clause is satisfied by deleting the upload.
    """
    every = reading.workflows()
    publishers = sorted(
        name for name, workflow in every.items() if rules.publishes_from_main(workflow)
    )
    assert publishers == [PUBLISHER], f"expected [{PUBLISHER!r}], found {publishers}"
    assert PUBLISHER not in reading.pull_request_closure(every), (
        f"{PUBLISHER} publishes from main but a pull request can reach it"
    )
    workflow = every[PUBLISHER]
    findings = rules.publisher_findings(workflow) + rules.wiring_findings(workflow)
    assert not findings, f"{PUBLISHER}: {findings}"


def test_only_the_publisher_writes_the_baseline() -> None:
    """The only ratcheted coverage step a push can reach is the publisher's."""
    writers = rules.baseline_writers(reading.workflows())
    assert writers == [PUBLISHER], f"expected the publisher alone, saw {writers}"


def _baselines(workflow: reading.Workflow) -> list[tuple[object, object]]:
    """Return the baseline paths every coverage step in ``workflow`` reads."""
    return [
        (
            rules.step_input(step, "baseline-rust-file"),
            rules.step_input(step, "baseline-python-file"),
        )
        for step in reading.steps(workflow)
        if rules.is_coverage(step)
    ]


def test_every_pull_request_lane_reads_the_publisher_baseline() -> None:
    """Each lane, judged alone, reads the baseline the publisher writes."""
    every = reading.workflows()
    written = _baselines(every[PUBLISHER])
    assert len(written) == 1, f"expected one publisher coverage step, saw {written}"
    read = [
        (name, baseline)
        for name in sorted(reading.pull_request_closure(every))
        for baseline in _baselines(every[name])
    ]
    assert read, "no pull-request lane measures coverage"
    for name, baseline in read:
        assert baseline == written[0], (
            f"{name} reads {baseline}, the publisher writes {written[0]}"
        )
