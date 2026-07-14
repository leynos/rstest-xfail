# Developer Guide

This guide explains the contributor workflow for the generated rstest-xfail
project.

## Normative references

Read
[terms of reference](terms-of-reference.md), [technical design](xfail-design.md),
and [roadmap](roadmap.md) before changing rstest-xfail architecture or
delivery scope. These documents define the problem boundaries, expected-failure
classification model, `rstest-bdd` ownership handoff, and implementation
sequence.

## Local Workflow

Use `make all` as the public entrypoint for formatting, linting, and tests.
`make lint` runs rustdoc, Clippy, and Whitaker. `make test` prefers
`cargo nextest run` and falls back to `cargo test` when cargo-nextest is not
available. `make audit` derives the Rust workspace root with `cargo metadata`,
logs workspace member manifests, and runs `cargo audit` once from the workspace
root. `make coverage` uses `cargo llvm-cov` with `lld`.

GitHub Actions Act validation lives in `.github/workflows/act-validation.yml`.
The main `.github/workflows/ci.yml` workflow deliberately does not run
`make test WITH_ACT=1`; the separate Act workflow runs those slower
container-backed checks in parallel.

## Tooling

Development builds use Cranelift for debug code generation. On Linux targets,
`.cargo/config.toml` configures clang to link with `mold` so debug builds link
quickly. Coverage generation uses `lld` because LLVM coverage tooling expects
LLVM-compatible linker behaviour.

Install `clang`, `lld`, `mold`, `python3`, and `cargo-audit` before running the
full generated workflow locally on Linux.

Whitaker is the df12 Productions opinionated lint suite used by `make lint`.
See the [Whitaker user's guide](whitaker-users-guide.md) for installation,
configuration, and local invocation details.

Lading is the df12 Productions release helper for Cargo workspaces. See the
[Lading user guide](lading-users-guide.md) for version bumping, publication
planning, and workspace publishing workflows.

`rstest-bdd` is a behaviour-driven development extension to `rstest` that runs
Gherkin-backed tests through Rust's standard test infrastructure. See the
[`rstest-bdd` user's guide](rstest-bdd-users-guide.md) for fixture integration,
scenario bindings, and supported testing patterns.

### Spelling policy

Run `make spelling` to enforce en-GB-oxendict prose spelling. The tracked
`typos.toml` starts from the shared estate dictionary and applies the narrow
repository policy in `typos.local.toml`. Edit the local policy, then run
`make spelling-config` rather than changing generated entries by hand. The
focused shared config builder refreshes its untracked local dictionary cache
only when the authoritative copy is newer.

### Security audit ignores

Security audit jobs may set `CARGO_AUDIT_IGNORES` for narrowly scoped RustSec
advisories that affect unused or tooling-only dependency paths. Keep each
ignore tied to a documented runtime impact analysis, and remove it when the
affected dependency leaves the graph or the project starts using the advised
runtime path.

### Workflow pins and Dependabot

Dependabot owns the upgrade of GitHub Actions and reusable workflows,
including calls into `leynos/shared-actions`. Contract tests that assert a
caller's exact commit SHA create a lockstep dependency: every time Dependabot
opens a bump PR, the test fails until a human edits the pinned constant to
match. That defeats the purpose of automated dependency updates and turns a
routine bump into a manual chore.

Contract tests may still verify the *shape* of a reusable-workflow caller.
They must not verify the specific SHA value.

- Do assert the workflow references the correct reusable workflow path.
- Do assert the ref is pinned to a full 40-character commit SHA, not a
  mutable branch such as `main` or `rolling`.
- Do assert the expected `on:` triggers, least-privilege `permissions:`, and
  the inputs the caller relies on.
- Do not hard-code the current SHA value as an expected string. Match it with
  a pattern instead.
- Do not fail a test purely because Dependabot bumped the pinned SHA.

```python
import re

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def test_uses_pinned_full_sha(caller_step):
    ref = caller_step["uses"].split("@")[-1]
    assert SHA_RE.match(ref), f"expected a 40-hex commit SHA, got {ref!r}"
```

If a workflow's behaviour genuinely depends on a feature only present from a
particular commit onwards, express that as a comment or a changelog note, not
as a test assertion on the SHA string.
