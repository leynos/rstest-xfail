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
