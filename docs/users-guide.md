# User Guide

This guide explains how to use the generated rstest-xfail project after
rendering it from the template.

## Generated Tooling

Generated projects use Rust 2024, a pinned nightly toolchain, strict lint
settings, and documented starter code. Library projects render a library crate
root. Application projects render `src/main.rs`, a library crate root, release
automation, and `[package.metadata.binstall]` metadata for binary installation.

A rendered project is a Cargo workspace. This repository renders the library
form, so the code lives under `crates/`, not at a root `src/`: the facade crate
`crates/rstest-xfail/` re-exports the public surface,
`crates/rstest-xfail-core/` holds the domain vocabulary, and
`crates/rstest-xfail-macros/` holds the procedural macros. Those three crate
roots are placeholder stubs until the vocabulary (roadmap 1.2.x) and the macro
(roadmap 2.1.x) land. To work on a single crate, pass `-p <crate>` to `cargo`.
See [repository layout](repository-layout.md) for the full tree.

Development builds use Cranelift for debug code generation. On Linux targets,
`.cargo/config.toml` configures clang to link with `mold` so local debug builds
link quickly. Coverage generation uses `lld` instead because LLVM coverage
tools expect LLVM-compatible linker behaviour.

## Expected-failure policy (planned version 1)

The `#[xfail(reason = "...")]` marker is planned for version 1. The three crate
roots are still placeholders, so the marker is not implemented or enforced yet;
this section records the policy those crates will follow.

An expected failure (XFAIL) means the test body ran and failed in an allowed
way. An unexpected pass (XPASS) means a body marked as expected to fail passed
instead, usually because its bug was fixed.

- Strict XPASS is the default. A passing body under `#[xfail]` fails the test,
  and therefore the suite, until the marker is removed.
- `#[xfail(reason = "BUG-123", strict = false)]` is an explicit, per-test
  opt-out. The body still runs, the result is still classified and reported as
  XPASS, but the marked test does not fail. There is no global or environment
  setting for this.
- A failure that does not match the configured mode or `contains` condition is
  an unexpected failure. It fails the test under both settings.

Warning for Continuous Integration (CI) users: with `strict = false`, a test
that starts passing can leave CI green when no other test fails, and it keeps a
stale expected-failure marker. A green suite is not evidence that the marked
bug still exists. Prefer the strict default, and treat opted-out markers as
cleanup debt. The harness may also hide diagnostics from successful tests, so
an XPASS report is not guaranteed to appear in the log.

See [ADR 0003](adrs/adr-0003-strict-xpass-default-and-non-strict-policy.md) for
the decision and [technical design](xfail-design.md) §7 for the planned macro
arguments.

## Makefile Targets

The generated `Makefile` exposes these public targets:

- `make all` runs formatting checks, linting, and tests.
- `make check-fmt` verifies Rust formatting.
- `make lint` runs rustdoc, Clippy, and Whitaker with warnings denied.
- `make test` runs `cargo nextest run` when cargo-nextest is installed and
  falls back to `cargo test` otherwise. All projects also run doctests.
- `make build` builds the debug target.
- `make release` builds the release target.
- `make coverage` writes `lcov.info` using `cargo llvm-cov` and `lld`.
- `make audit` derives the Rust workspace root with `cargo metadata` and runs
  `cargo audit` once from that root.
- `make markdownlint` checks Markdown files.
- `make nixie` validates Mermaid diagrams.

Install `clang`, `lld`, `mold`, `python3`, and `cargo-audit` before running the
full generated workflow locally on Linux.
