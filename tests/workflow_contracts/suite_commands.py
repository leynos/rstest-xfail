"""Recognize shell commands that run a Rust crate's test suite.

The suite-once contract needs to know whether a workflow line runs the suite
outside the coverage action. A substring check is both too wide (``echo
cargo test``) and too narrow (``make "test"``, ``make lint&&make test``), so a
command is split into segments at the shell separators that sit outside quotes
and escapes, each segment is split into words as the shell would, and the
program each segment runs is read before its arguments, through any ``env``
wrapper, so ``echo cargo test`` is not a suite run.
"""

from __future__ import annotations

import re
import shlex

#: Make options that take their value as the next word.
MAKE_VALUE_OPTIONS = frozenset(
    {"-C", "-f", "-I", "-o", "-W", "--directory", "--file", "--makefile"}
)
#: Make targets that run the suite: ``test``, ``all`` (which runs it),
#: ``coverage`` and the fast local variants. A bare ``make`` runs the default
#: goal, ``all``, so it counts too.
SUITE_TARGETS = frozenset({"test", "all", "coverage", "dev-test", "test-fast"})
#: ``env`` options that take their value as the next word.
ENV_VALUE_OPTIONS = frozenset({"-u", "--unset", "-C", "--chdir"})
#: The shell's view of a command, one piece at a time: a comment (dropped), a
#: line continuation (read as a space), a separator between commands, or text,
#: where quoted strings and escaped characters are kept whole so a separator
#: inside them does not split the command.
TOKENS = re.compile(
    r"""
    (?P<comment>(?:^|(?<=[\s;&|]))\#[^\n]*)
    |(?P<continuation>\\\n)
    |(?P<separator>[;&|\n])
    |(?P<text>'[^']*'|"(?:\\.|[^"\\])*"|\\.|[^'"\\;&|\n\#]+|\#)
    """,
    re.VERBOSE | re.DOTALL | re.MULTILINE,
)
#: Cargo options that take their value as the next word.
CARGO_VALUE_OPTIONS = frozenset(
    {"--config", "-Z", "-C", "--manifest-path", "--color", "--target-dir"}
)
#: Cargo subcommands that run the suite.
SUITE_SUBCOMMANDS = frozenset({"test", "nextest", "llvm-cov"})


def _segments(command: str) -> list[str]:
    """Split a command at the separators outside quotes, escapes and comments."""
    segments = [""]
    for token in TOKENS.finditer(command):
        if token.lastgroup == "separator":
            segments.append("")
        elif token.lastgroup == "text":
            segments[-1] += token.group()
        elif token.lastgroup == "continuation":
            segments[-1] += " "
    return segments


def _is_assignment(word: str) -> bool:
    """Report whether a word is a leading ``NAME=value`` assignment."""
    return "=" in word and not word.startswith("-")


def _without_assignments(words: list[str]) -> list[str]:
    """Return the words from the first one that is not an assignment."""
    while words and _is_assignment(words[0]):
        words = words[1:]
    return words


def _words(segment: str) -> list[str]:
    """Split one segment into words as the shell would, less assignments."""
    try:
        words = shlex.split(segment, comments=True)
    except ValueError:
        words = segment.split()
    return _without_assignments(words)


def _operands(words: list[str], value_options: frozenset[str]) -> list[str]:
    """Return a command's operands: its words less options and their values."""
    found: list[str] = []
    skip = False
    for word in words:
        if skip:
            skip = False
        elif word in value_options:
            skip = True
        elif not word.startswith(("-", "+")) and "=" not in word:
            found.append(word)
    return found


def _unwrap(words: list[str]) -> list[str]:
    """Strip an ``env`` wrapper, with its options and assignments."""
    program = words[0].rsplit("/", 1)[-1] if words else ""
    if program != "env":
        return words
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in ENV_VALUE_OPTIONS else 1
    return _unwrap(_without_assignments(words[index:]))


def _segment_runs_suite(segment: str) -> bool:
    """Report whether one shell segment runs the suite."""
    words = _unwrap(_words(segment))
    if not words:
        return False
    program = words[0].rsplit("/", 1)[-1]
    if program == "cargo":
        operands = _operands(words[1:], CARGO_VALUE_OPTIONS)
        return bool(operands) and operands[0] in SUITE_SUBCOMMANDS
    if program != "make":
        return False
    targets = _operands(words[1:], MAKE_VALUE_OPTIONS)
    return not targets or bool(SUITE_TARGETS & set(targets))


def runs_suite(command: str) -> bool:
    """Report whether a shell command runs the suite, in any spelling.

    Parameters
    ----------
    command : str
        A workflow step's ``run`` text, which may span several lines.

    Returns
    -------
    bool
        True when any segment runs ``cargo test``, ``cargo nextest`` or
        ``cargo llvm-cov``, or runs ``make`` with no target or with a suite target.

    Examples
    --------
    >>> runs_suite("make lint&&make test")
    True
    >>> runs_suite("echo cargo test")
    False
    """
    return any(_segment_runs_suite(part) for part in _segments(command))
