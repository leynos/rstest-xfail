"""Drive the CV-005 main-publisher rules against fixtures.

Each case varies one clause of an otherwise complying publisher and asserts
the rule names that clause and nothing else, so a rule that fails for the
wrong reason cannot pass as one that works.
"""

from __future__ import annotations

import codescene_reading as reading
import codescene_rules as rules
import pytest

PUBLISHER = """
on:
  push:
    branches: [main]
  workflow_dispatch:
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: false
jobs:
  coverage:
    steps:
      - uses: leynos/shared-actions/.github/actions/generate-coverage@abc
        with:
          output-path: lcov.info
          format: lcov
          with-ratchet: 'true'
      - name: Check CodeScene token
        id: codescene-token
        run: echo "available=${{ secrets.CS_ACCESS_TOKEN != '' }}" >> "$GITHUB_OUTPUT"
      - name: Upload
        if: ${{ steps.codescene-token.outputs.available == 'true' && github.ref == 'refs/heads/main' }}
        uses: leynos/shared-actions/.github/actions/upload-codescene-coverage@abc
        with:
          path: lcov.info
          format: lcov
          access-token: ${{ secrets.CS_ACCESS_TOKEN }}
"""

GUARD = "steps.codescene-token.outputs.available == 'true' && github.ref == 'refs/heads/main'"
CHECK = (
    "      - name: Check CodeScene token\n        id: codescene-token\n"
    "        run: echo \"available=${{ secrets.CS_ACCESS_TOKEN != '' }}\""
    ' >> "$GITHUB_OUTPUT"\n'
)
UPLOAD_NAME = "      - name: Upload\n"
REUSABLE = "jobs:\n  forward:\n    uses: ./.github/workflows/elsewhere.yml\n"


def _env_binding(indent: str) -> str:
    """Return a declaration of the token in an ``env`` at ``indent``."""
    return (
        f"{indent}env:\n{indent}  CS_ACCESS_TOKEN: ${{{{ secrets.CS_ACCESS_TOKEN }}}}\n"
    )


def _vary(old: str, new: str) -> reading.Workflow:
    """Apply one replacement to the publisher, failing if it changes nothing."""
    source = PUBLISHER.replace(old, new, 1)
    assert not old or source != PUBLISHER, f"the case changed nothing: {old!r}"
    return reading.parse("fixture", source)


def _names_exactly(findings: list[str], expected: tuple[str, ...]) -> None:
    """Assert ``findings`` name exactly the ``expected`` clauses."""
    assert len(findings) == len(expected), findings
    for clause in expected:
        assert any(clause in finding for finding in findings), (clause, findings)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("on:\n  push:\n    branches: [main]\njobs: {}\n", True),
        ("on:\n  push:\njobs: {}\n", False),
        ("on: push\njobs: {}\n", False),
        ("on:\n  push:\n    tags: ['v*']\njobs: {}\n", False),
        ("on:\n  push:\n    branches: ['**']\njobs: {}\n", False),
        ("on:\n  push:\n    branches: [main, develop]\njobs: {}\n", False),
    ],
    ids=[
        "main_only",
        "unfiltered",
        "scalar",
        "tags",
        "every_branch",
        "main_and_another",
    ],
)
def test_only_a_push_restricted_to_main_is_the_publisher(
    source: str,
    expected: bool,
) -> None:
    """Only a push filtered to the literal ``main`` publishes."""
    assert rules.publishes_from_main(reading.parse("fixture", source)) is expected


PR = "github.event_name == 'workflow_dispatch'"


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("", "", ()),
        (GUARD, f"{GUARD} && github.actor != 'x'", ()),
        (GUARD, f"{GUARD} && github.actor != 'x' || {PR}", ("with ||",)),
        (
            GUARD,
            "steps.codescene-token.outputs.available == 'true'",
            ("github.ref ==",),
        ),
        (GUARD, "github.ref == 'refs/heads/main'", ("earlier token check",)),
        (GUARD, GUARD.replace("codescene-token", "other"), ("earlier token check",)),
        (f"        if: ${{{{ {GUARD} }}}}\n", "", ("no condition",)),
    ],
    ids=[
        "complies",
        "narrowed",
        "disjunction",
        "no_ref_guard",
        "no_check_guard",
        "other_step_id",
        "no_condition",
    ],
)
def test_the_upload_condition_is_judged(
    old: str, new: str, expected: tuple[str, ...]
) -> None:
    """The hidden ``||`` keeps both conjuncts whole: only its refusal catches it."""
    _names_exactly(rules.publisher_findings(_vary(old, new)), expected)


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (CHECK, "", ("earlier token check",)),
        (
            "available=${{ secrets.CS_ACCESS_TOKEN != '' }}",
            "available=true",
            ("earlier token check",),
        ),
        (
            "run: echo",
            "run: false && echo",
            ("earlier token check", "referenced outside"),
        ),
        (
            "        id: codescene-token\n",
            "        id: codescene-token\n        if: false\n",
            ("earlier token check", "referenced outside"),
        ),
        (
            "        id: codescene-token\n",
            "        id: codescene-token\n" + _env_binding("        "),
            ("earlier token check", "referenced outside", "binds CS_ACCESS_TOKEN"),
        ),
    ],
    ids=["deleted", "other_command", "neutralised", "conditional", "bound_in_env"],
)
def test_the_token_check_is_judged(
    old: str, new: str, expected: tuple[str, ...]
) -> None:
    """With the check gone the upload skips forever, so it is compared whole."""
    _names_exactly(rules.publisher_findings(_vary(old, new)), expected)


def test_a_check_after_the_upload_does_not_guard_it() -> None:
    """A step's outputs are visible only to later steps."""
    source = PUBLISHER.replace(CHECK, "", 1) + CHECK
    findings = rules.publisher_findings(reading.parse("fixture", source))
    _names_exactly(findings, ("earlier token check",))


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            UPLOAD_NAME,
            UPLOAD_NAME + _env_binding("        "),
            ("binds CS_ACCESS_TOKEN", "referenced outside"),
        ),
        ("jobs:\n", _env_binding("") + "jobs:\n", ("binds CS_ACCESS_TOKEN",)),
        (
            "    steps:\n",
            _env_binding("    ") + "    steps:\n",
            ("binds CS_ACCESS_TOKEN",),
        ),
        (
            UPLOAD_NAME,
            "      - run: echo ${{ secrets.CS_ACCESS_TOKEN }}\n" + UPLOAD_NAME,
            ("referenced outside",),
        ),
        (
            "jobs:\n",
            REUSABLE + "    with:\n      t: ${{ secrets.CS_ACCESS_TOKEN }}\n",
            ("reusable workflow",),
        ),
        (
            "jobs:\n",
            REUSABLE + "    secrets:\n      T: ${{ secrets.CS_ACCESS_TOKEN }}\n",
            ("reusable workflow",),
        ),
        ("jobs:\n", REUSABLE + "    secrets: inherit\n", ("reusable workflow",)),
        (
            "    steps:\n",
            "    env:\n      cs_access_token: ${{ secrets.cs_access_token }}\n    steps:\n",
            ("binds CS_ACCESS_TOKEN",),
        ),
        (
            UPLOAD_NAME,
            "      - run: echo ${{ secrets.cs_access_token }}\n" + UPLOAD_NAME,
            ("referenced outside",),
        ),
        (
            UPLOAD_NAME,
            "      - run: echo ${{ secrets['CS_ACCESS_TOKEN'] }}\n" + UPLOAD_NAME,
            ("computed name",),
        ),
    ],
    ids=[
        "upload_env",
        "workflow_env",
        "job_env",
        "run_step",
        "forwarded_as_input",
        "forwarded_by_name",
        "forwarded_by_inheritance",
        "lower_case_env",
        "lower_case_run_step",
        "computed",
    ],
)
def test_the_token_travels_only_where_allowed(
    old: str, new: str, expected: tuple[str, ...]
) -> None:
    """No env anywhere, however the name is cased.

    The composite upload hands its step's env to the nested steps it runs.
    """
    _names_exactly(rules.publisher_findings(_vary(old, new)), expected)


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("cancel-in-progress: false", "cancel-in-progress: true", ("may cancel",)),
        (
            "cancel-in-progress: false",
            "cancel-in-progress: ${{ true }}",
            ("may cancel",),
        ),
        (
            "}}-${{ github.ref",
            "}}-${{ github.event_name }}-${{ github.ref",
            ("concurrency group",),
        ),
        (
            "concurrency:\n  group: ${{ github.workflow }}-${{ github.ref }}\n"
            "  cancel-in-progress: false\n",
            "",
            ("concurrency group",),
        ),
        (
            "    steps:\n",
            "    concurrency:\n      group: x\n      cancel-in-progress: true\n    steps:\n",
            ("may cancel",),
        ),
    ],
    ids=[
        "cancels",
        "cancels_by_expression",
        "keyed_on_event",
        "no_group",
        "job_cancels",
    ],
)
def test_the_publisher_never_cancels(
    old: str, new: str, expected: tuple[str, ...]
) -> None:
    """Keyed on the event, an earlier dispatch could upload older coverage last."""
    _names_exactly(rules.publisher_findings(_vary(old, new)), expected)


def test_a_continued_cli_upload_is_still_an_upload() -> None:
    r"""The shell joins ``cs-coverage \`` and ``upload`` into one command."""
    extra = (
        "      - run: |\n          cs-coverage \\\n            upload --format lcov\n"
    )
    findings = rules.publisher_findings(reading.parse("fixture", PUBLISHER + extra))
    _names_exactly(findings, ("no condition",))


def test_an_expression_mode_is_still_an_upload() -> None:
    """Only the literal ``check`` mode is not an upload, so this one is judged."""
    extra = (
        "      - uses: leynos/shared-actions/.github/actions/upload-codescene-coverage@abc\n"
        "        with:\n          mode: ${{ 'upload' }}\n"
        "          access-token: ${{ secrets.CS_ACCESS_TOKEN }}\n"
    )
    findings = rules.publisher_findings(reading.parse("fixture", PUBLISHER + extra))
    _names_exactly(findings, ("no condition",))


def test_check_mode_is_not_an_upload() -> None:
    """The upload action in ``check`` mode publishes nothing."""
    workflow = _vary("          path: lcov.info\n", "          mode: check\n")
    _names_exactly(rules.publisher_findings(workflow), ("uploads nothing",))


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("${{ github.ref == 'refs/heads/main' && env.X != 'a||b' }}", 2),
        ("${{ github.ref == 'refs/heads/main' && env.X != 'a&&b' }}", 2),
        ("github.ref == 'refs/heads/main' || true", None),
    ],
    ids=["quoted_or", "quoted_and", "bare_or"],
)
def test_quoted_operators_are_not_operators(
    condition: str, expected: int | None
) -> None:
    """Operators inside quoted literals neither split nor disjoin."""
    parts = rules.conjuncts(condition)
    assert (None if parts is None else len(parts)) == expected


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("", "", ()),
        ("path: lcov.info", "path: other.info", ("which no coverage step writes",)),
        (
            "          format: lcov\n          access",
            "          format: cobertura\n          access",
            ("which no coverage step writes",),
        ),
        ("          access-token: ${{ secrets.CS_ACCESS_TOKEN }}\n", "", ("is None",)),
        (
            "access-token: ${{ secrets.CS_ACCESS_TOKEN }}",
            "access-token: ${{ env.CS_ACCESS_TOKEN }}",
            ("access-token is",),
        ),
    ],
    ids=["wired", "other_path", "other_format", "no_token", "env_token"],
)
def test_the_upload_sends_what_was_measured(
    old: str, new: str, expected: tuple[str, ...]
) -> None:
    """The upload reads what the coverage step wrote, with the token."""
    _names_exactly(rules.wiring_findings(_vary(old, new)), expected)


CALLED_WRITER = (
    "on: workflow_call\njobs:\n  measure:\n    steps:\n"
    "      - uses: leynos/shared-actions/.github/actions/generate-coverage@abc\n"
    "        with:\n          with-ratchet: 'true'\n"
)


@pytest.mark.parametrize(
    "prefix", ["./", "$/"], ids=["dot_prefixed", "dollar_prefixed"]
)
def test_a_called_baseline_writer_is_counted(prefix: str) -> None:
    """A push reaching a second ratcheted step through a call is two writers."""
    caller = (
        "on:\n  push:\n    branches: ['**']\njobs:\n  call:\n"
        f"    uses: {prefix}.github/workflows/called.yml\n"
    )
    every = {
        "publisher.yml": reading.parse("publisher", PUBLISHER),
        "caller.yml": reading.parse("caller", caller),
        "called.yml": reading.parse("called", CALLED_WRITER),
    }
    assert rules.baseline_writers(every) == ["called.yml", "publisher.yml"]
