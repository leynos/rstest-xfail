# Repository layout

This document describes the generated rstest-xfail repository layout. It is the
canonical reference for where source code, tests, configuration, automation,
and long-lived documentation belong.

## Top-level tree

The tree below shows the generated repository structure. It is intentionally
compact and omits build output such as `target/`.

```plaintext
.
├── .cargo/
│   └── config.toml
├── .github/
│   ├── dependabot.yml
│   └── workflows/
│       ├── act-validation.yml
│       ├── ci.yml
├── crates/
│   ├── rstest-xfail/
│   │   ├── Cargo.toml
│   │   ├── src/
│   │   │   └── lib.rs
│   │   └── tests/
│   │       ├── public_surface.rs
│   │       ├── snapshots/
│   │       ├── stub.rs
│   │       └── workspace_members.rs
│   ├── rstest-xfail-core/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       └── lib.rs
│   └── rstest-xfail-macros/
│       ├── Cargo.toml
│       └── src/
│           └── lib.rs
├── docs/
│   ├── contents.md
│   ├── developers-guide.md
│   ├── roadmap.md
│   ├── repository-layout.md
│   ├── terms-of-reference.md
│   ├── users-guide.md
│   ├── xfail-design.md
│   └── ...
├── scripts/
│   ├── tests/
│   │   └── test_typos_rollout_check.py
│   └── typos_rollout_check.py
├── tests/
│   └── workflow_contracts/
│       └── mutation_testing_test.py
├── AGENTS.md
├── Cargo.toml
├── LICENSE
├── Makefile
├── README.md
├── clippy.toml
├── codecov.yml
├── rust-toolchain.toml
├── typos.local.toml
└── typos.toml
```

## Path responsibilities

- `.cargo/config.toml`: Configures Cargo defaults for local development,
  including Linux linker and code-generation settings.
- `.github/dependabot.yml`: Configures automated dependency update checks.
- `.github/workflows/act-validation.yml`: Runs the generated workflow
  validation through `act` separately from main CI.
- `.github/workflows/ci.yml`: Runs the generated project's continuous
  integration checks.

- `docs/`: Holds long-lived reference documentation, guides, style rules, and
  design material.
- `docs/contents.md`: Indexes the documentation set and should be updated when
  documentation files are added, renamed, or removed.
- `docs/terms-of-reference.md`: Defines the problem space, scope boundaries,
  users, constraints, and open questions for rstest-xfail.
- `docs/xfail-design.md`: Specifies the expected-failure macro architecture,
  core classifier contract, async boundary, and rstest-bdd integration model.
- `docs/roadmap.md`: Breaks the design into sequenced, review-sized delivery
  work.
- `docs/users-guide.md`: Explains how to use the generated project and its
  public build and test commands.
- `docs/developers-guide.md`: Explains the contributor workflow and local
  tooling used to work on the generated project.
- `docs/repository-layout.md`: Documents the repository tree and path
  responsibilities.

- `crates/rstest-xfail-core/`: The domain core crate. It owns the outcome and
  policy vocabulary and the runtime classification functions (roadmap 1.2.x)
  and must stay a pure leaf with no dependency on the sibling crates or on
  procedural-macro tooling (constraint D1).
- `crates/rstest-xfail-macros/`: The procedural-macro crate. It parses
  `#[xfail(...)]` and rewrites functions (roadmap 2.1.x).
- `crates/rstest-xfail/`: The facade crate. It re-exports the public surface
  intended for ordinary users (`rstest_xfail::xfail` at task 1.1.1) and owns
  the integration tests that document that surface and the workspace member
  contract.

- `scripts/typos_rollout_check.py`: Enforces exact phrase corrections that the
  token-based Typos scanner cannot represent.
- `scripts/tests/test_typos_rollout_check.py`: Holds the focused phrase-scanner
  tests.

- `tests/`: Holds black-box workflow-contract tests that are not owned by a
  single crate (currently `workflow_contracts/`).
- `AGENTS.md`: Provides repository-specific working instructions for agents and
  contributors.
- `Cargo.toml`: The virtual workspace manifest. It owns no source code; it
  declares the `crates/` members, `resolver = "3"`, shared package metadata,
  shared workspace dependencies, and the inherited lint policy.
- `LICENSE`: Records the project licence text.
- `Makefile`: Provides the public build, lint, test, coverage, and
  documentation validation commands.
- `README.md`: Introduces the project and gives the shortest useful
  getting-started path.
- `clippy.toml`: Configures Clippy lint behaviour that is not expressed
  directly in `Cargo.toml`.
- `codecov.yml`: Configures coverage reporting behaviour.
- `rust-toolchain.toml`: Pins the Rust toolchain channel and required
  components.
- `typos.local.toml`: Holds narrow repository-specific spelling policy.
- `typos.toml`: Provides the generated en-GB-oxendict configuration consumed by
  the pinned spelling gate.

## Ownership boundaries

- Keep each crate's source under its `crates/*/src/` tree. Add modules below a
  crate root when a feature grows beyond a small entrypoint or crate root.
- Keep black-box integration tests that exercise a crate's public surface under
  that crate's `tests/` directory (for example `crates/rstest-xfail/tests/`).
  Keep externally observable workflow tests that span crates under `tests/`.
- Keep reusable documentation under `docs/`. Update `docs/contents.md` whenever
  a documentation file is added, renamed, or removed.
- Keep build and validation entrypoints in `Makefile`; prefer adding or
  extending a Make target over documenting an ad hoc command.
- Keep continuous integration workflow changes under `.github/workflows/` and
  dependency-update policy under `.github/dependabot.yml`.
- Do not commit generated build output such as `target/`, coverage artefacts,
  or local editor state.
- Keep the core crate free of dependency edges to the facade, the macros crate,
  and procedural-macro tooling (constraint D1, enforced by
  `crates/rstest-xfail/tests/workspace_members.rs`).

## Updating this document

Update this document when the repository gains a new top-level directory, a new
long-lived documentation category, a new workflow file, or a changed ownership
boundary that would otherwise make the tree misleading.
