"""Recognize shell commands that run the Rust or Python test suite.

The suite-once contract needs to know whether a workflow line runs the suite
outside the coverage action. A substring check is both too wide (``echo
pytest``) and too narrow (``make "test"``, ``make lint&&make test``), so a
command is split into segments at the shell separators that sit outside quotes,
escapes and comments. Each segment is split into words as the shell would, and
the program it runs is read before its arguments. Control words such as
``then`` and wrappers such as ``env``, ``timeout``, ``uv run`` and
``python -m`` are looked through, and the string after ``sh -c`` or
``bash -c`` is read as a command of its own.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from pathlib import PurePosixPath

#: Make options that take their value as the next word.
MAKE_VALUE_OPTIONS = frozenset(
    {"-C", "-f", "-I", "-o", "-W", "--directory", "--file", "--makefile"}
)
#: Make targets that run the suite: ``test``, ``all`` (which runs it),
#: ``coverage`` and the fast local variants. A bare ``make`` runs the default
#: goal, ``all``, so it counts too.
SUITE_TARGETS = frozenset({"test", "all", "coverage", "dev-test", "test-fast"})
#: ``uv run`` and ``uvx`` options that take their value as the next word.
UV_VALUE_OPTIONS = frozenset(
    {"--with", "--python", "-p", "--group", "--extra", "--from", "--project"}
)
#: Wrappers that run the command after their own options, mapped to the
#: options that take a value and the operands they read before the command.
WRAPPERS: dict[str, tuple[frozenset[str], int]] = {
    "env": (frozenset({"-u", "--unset", "-C", "--chdir"}), 0),
    "timeout": (frozenset({"-s", "--signal", "-k", "--kill-after"}), 1),
    "nice": (frozenset({"-n", "--adjustment"}), 0),
    "command": (frozenset(), 0),
    "exec": (frozenset({"-a"}), 0),
}
#: Reserved words that open or continue a compound command; the command
#: they introduce follows them in the same segment.
CONTROL_WORDS = frozenset(
    {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "time"}
)
#: Shells whose ``-c`` operand is itself a command.
SHELLS = frozenset({"sh", "bash"})
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
#: Python interpreters by name: ``python``, ``python3`` and ``python3.13``.
PYTHON_PROGRAM = re.compile(r"python(?:3(?:\.\d+)?)?")
#: Programs that are pytest itself.
PYTEST_PROGRAMS = frozenset({"pytest", "py.test"})
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
    """Split one segment into words as the shell would, less assignments.

    Comments were dropped when the command was segmented, so a ``#`` left here
    sits inside a word, as in ``make test#notes``, and stays part of it.
    """
    try:
        words = shlex.split(segment, comments=False)
    except ValueError:
        words = segment.split()
    if words:
        # A subshell's parentheses open its first segment and close its last.
        words[0] = words[0].lstrip("(")
        words[-1] = words[-1].rstrip(")")
    return _without_assignments([word for word in words if word])


def _program(words: list[str]) -> str:
    """Return the name of the program a word list runs, without its directory."""
    return PurePosixPath(words[0]).name if words else ""


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


def _after_options(words: list[str], value_options: frozenset[str]) -> list[str]:
    """Return the words from the first operand on."""
    index = 0
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in value_options else 1
    return words[index:]


def _past_control_word(words: list[str]) -> list[str] | None:
    """Return the command after a leading reserved word such as ``then``."""
    return words[1:] if _program(words) in CONTROL_WORDS else None


def _past_wrapper(words: list[str]) -> list[str] | None:
    """Return the command a wrapper such as ``env`` or ``timeout`` runs."""
    wrapper = WRAPPERS.get(_program(words))
    if wrapper is None:
        return None
    value_options, leading_operands = wrapper
    after = _after_options(words[1:], value_options)[leading_operands:]
    return _without_assignments(after)


def _past_uv(words: list[str]) -> list[str] | None:
    """Return the command ``uv run`` or ``uvx`` runs."""
    program = _program(words)
    if program == "uv" and words[1:2] == ["run"]:
        return _after_options(words[2:], UV_VALUE_OPTIONS)
    if program == "uvx":
        return _after_options(words[1:], UV_VALUE_OPTIONS)
    return None


def _past_python_module(words: list[str]) -> list[str] | None:
    """Return the module command ``python -m`` runs."""
    is_module_run = words[1:2] == ["-m"]
    return (
        words[2:]
        if PYTHON_PROGRAM.fullmatch(_program(words)) and is_module_run
        else None
    )


#: Readers that each look through one kind of prefix to the command behind it.
UNWRAPPERS: tuple[Callable[[list[str]], list[str] | None], ...] = (
    _past_control_word,
    _past_wrapper,
    _past_uv,
    _past_python_module,
)


def _unwrap(words: list[str]) -> list[str]:
    """Strip every control word and wrapper in front of the command."""
    for unwrapper in UNWRAPPERS:
        inner = unwrapper(words)
        if inner is not None:
            return _unwrap(inner)
    return words


def _cargo_runs_suite(arguments: list[str]) -> bool:
    """Report whether cargo's arguments name a suite-running subcommand."""
    operands = _operands(arguments, CARGO_VALUE_OPTIONS)
    return bool(operands) and operands[0] in SUITE_SUBCOMMANDS


def _make_runs_suite(arguments: list[str]) -> bool:
    """Report whether make's arguments run the default goal or a suite target."""
    targets = _operands(arguments, MAKE_VALUE_OPTIONS)
    return not targets or bool(SUITE_TARGETS & set(targets))


def _shell_runs_suite(arguments: list[str]) -> bool:
    """Report whether ``sh -c`` or ``bash -c`` is given a suite-running command."""
    if "-c" not in arguments:
        return False
    script = arguments[arguments.index("-c") + 1 :][:1]
    return bool(script) and runs_suite(script[0])


def _pytest_runs_suite(_arguments: list[str]) -> bool:
    """Report that pytest runs the suite, whatever its arguments."""
    return True


#: What each suite-capable program's arguments must say for it to run the suite.
READERS: dict[str, Callable[[list[str]], bool]] = {
    "cargo": _cargo_runs_suite,
    "make": _make_runs_suite,
    **dict.fromkeys(SHELLS, _shell_runs_suite),
    **dict.fromkeys(PYTEST_PROGRAMS, _pytest_runs_suite),
}


def _segment_runs_suite(segment: str) -> bool:
    """Report whether one shell segment runs the suite."""
    words = _unwrap(_words(segment))
    reader = READERS.get(_program(words))
    return reader is not None and reader(words[1:])


def runs_suite(command: str) -> bool:
    """Report whether a shell command runs the suite, in any spelling.

    Parameters
    ----------
    command : str
        A workflow step's ``run`` text, which may span several lines.

    Returns
    -------
    bool
        True when any segment runs pytest, ``cargo test``, ``cargo nextest``
        or ``cargo llvm-cov``, or runs ``make`` with no target or a suite
        target, directly or through a control word, wrapper or ``sh -c``.

    Examples
    --------
    >>> runs_suite("if true; then make test; fi")
    True
    >>> runs_suite("echo 'pre;make test;post'")
    False
    """
    return any(_segment_runs_suite(part) for part in _segments(command))
