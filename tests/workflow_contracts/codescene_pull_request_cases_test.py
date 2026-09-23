"""Drive the CV-005 readers and pull-request rules against fixtures.

Every real workflow complies, so a rule exercised only over them passes
whether or not it detects anything. Each case builds the breach it names and
asserts the rule reports it; the compliant fixtures assert it stays quiet.
"""

from __future__ import annotations

import itertools

import codescene_reading as reading
import codescene_rules as rules
import pytest

BREACHING = """
on:
  pull_request:
jobs:
  build:
    steps:
      - uses: leynos/shared-actions/.github/actions/generate-coverage@abc
        with:
          output-path: lcov.info
      - env:
          CS_ACCESS_TOKEN: ${{ secrets.CS_ACCESS_TOKEN }}
        uses: leynos/shared-actions/.github/actions/upload-codescene-coverage@abc
      - run: cs-coverage upload --format lcov
      - run: curl https://api.codescene.io/v2/projects
"""

COMPLIANT = """
on:
  pull_request:
jobs:
  build:
    steps:
      - uses: leynos/shared-actions/.github/actions/generate-coverage@abc
        with:
          output-path: lcov.info
          with-ratchet: 'true'
          publish-artefact: 'false'
"""


def _parse(source: str) -> reading.Workflow:
    """Parse a fixture through the contract's own strict reader."""
    return reading.parse("fixture", source)


@pytest.mark.parametrize(("source", "expected"), [(BREACHING, 6), (COMPLIANT, 0)])
def test_the_pull_request_rule_counts_each_breach(source: str, expected: int) -> None:
    """Token, host, action, CLI, missing ratchet and published report: six."""
    findings = rules.pull_request_findings(_parse(source))
    assert len(findings) == expected, findings


@pytest.mark.parametrize(
    "job",
    [
        "steps:\n  - run: echo ${{ secrets.CS_ACCESS_TOKEN }}\n",
        "steps:\n  - run: |\n      # ${{ secrets.CS_ACCESS_TOKEN }}\n      true\n",
        "steps:\n  - uses: x/y@abc\n    with:\n      t: ${{ secrets.CS_ACCESS_TOKEN }}\n",
        "env:\n  T: ${{ secrets.CS_ACCESS_TOKEN }}\nsteps:\n  - run: 'true'\n",
        "uses: ./.github/workflows/c.yml\nsecrets:\n  X: ${{ secrets.CS_ACCESS_TOKEN }}\n",
        "uses: ./.github/workflows/c.yml\nsecrets: inherit\n",
        "steps:\n  - run: echo ${{ secrets[format('CS_{0}', 'ACCESS_TOKEN')] }}\n",
        "steps:\n  - run: echo '${{ toJSON(secrets) }}'\n",
    ],
    ids=[
        "run_body",
        "block_scalar",
        "action_input",
        "env_value",
        "named_forwarding",
        "inherit",
        "computed_name",
        "whole_context",
    ],
)
def test_every_route_to_the_token_is_reported(job: str) -> None:
    """A run body, block scalar, input, env, forwarding or inheritance."""
    indented = "".join(f"    {line}\n" for line in job.splitlines())
    source = f"on: pull_request\njobs:\n  lane:\n{indented}"
    assert rules.pull_request_findings(_parse(source)), source


@pytest.mark.parametrize(
    ("source", "clause"),
    [
        (
            "on: pull_request\ndefaults:\n  run:\n"
            "    shell: curl -d @- https://API.CodeScene.io/x {0}\njobs: {}\n",
            "contacts codescene.io",
        ),
        (
            "on:\n  workflow_call:\n    secrets:\n      CS_ACCESS_TOKEN:\n"
            "        required: true\njobs: {}\n",
            "receives CS_ACCESS_TOKEN",
        ),
    ],
    ids=["default_shell", "declared_secret"],
)
def test_the_whole_document_is_read(source: str, clause: str) -> None:
    """A default shell and a declared secret sit outside every job."""
    findings = rules.pull_request_findings(_parse(source))
    assert len(findings) == 1, findings
    assert clause in findings[0], findings


def test_a_named_secret_and_prose_are_not_computed_references() -> None:
    """Another named secret and the word in prose do not trip the clause."""
    source = (
        "on: pull_request\njobs:\n  lane:\n    steps:\n"
        "      - run: echo ${{ secrets.GITHUB_TOKEN }} keeps secrets out of logs\n"
    )
    assert rules.pull_request_findings(_parse(source)) == []


def test_a_call_to_a_missing_workflow_is_reported() -> None:
    """The closure can only follow a file it has read."""
    caller = "on: pull_request\njobs:\n  c:\n    uses: ./.github/workflows/gone.yml\n"
    every = {"caller.yml": _parse(caller)}
    missing = reading.missing_callees(every, reading.pull_request_closure(every))
    assert len(missing) == 1, missing
    assert "gone.yml" in missing[0], missing


CALLEE = """
on: workflow_call
jobs:
  leak:
    steps:
      - run: |
          curl -H "Authorization: ${{ secrets.CS_ACCESS_TOKEN }}" https://codescene.io/api
"""


@pytest.mark.parametrize(
    "call",
    [
        "./.github/workflows/called.yml",
        "$/.github/workflows/called.yml",
        ".github/workflows/called.yml",
    ],
    ids=["dot_prefixed", "dollar_prefixed", "bare"],
)
def test_a_called_workflow_is_inside_the_pull_request_closure(call: str) -> None:
    """The probe: a workflow_call callee given the token by inheritance."""
    caller = (
        f"on: [pull_request]\njobs:\n  c:\n    uses: {call}\n    secrets: inherit\n"
    )
    every = {"caller.yml": _parse(caller), "called.yml": _parse(CALLEE)}
    assert "called.yml" in reading.pull_request_closure(every)
    assert len(rules.pull_request_findings(every["called.yml"])) == 2


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("./.github/workflows/called.yml", (reading.LOCAL, "called.yml")),
        ("$/.github/workflows/called.yml", (reading.LOCAL, "called.yml")),
        ("leynos/shared-actions/.github/workflows/c.yml@abc", (reading.REMOTE, "")),
        ("$/.github/workflows/called.yml@main", (reading.REFUSED, "")),
        ("./.github/workflows/called.yml@main", (reading.REFUSED, "")),
        ("./.github/workflows/sub/called.yml", (reading.REFUSED, "")),
    ],
    ids=["dot", "dollar", "remote", "dollar_with_ref", "dot_with_ref", "nested"],
)
def test_each_call_spelling_is_classified(
    reference: str, expected: tuple[str, str]
) -> None:
    """Both local spellings resolve; a local shape with a ref is refused."""
    assert reading.classify_call(reference) == expected


def test_a_refused_call_is_a_finding() -> None:
    """The pull-request rule names a refused call."""
    source = "on: pull_request\njobs:\n  c:\n    uses: $/.github/workflows/c.yml@main\n"
    findings = rules.pull_request_findings(_parse(source))
    assert len(findings) == 1, findings
    assert "resolves to no workflow" in findings[0], findings


@pytest.mark.parametrize(
    "source",
    [
        "on: pull_request\njobs: {}\n",
        "on: [push, pull_request]\njobs: {}\n",
        "on:\n  pull_request:\njobs: {}\n",
        "'on':\n  pull_request:\njobs: {}\n",
        "on: [pull_request_target]\njobs: {}\n",
        "on: pull_request_review\njobs: {}\n",
        "on: [pull_request_review_comment]\njobs: {}\n",
        "on:\n  merge_group:\njobs: {}\n",
        "on:\n  workflow_run:\n    workflows: [CI]\njobs: {}\n",
    ],
    ids=[
        "scalar",
        "sequence",
        "mapping",
        "quoted_key",
        "target",
        "review",
        "review_comment",
        "merge_group",
        "workflow_run",
    ],
)
def test_every_pull_request_trigger_is_read(source: str) -> None:
    """Each form and each event that runs pull-request code seeds the closure."""
    assert reading.starts_on_pull_request(_parse(source)), source


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (
            "on: pull_request\njobs:\n  a:\n    runs-on: x\n    runs-on: y\n",
            "duplicate",
        ),
        ("'on': push\non: pull_request\njobs: {}\n", "under both"),
    ],
    ids=["duplicate_key", "both_trigger_keys"],
)
def test_an_ambiguous_document_is_refused(source: str, reason: str) -> None:
    """A repeated key and a doubled trigger block are both refused."""
    with pytest.raises(reading.ContractError, match=reason):
        reading.parse("fixture", source)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("ci.yml", True), ("ci.YML", True), ("ci.Yaml", True), ("ci.json", False)],
)
def test_workflow_files_are_recognised_in_any_case(name: str, expected: bool) -> None:
    """A case-sensitive comparison would skip a ``.YML`` workflow in silence."""
    assert reading.is_workflow(name) is expected


def _graph_workflows(
    size: int, seeds: tuple[bool, ...], edges: tuple[bool, ...]
) -> dict:
    """Render one call graph as workflows, rotating through call spellings."""
    spellings = itertools.cycle(("./", "$/", ""))
    every = {}
    for caller in range(size):
        calls = "".join(
            f"  call_{callee}:\n    uses: {next(spellings)}.github/workflows/w{callee}.yml\n"
            for callee in range(size)
            if edges[caller * size + callee]
        )
        trigger = "pull_request" if seeds[caller] else "workflow_call"
        body = f"jobs:\n{calls}" if calls else "jobs: {}\n"
        every[f"w{caller}.yml"] = _parse(f"on: {trigger}\n{body}")
    return every


def _reachable(size: int, seeds: tuple[bool, ...], edges: tuple[bool, ...]) -> set[str]:
    """Compute reachability by relaxing every edge until nothing changes."""
    reached = {index for index in range(size) if seeds[index]}
    changed = True
    while changed:
        grown = reached | {
            callee
            for caller in reached
            for callee in range(size)
            if edges[caller * size + callee]
        }
        changed = grown != reached
        reached = grown
    return {f"w{index}.yml" for index in reached}


@pytest.mark.parametrize("size", [1, 2, 3])
def test_the_closure_is_exactly_what_a_pull_request_can_reach(size: int) -> None:
    """Every call graph of up to three workflows, cycles and self-calls included.

    The graphs are enumerated exhaustively rather than sampled, and the rule's
    own query is compared with an independent reachability computation.
    """
    for seeds in itertools.product((False, True), repeat=size):
        for edges in itertools.product((False, True), repeat=size * size):
            every = _graph_workflows(size, seeds, edges)
            assert reading.pull_request_closure(every) == _reachable(
                size, seeds, edges
            ), (
                seeds,
                edges,
            )
