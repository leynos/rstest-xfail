"""Contract tests for the Rust build standard.

The standard makes the parallel ``rustc`` frontend the default for every
development build and mold the default linker on Linux. Cargo reads both from
``.cargo/config.toml``, but it applies a single ``rustflags`` source rather
than merging them, and an assigned ``RUSTFLAGS`` replaces every source. So the
flags must be repeated in each configuration source, restated wherever the
Makefile assigns ``RUSTFLAGS`` for a gate target, and kept out of the coverage
and release recipes, which measure or ship and so stay on the default flags.

The Makefile clauses are checked by running ``make -n`` and reading the
commands it would run, rather than by reading the Makefile's text, so a flag
lost through a variable or a recipe edit fails here.

Run via ``make test-workflow-contracts``.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
THREADS_FLAG = "-Zthreads=8"
MOLD_FLAG = "-Clink-arg=-fuse-ld=mold"
LINUX_TABLES = {"x86_64-unknown-linux-gnu", 'cfg(target_os = "linux")'}
RUSTFLAGS_RE = re.compile(r'RUSTFLAGS="([^"]*)"')


def _normalized(flags: list[str]) -> list[str]:
    """Join ``-C value`` pairs into ``-Cvalue`` so spellings compare equal."""
    joined: list[str] = []
    for flag in flags:
        if joined and joined[-1] == "-C":
            joined[-1] = f"-C{flag}"
        else:
            joined.append(flag)
    return joined


def _sources() -> dict[str, list[str]]:
    """Return every ``rustflags`` source in the configuration, by table."""
    config = tomllib.loads((ROOT / ".cargo" / "config.toml").read_text("utf-8"))
    sources = {"build": config.get("build", {}).get("rustflags")}
    for key, table in config.get("target", {}).items():
        sources[key] = table.get("rustflags")
    return {key: _normalized(flags) for key, flags in sources.items() if flags}


def _make_commands(target: str) -> list[str]:
    """Return the commands ``make -n TARGET`` prints, continuations joined."""
    result = subprocess.run(
        ["make", "-n", "-B", "BUILD_HOST_OS=Linux", target],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    # A recipe continued with a trailing backslash is one command.
    return result.stdout.replace("\\\n", " ").splitlines()


def _runs_whitaker(line: str) -> bool:
    """Return whether the command executes Whitaker, past ``env`` and assignments."""
    words = shlex.split(line)
    index = 0
    while index < len(words):
        word = words[index]
        if word == "env":
            index += 1
        elif word == "-u":
            index += 2
        elif re.match(r"[A-Za-z_][A-Za-z0-9_]*=", word):
            index += 1
        else:
            return word.rsplit("/", 1)[-1] == "whitaker"
    return False


def _make_rustflags(target: str) -> list[list[str]]:
    """Return the ``RUSTFLAGS`` each Cargo command of ``make -n TARGET`` assigns.

    Whitaker is not a Cargo gate build: its installer-managed toolchain takes
    none of the development flags, so its route is held to its own test.
    """
    return [
        shlex.split(match.group(1))
        for line in _make_commands(target)
        if "cargo" in line and not _runs_whitaker(line)
        for match in [RUSTFLAGS_RE.search(line)]
        if match
    ]


def test_every_rustflags_source_carries_the_parallel_frontend() -> None:
    """Cargo applies one source, so each must name the flag itself."""
    sources = _sources()
    assert "build" in sources, "no [build] rustflags for non-Linux hosts"
    missing = [key for key, flags in sources.items() if THREADS_FLAG not in flags]
    assert missing == [], f"{THREADS_FLAG} missing from {missing}"


def test_mold_is_confined_to_linux() -> None:
    """mold ships for Linux only; a wider source would break other hosts."""
    sources = _sources()
    linux = [key for key in sources if key in LINUX_TABLES]
    assert linux, "no Linux target table carries rustflags"
    assert all(MOLD_FLAG in sources[key] for key in linux), "Linux lost mold"
    wider = [
        key
        for key, flags in sources.items()
        if key not in LINUX_TABLES and MOLD_FLAG in flags
    ]
    assert wider == [], f"mold named beyond Linux in {wider}"


def test_sources_differ_only_by_the_linker() -> None:
    """A flag named in one source and not another vanishes on some host."""
    stripped = {
        tuple(f for f in flags if f != MOLD_FLAG) for flags in _sources().values()
    }
    assert len(stripped) == 1, f"rustflags sources disagree: {stripped}"


@pytest.mark.parametrize("target", ["test", "typecheck"])
def test_gate_targets_restate_both_flags(target: str) -> None:
    """An assigned RUSTFLAGS replaces the configuration's sources."""
    assignments = _make_rustflags(target)
    assert assignments, f"`make {target}` assigns no RUSTFLAGS"
    for flags in assignments:
        assert THREADS_FLAG in flags, f"`make {target}` drops {THREADS_FLAG}: {flags}"
        assert MOLD_FLAG in flags, f"`make {target}` drops {MOLD_FLAG}: {flags}"


@pytest.mark.parametrize("target", ["coverage", "release"])
def test_coverage_and_release_take_neither_flag(target: str) -> None:
    """Coverage measures and release ships, so both stay on default flags.

    Each must also assign RUSTFLAGS, since only an assignment displaces the
    configuration's sources.
    """
    assignments = _make_rustflags(target)
    assert assignments, (
        f"`make {target}` assigns no RUSTFLAGS, so it takes the configuration's"
    )
    for flags in assignments:
        assert THREADS_FLAG not in flags, f"`make {target}` takes {THREADS_FLAG}"
        assert MOLD_FLAG not in flags, f"`make {target}` takes {MOLD_FLAG}"


def test_coverage_recipe_selects_llvm() -> None:
    """Instrumentation needs LLVM, and the dev profile defaults to Cranelift.

    So the ``cargo llvm-cov`` command itself must select LLVM, or coverage would
    inherit the Cranelift default from ``.cargo/config.toml``.
    """
    result = subprocess.run(
        ["make", "-n", "-B", "BUILD_HOST_OS=Linux", "coverage"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    commands = result.stdout.replace("\\\n", " ").splitlines()
    coverage = [line for line in commands if "llvm-cov" in line]
    assert coverage, "`make coverage` runs no cargo llvm-cov command"
    for line in coverage:
        assert "CARGO_PROFILE_DEV_CODEGEN_BACKEND=llvm" in line, line


def test_the_whitaker_route_is_isolated() -> None:
    """Whitaker clears inherited flag sources and assigns its own.

    Its toolchain must not inherit the development flags. An unset
    ``RUSTFLAGS`` would leave Cargo reading the configuration's ``rustflags``,
    so the route assigns the warning policy alone, clears the encoded flags that
    Cargo prefers, displaces the Cranelift development profile with LLVM, and
    opts the temporary project where Dylint builds its driver into the backend
    key.
    """
    routes = [line for line in _make_commands("lint") if _runs_whitaker(line)]
    assert routes, "`make lint` runs no Whitaker command"
    for route in routes:
        words = shlex.split(route)
        removed = {words[i + 1] for i, word in enumerate(words[:-1]) if word == "-u"}
        assert "CARGO_ENCODED_RUSTFLAGS" in removed, f"encoded flags not cleared: {route}"
        assigned = dict(
            word.split("=", 1) for word in words if re.match(r"[A-Z_]+=", word)
        )
        assert assigned.get("RUSTFLAGS") == "-D warnings", (
            f"Whitaker must assign the warning policy alone: {route}"
        )
        assert assigned.get("CARGO_PROFILE_DEV_CODEGEN_BACKEND") == "llvm", (
            f"Whitaker must displace the Cranelift development profile: {route}"
        )
        assert assigned.get("CARGO_UNSTABLE_CODEGEN_BACKEND") == "true", (
            f"Whitaker's driver build needs the backend key: {route}"
        )
