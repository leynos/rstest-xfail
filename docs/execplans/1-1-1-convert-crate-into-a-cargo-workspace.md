# Convert the crate into a Cargo workspace (1.1.1)

This ExecPlan (execution plan) is a living document. The sections `Constraints`,
`Tolerances`, `Risks`, `Progress`, `Surprises & discoveries`, `Decision log`,
and `Outcomes & retrospective` must be kept up to date as work proceeds.

Status: COMPLETE

This plan delivers roadmap task **1.1.1** (see [roadmap](../roadmap.md) §1.1).
It converts the single-package `rstest-xfail` crate into a three-crate Cargo
workspace. It does **not** implement the classifier vocabulary (roadmap 1.2.x),
the `#[xfail]` macro behaviour (roadmap 2.1.x), or the strictness and async
Architecture Decision Records (roadmap 1.1.2 and 1.1.3). Those are separate
tasks and are explicitly out of scope.

## Signposts: documents and skills

Read these before starting. They are the source of truth for this work.

- [Technical design](../xfail-design.md) §§5-6 — the three-crate architecture
  and the core crate contract this plan realizes.
- [Roadmap](../roadmap.md) §1.1.1 — the task definition and success criterion.
- [Repository layout](../repository-layout.md) — the canonical tree this plan
  updates.
- [Developer guide](../developers-guide.md) — the local workflow and `make`
  targets.
- [Documentation style guide](../documentation-style-guide.md) — spelling
  (en-GB-oxendict), Markdown rules, and ADR conventions used here.
- [AGENTS.md](../../AGENTS.md) — code style, testing mandate, dependency
  policy, and commit gates.

Relevant skills (load with the `rust-router` skill as the entry point):

- `arch-crate-design` — crate boundaries, workspace structure, feature flags,
  public versus internal surface.
- `arch-decision-records` — the format for the workspace boundary decision.
- `rust-unit-testing` — `rstest` fixtures, table tests, `serial_test`
  isolation, and rich assertions with `googletest`, `pretty_assertions`, and
  `insta`.
- `hexagonal-architecture` — to protect the core and adapter boundary without
  transplanting ceremony.
- `execplans` — the format and discipline this document follows.
- `pr-creation` — the draft pull-request conventions used to deliver this work.

## Purpose / big picture

After this change, the repository is a Cargo workspace with three member crates
rather than one package:

- `rstest-xfail-core` — the domain library that will own the outcome and
  policy vocabulary and the classification functions (design §6). It is pure:
  it depends on neither sibling crate nor on any procedural-macro tooling.
- `rstest-xfail-macros` — a procedural-macro crate that will parse `#[xfail]`
  and rewrite annotated functions (design §7). It is the driving adapter.
- `rstest-xfail` — the facade crate that users name in their manifest. It
  re-exports the `#[xfail]` attribute, and at this task nothing else (design
  §5).

At this task the three crates hold documented placeholders only. The observable
success is structural and is exactly the roadmap criterion: running
`cargo metadata` lists all three workspace members, and the facade re-exports
only the intended public surface. A reader can confirm both without inspecting
any implementation.

This split is the foundation for everything downstream. It is the single
decision that lets `rstest-bdd` consume classification semantics from
`rstest-xfail-core` without pulling in procedural-macro expansion machinery
(design §5).

## Constraints

Hard invariants. Violation requires escalation, not a workaround.

- **D1 — core purity.** `rstest-xfail-core` must not depend on
  `rstest-xfail-macros` or `rstest-xfail`, and must not list `proc-macro2`,
  `syn`, or `quote` among its dependencies, directly or through a feature. The
  dependency arrows point one way only: `rstest-xfail` depends on both
  siblings, and `rstest-xfail-macros` may depend on `rstest-xfail-core`. The
  core depends on neither. This is gated by an automated test (see Concrete
  steps), not only a manual command.
- **C-SURFACE-1 — placeholder surface only.** The facade re-exports only the
  placeholder `#[xfail]` attribute. The core exposes no public items at 1.1.1
  (only its crate-level documentation), so no fictitious type is locked into
  the public surface. No classifier types, no macro argument parsing or
  function rewriting. Every module begins with a `//!` comment and every public
  item carries `///` docs, because the inherited `missing_docs` and
  `missing_crate_level_docs` lints are set to `deny`.
- **C-DEPS-1 — no new runtime dependencies.** This task adds only *path*
  dependencies between the three members. No new crates.io *runtime* dependency
  enters any manifest. Test-only `dev-dependencies` (such as `rstest`, `insta`,
  `serde_json`, `serial_test`, and the `cap-std`/`camino` pair the surface test
  reads the facade source through) are expected and permitted. Any new
  dependency uses a caret requirement (AGENTS.md "Dependency management").
- **C-LINTS-1 — lint policy preserved.** The current lint tables move into
  `[workspace.lints]` with zero net change to the enforced lint set, and every
  member sets `[lints] workspace = true`. `clippy.toml` stays at the workspace
  root, unchanged.
- **C-GREEN-1 — toolchain unchanged.** `rust-toolchain.toml` is not bumped by
  this task. The commit gate passes on the existing pinned toolchain. The pin
  was `nightly-2026-05-28` when this plan was written; the rebase onto `main`
  brought `nightly-2026-10-11`, and the constraint holds for whichever pin the
  branch inherits.
- **C-SCOPE-1 — no downstream redesign.** Do not implement classifier types
  (1.2.x), macro behaviour (2.1.x), or the strictness and async ADRs (1.1.2,
  1.1.3). Do not restructure `docs/roadmap.md` beyond ticking the 1.1.1
  checkbox on completion.

## Tolerances (exception triggers)

Thresholds that trigger escalation. These bound autonomous action; they are not
quality criteria.

- **Scope.** Expect roughly three crate manifests, three crate roots, one
  virtual workspace manifest, the moved test, two new tests, the new ADR, and
  the documentation edits named below. If implementation requires net new
  source logic beyond documented placeholders, or touches more than the files
  listed in `Plan of work`, stop and escalate — logic leaking in from 1.2.x is
  a smell.
- **Interface.** The facade's intended public surface is fixed by this plan to
  the placeholder `#[xfail]` attribute re-exported from the macros crate. If a
  different surface seems necessary, stop and present options.
- **Dependencies.** If any *runtime* dependency (not a `dev-dependency`)
  appears necessary, stop and escalate (C-DEPS-1).
- **Iterations.** If the gate still fails after three focused attempts on the
  same cause, stop and escalate with the transcript.
- **Ambiguity.** If two valid interpretations materially change the outcome,
  stop and present them with trade-offs.

Stop-and-escalate triggers specific to this task:

- **T-STOP-1 (Cranelift).** If `rstest-xfail-macros` cannot build under the
  pinned nightly with the Cranelift codegen backend, and neither a per-package
  `codegen-backend` override nor an LLVM fallback resolves it without changing
  the toolchain or the continuous-integration (CI) Cranelift install, stop and
  escalate. Do not silently bump the toolchain or remove the Cranelift dev
  profile (Risk R1).
- **T-STOP-2 (lint regression).** If the `[workspace.lints]` migration cannot
  reproduce the current `cargo clippy --workspace` lint inventory exactly, stop
  and escalate rather than dropping a lint to make the build green (Risk R3).

## Risks

| Risk                                                                                                                                                                                                                                                                                                                                     | Severity | Likelihood | Mitigation                                                                                                                                                                                                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1. The Cranelift codegen backend cannot build the procedural-macro crate. `.cargo/config.toml` sets `[profile.dev] codegen-backend = "cranelift"` workspace-wide; procedural macros are host-compiled and Cranelift's procedural-macro coverage has historically lagged the LLVM backend. CI also installs Whitaker with `--cranelift`. | High     | Medium     | Validate a bare `proc-macro = true` crate under the pinned nightly first (Concrete steps, Stage B). On failure, scope the LLVM backend to only `rstest-xfail-macros` via `[profile.dev.package.rstest-xfail-macros] codegen-backend = "llvm"` in `.cargo/config.toml`. Escalate per T-STOP-1 if neither works.        |
| R2. `public-api` / `cargo-public-api` rustdoc-JSON incompatibility with the pinned nightly, if adopted for the surface test. The tool consumes nightly rustdoc JSON whose format is unstable and version-locked, and `nightly-2026-05-28` may not match a published tool version.                                                        | Medium   | Medium     | This plan does **not** adopt `cargo-public-api` for 1.1.1 (see Decision log). The surface is documented with a source-derived surface assertion, a lightweight reachability test, and an `insta` snapshot. A rigorous compiled-API surface and SemVer lock is deferred to the publishing-boundary roadmap item.       |
| R3. The lint-table migration to `[workspace.lints]` silently drops or mistypes a lint. The root manifest carries roughly fifty hand-maintained Clippy lines plus `[lints.rust]` and `[lints.rustdoc]`.                                                                                                                                   | Medium   | Medium     | Move the tables verbatim. Diff the pre- and post-migration `cargo clippy --workspace` inventory. Confirm each member manifest carries `[lints] workspace = true`; an omission means that crate silently runs with default lints. Escalate per T-STOP-2.                                                               |
| R4. The Makefile `TARGET` and `build`/`release` rules reference a moved or renamed artefact. `TARGET ?= librstest-xfail.rlib` assumes a single root library, and a hyphenated crate actually produces `librstest_xfail.rlib`.                                                                                                            | Medium   | High       | Repoint `TARGET` to `librstest_xfail.rlib` (the facade's artefact) and verify `make build`/`make release` produce it. The `test`, `coverage`, and `audit` targets already pass `--workspace` or derive the root from `cargo metadata` and need no change.                                                             |
| R5. The CI workflow assumes a single crate. `.github/workflows/ci.yml` drives everything through `make` (check-fmt, lint, audit, test, coverage).                                                                                                                                                                                        | Medium   | Low        | The Makefile targets already use `--workspace`/`--all-targets`, so CI inherits the R3/R4 fixes. Run the gate locally and confirm no workflow edit is needed; flag if the coverage action needs a workspace flag.                                                                                                      |
| R6. Placeholder churn when 1.2.x and 2.1.x replace the skeleton. Placeholder roots and the moved `tests/stub.rs` will be rewritten within one or two tasks.                                                                                                                                                                              | Low      | High       | Keep placeholders minimal and clearly marked disposable, mirroring the existing `tests/stub.rs` "delete this file" comment. Write no tests against placeholder *behaviour* beyond proving the no-op macro passes a body through; test only structure and reachability. Record that 1.2.1/2.1.1 must remove the stubs. |
| R7. Tests that shell out to `cargo metadata` from inside `cargo test`/`cargo nextest` contend on the package-cache lock and can stall or run nondeterministically under parallelism.                                                                                                                                                     | Medium   | Medium     | Use `cargo metadata --no-deps --offline` with `CARGO_NET_OFFLINE=1`, keep all metadata-spawning tests in one test binary, and serialize them with `serial_test`. If flakiness persists, consolidate the metadata read into a single fetch.                                                                            |

*Table 1: Anticipated risks, with severity, likelihood, and mitigation for the
workspace conversion.*

Risks differ from surprises: risks are anticipated here; surprises are recorded
below as they emerge.

## Progress

- [x] (2026-08-15 02:30Z) Stage A complete — signposted docs and skills read;
  manifest and surface design confirmed against the current tree.
- [x] (2026-08-15 03:35Z) Stage B complete — Cranelift procedural-macro spike
  passes under the pinned nightly; red tests authored and observed failing for
  the right reasons (`left: {"rstest-xfail"}` member-set diff and
  `unresolved import rstest_xfail::xfail`). See Surprises for the googletest
  form deviation.
- [x] (2026-08-15 04:45Z) Stage C complete — virtual workspace manifest, three
  member crates, and test relocations in place; `cargo metadata` lists exactly
  the three members, `make test` is green (8 tests plus doctests), and the
  Red-Green-Refactor evidence (member-set diff, unresolved import) has been
  replaced by passing assertions. Note: the root `tests/` directory stays
  because `tests/workflow_contracts/` (mutation-testing contract tests) is a
  separate, still-valid suite; only `stub.rs` and the new metadata/surface
  tests moved into `crates/rstest-xfail/tests/`.
- [x] (2026-08-15 05:10Z) Stage D complete — ADR-002 written; documentation
  updated (`repository-layout.md`, `developers-guide.md`, `contents.md`, and
  the §5 realization note in `xfail-design.md`); Makefile `TARGET` repointed;
  roadmap 1.1.1 checkbox ticked.
- [x] (2026-08-15 05:30Z) `coderabbit review --agent` run and all concerns
  cleared (0 findings across 20 reviewed files).
- [x] (2026-08-15 05:15Z) Roadmap 1.1.1 checkbox ticked in `docs/roadmap.md`
  (the `- [x] 1.1.1.` line).
- [x] (2026-08-15 05:45Z) Draft pull request #12 opened/updated with title
  `Convert the crate into a Cargo workspace (1.1.1)`, linking this execplan and
  roadmap §1.1.1; branch pushed (5 implementation commits).
- [x] (2026-10-12) Pull request #12 closed as superseded: its head predated the
  rebase onto `main`, so the branch could not be fast-forwarded.
- [x] (2026-10-12) Draft pull request #112 opened from
  `1-1-1-cargo-workspace-conversion` with the same title, entrypoints, and
  acceptance criteria, carrying the rebased history and the review revisions
  below. All six commit gates pass at its head commit.

Replace `(pending)` with a UTC timestamp as each row completes, for example
`- [x] (2026-06-24 14:00Z) Stage B complete.` Split any partially completed row
into "done" and "remaining" rows at a stopping point.

## Surprises & discoveries

Record unexpected findings here with evidence and impact as work proceeds. For
example, confirm the exact rlib artefact name with `ls target/debug/` after the
first `make build` rather than assuming it.

- **googletest matcher API differs from the reviewed snippets.** The plan's
  `verify_that!(names, contains(eq(...)))` snippets do not compile against the
  resolved googletest: its container matchers require `Copy` containers and
  items, `TestAssertionFailure` does not implement `std::error::Error`, and
  `?`-propagation from a `Result<_, Box<dyn Error>>` helper into a googletest
  `Result` fails. Resolved `dev-dependency` versions: `rstest 0.26.1`,
  `googletest 0.13.0` (pinned back from the default latest to match the plan's
  stated manifest), `pretty_assertions 1.4.1`, `insta 1.48.0`,
  `serde_json 1.0.151`, `serial_test 4.0.1`, `eyre 0.6.14`, plus the
  `cap-std 4.0.3` and `camino 1.2.6` pair the surface test reads the facade
  source through. Tests now use `assert_that!` (panic-style) in
  `Result`-returning tests and pass `&BTreeSet<String>` to `contains`; the
  exact-set test keeps `pretty_assertions`. The assertions' meaning is
  unchanged; this is a form deviation recorded here.
- **Cranelift procedural-macro spike confirms risk R1 is retired for this
  task.** A bare `proc-macro = true` crate plus a `#[proc_macro_attribute]`
  no-op built, and an integration test that expands and runs the attribute,
  passed under `nightly-2026-05-28` with the dev Cranelift profile. No LLVM
  fallback override was needed and none is added.
- **The whitaker dylint step is a fourth `make lint` recipe line, and a
  `lint` failure on an earlier line hides it.** The first full-gate run reported
  `lint` as one failed row, which read as "clippy failed". Clippy had in fact
  failed and aborted the target, so the `whitaker --all` dylint pass never ran
  at all; its status was unobserved, not failing. Once clippy was fixed,
  whitaker found three diagnostics that clippy cannot see, because it runs a
  different toolchain and a different lint set: two `no_std_fs_operations`
  errors (a `std::fs` import and a `fs::read_to_string`), and one
  `conditional_max_n_branches`. Record per-recipe-line outcomes for
  `make lint`, not one verdict for the target. The `no_std_fs_operations`
  denial is also why the facade surface test reads its own source through
  `cap_std::fs::Dir` and `camino::Utf8Path` rather than `std::fs`, which
  required adding that pair as `dev-dependencies`.

## Decision log

- Decision: Use a **virtual workspace manifest** at the repository root with
  members under `crates/`. Rationale: the three crates are peers; none should
  own the root. Making the facade the root package would force the core and
  macros crates into sub-paths of the facade, which is misleading because the
  core has no dependency on the facade. A virtual manifest keeps the root free
  of package identity. The `crates/` directory is the conventional uniform home
  and matches the generic `cargo metadata` walk already used by `make audit`.
  Date/Author: 2026-06-24, planning team.
- Decision: **Expose no public item from `rstest-xfail-core` at 1.1.1**; the
  facade re-exports only the placeholder `#[xfail]` attribute. Rationale:
  design §14 lists "whether the facade re-exports all core types or only stable
  policy constructors" as an open question. Inventing a placeholder core type
  to re-export would prejudge that decision and lock a meaningless item into
  the public surface that the snapshot test then advertises as the contract.
  The roadmap criterion's "intended public surface" at 1.1.1 is the `#[xfail]`
  attribute alone. The facade consequently declares a dependency only on
  `rstest-xfail-macros`; the path dependency on `rstest-xfail-core` is deferred
  to roadmap 1.2.x, when the core first exposes items the facade can re-export
  (revised after review, see Post-review revisions). Date/Author: 2026-06-24,
  planning team and review panel.
- Decision: Ship a **no-op `#[xfail]` placeholder attribute** in the macros
  crate, and prove it passes a body through unchanged. Rationale: `#[xfail]` is
  the facade's intended surface, and a `proc-macro = true` crate must export a
  macro to be exercised at all. A no-op also de-risks R1. The design forbids a
  rewritten body from ever masking its real outcome, so the placeholder test
  annotates a function with an observable body and asserts the body still runs,
  proving the no-op does not absorb the outcome. Argument parsing remains
  deferred to 2.1.1. Date/Author: 2026-06-24, planning team and review panel.
- Decision: Document the facade surface with a **lightweight reachability test
  plus an `insta` snapshot**, not `cargo-public-api`. Rationale:
  `cargo-public-api` consumes nightly rustdoc JSON whose format is
  version-locked, and the repository pins a specific nightly; coupling a
  published tool version to that nightly is brittle for a surface of one
  placeholder attribute. **Revised during implementation:** the snapshot alone
  records intent but cannot detect an unintended export, so the shipped test
  additionally *derives* the exported names from the facade's own `src/lib.rs`
  and asserts them against `INTENDED_PUBLIC_SURFACE` before snapshotting. The
  remaining limitation is narrower and stated in the test: the derivation reads
  source, not compiled metadata. A rigorous compiled-API surface and SemVer
  lock belongs at the publishing boundary in a later roadmap item. Date/Author:
  2026-06-24, planning team and review panel; revision 2026-10-12,
  implementation.
- Decision: Add a minimal **ADR
  `adr-002-cargo-workspace-and-crate-boundaries`** now. Rationale: the crate
  boundary is substantive and hard to reverse, and it is cited by every later
  task and by downstream `rstest-bdd` work. AGENTS.md and the style guide both
  call for capturing a substantive decision in an ADR referenced from the
  design document. The plan anticipated `adr-001` as the next sequence number,
  but `adr-001` was taken by the shared CV-005 contract library decision on
  `main` before this branch was rebased, so the crate-boundary ADR is numbered
  `adr-002`; ADR numbers are assigned in creation order and this plan does not
  reserve numbers for the 1.1.2 and 1.1.3 ADRs. Date/Author: 2026-06-24,
  planning team and review panel.
- Decision: Enforce the red stage with a **compile-fail import and a value
  diff**, recording the observable substitute, because Rust's stable test
  harness has no strict expected-failure marker for these reds. Rationale: the
  `execplans` skill asks for a strict expected-failure marker where the
  framework supports one, or a documented substitute otherwise. The
  reachability red is a `cargo`-refused import
  (`unresolved import rstest_xfail::xfail`) and the member-set red is the diff
  `left: {"rstest-xfail"}` against the three-member set; both are deterministic
  and observable. Date/Author: 2026-06-24, review panel.
- Decision: Set **`resolver = "3"`** in the virtual manifest and verify it with
  `cargo metadata` immediately after writing the manifest. Rationale: a virtual
  manifest has no package edition to infer the resolver from, so the resolver
  must be set explicitly; edition 2024 corresponds to resolver 3. The pinned
  nightly Cargo accepts resolver 3. The verification step (Concrete steps,
  Stage C) catches any toolchain mismatch on the very first `cargo metadata`
  rather than later. Date/Author: 2026-06-24, review panel.

## Context and orientation

The reader is assumed to know nothing of this repository. The state this plan
was written against — before the conversion it describes — was a single Cargo
package. The items below record that starting point; the branch that implements
the plan no longer has them.

- `Cargo.toml` (root) declares `package.name = "rstest-xfail"`, edition 2024,
  version 0.1.0, and licence ISC. It carries large lint tables:
  `[lints.clippy]` (roughly fifty entries, including `pedantic` at `warn` with
  `priority = -1` and many restriction lints set to `deny`), `[lints.rust]` with
  `missing_docs = "deny"`, and `[lints.rustdoc]` with
  `missing_crate_level_docs = "deny"`.
- `src/lib.rs` is a stub exposing `pub const fn greet() -> &'static str`.
- `tests/stub.rs` is a disposable integration test that only checks
  `CARGO_MANIFEST_DIR` is set. Its own module comment says to delete it once
  real tests exist.
- `clippy.toml` sets tight thresholds and `allow-expect-in-tests = true`. This
  means `.expect(...)` is permitted inside `#[test]` and `#[cfg(test)]` code,
  but `.unwrap()` is denied everywhere and helpers outside test scope must
  return `Result` and use `?` rather than panicking (AGENTS.md "Error
  handling").
- `.cargo/config.toml` enables the unstable `codegen-backend` feature and sets
  `[profile.dev] codegen-backend = "cranelift"`, plus a `mold` linker
  configuration for Linux.
- `rust-toolchain.toml` pins a nightly with the `clippy`, `llvm-tools-preview`,
  `rustc-codegen-cranelift-preview`, and `rustfmt` components. It pinned
  `nightly-2026-05-28` when this plan was written; the rebased branch inherits
  `nightly-2026-10-11` from `main`, and this task does not change it either way.
- `Makefile` is the public entrypoint. `make check-fmt`, `make lint`, and
  `make test` are the commit gates; `make all` runs the three in sequence.
  `make test` prefers `cargo nextest run` and also runs
  `cargo test --doc --workspace --all-features`. `make markdownlint`,
  `make nixie`, and `make audit` are separate targets, not part of `make all`.
  `make audit` derives the workspace root with
  `cargo metadata --no-deps --format-version 1` and runs `cargo audit` once at
  the root. The `build` and `release` targets build a file named by
  `TARGET ?= librstest-xfail.rlib`.
- `.github/workflows/ci.yml` runs everything through `make` (check-fmt,
  markdownlint, audit, lint, and a coverage action). It never invokes
  `make build` or `make release`.

Terms used in this plan:

- **Virtual manifest** — a root `Cargo.toml` with a `[workspace]` table but no
  `[package]` table. It owns no source code.
- **Facade crate** — the user-facing crate that re-exports the public surface
  of the other crates so users depend on one name.
- **Driving adapter** — code that translates external input (here, the
  `#[xfail]` attribute) into calls on the domain core.

### Hexagonal mapping

The ports-and-adapters lens protects the boundary; it is not a ceremony to
transplant. There are no `ports/` module trees at this stage because there is
no logic to wrap yet.

- **Domain core** — `rstest-xfail-core`. The hexagon interior. It will own the
  classification vocabulary and the `IntoBodyOutcome` seam (design §6.1). At
  1.1.1 it is a documented placeholder with no public items.
- **Driving adapter** — `rstest-xfail-macros`. Translates the user's attribute
  into calls on the core's inbound boundary (in a later task).
- **Composition root** — `rstest-xfail`. Wires the adapter to the core through
  re-exports.
- **Driven side** — none yet. The design keeps harness reporting in adapters,
  not the core (design §11), and `rstest-bdd` is a separate downstream
  consumer, out of scope here.

For screen readers: the following diagram shows the three crates as boxes with
an arrow from the facade to the macros crate. The core has no incoming and no
outgoing arrows at this task, expressing constraint D1, and is drawn detached
for that reason. Three arrows are therefore deferred: the facade-to-core edge
arrives with the core vocabulary (roadmap 1.2.x), and the macros-to-core edge
with the macro rewriting (roadmap 2.1.x).

```mermaid
flowchart LR
    facade["rstest-xfail (facade)"] --> macros["rstest-xfail-macros (driving adapter)"]
    core["rstest-xfail-core (domain core)"]
```

*Figure 1: The 1.1.1 dependency arrows. Only the facade-to-macros edge is
declared; the facade-to-core and macros-to-core edges are deferred to 1.2.x and
2.1.x respectively.*

Constraint D1 is the enforceable form of this mapping.

## Interfaces and dependencies

At the end of this task the following must exist.

The repository root `Cargo.toml` is a virtual workspace manifest:

```toml
[workspace]
resolver = "3"
members = [
    "crates/rstest-xfail-core",
    "crates/rstest-xfail-macros",
    "crates/rstest-xfail",
]

[workspace.package]
version = "0.1.0"
edition = "2024"
license = "ISC"
repository = "https://github.com/leynos/rstest-xfail"
# `homepage` is deliberately absent: it would duplicate `repository`, which
# Cargo warns about (`package.homepage` is redundant with `package.repository`).
readme = "README.md"
keywords = ["rust", "testing", "macros", "unit-tests"]
categories = ["development-tools"]

[workspace.dependencies]
# `rstest-xfail-core` is deliberately absent until a member depends on it. The
# workspace declares a dependency here only once a member names it with
# `<crate>.workspace = true`; an entry no member uses is reported by Cargo as an
# unused workspace dependency. The core's entry arrives with the facade
# re-exports in roadmap 1.2.x.
rstest-xfail-macros = { path = "crates/rstest-xfail-macros", version = "0.1.0" }

[workspace.lints.clippy]
pedantic = { level = "warn", priority = -1 }

# 1. hygiene
allow_attributes                    = "deny"
allow_attributes_without_reason     = "deny"
blanket_clippy_restriction_lints    = "deny"
cognitive_complexity                = "deny"
needless_pass_by_value              = "deny"
implicit_hasher                     = "deny"

# 2. debugging leftovers
dbg_macro                           = "deny"
print_stdout                        = "deny"
print_stderr                        = "deny"

# 2. panic-prone operations
unwrap_used                         = "deny"
expect_used                         = "deny"
indexing_slicing                    = "deny"
string_slice                        = "deny"
integer_division                    = "deny"
integer_division_remainder_used     = "deny"
panic_in_result_fn                  = "deny"
unreachable                         = "deny"

# 4. portability
host_endian_bytes                   = "deny"
little_endian_bytes                 = "deny"
big_endian_bytes                    = "deny"

# 5. nursery idiom polish
let_underscore_must_use             = "deny"
or_fun_call                         = "deny"
option_if_let_else                  = "deny"
self_named_module_files             = "deny"
shadow_reuse                        = "deny"
shadow_same                         = "deny"
shadow_unrelated                    = "deny"
str_to_string                       = "deny"
string_lit_as_bytes                 = "deny"
try_err                             = "deny"
unneeded_field_pattern              = "deny"
use_self                            = "deny"

# 6. numerical foot-guns
float_arithmetic                    = "deny"
cast_possible_truncation            = "deny"
cast_possible_wrap                  = "deny"
cast_precision_loss                 = "deny"
lossy_float_literal                 = "deny"

# 7. API ergonomics
missing_const_for_fn                = "deny"
must_use_candidate                  = "deny"
unused_async                        = "deny"

# 8. Error handling
missing_panics_doc                  = "deny"
error_impl_error                    = "deny"
result_large_err                    = "deny"

[workspace.lints.rust]
missing_docs                        = "deny"

[workspace.lints.rustdoc]
missing_crate_level_docs            = "deny"
```

The `[workspace.lints.*]` tables are the current root `[lints.*]` tables copied
verbatim, with only the table header gaining the `workspace.` prefix. The
`priority = -1` on `pedantic` is preserved so the explicit per-lint `deny`
entries override the group `warn`. The `authors`, `description`, and
`rust-version` keys are intentionally not added to `[workspace.package]`
because the current manifest does not set them and each crate carries its own
`description`.

The member manifest `crates/rstest-xfail-core/Cargo.toml`:

```toml
[package]
name = "rstest-xfail-core"
description = "Outcome and policy types and runtime classification for rstest-xfail"
version.workspace = true
edition.workspace = true
license.workspace = true
repository.workspace = true
readme.workspace = true
keywords.workspace = true
categories.workspace = true

[dependencies]

[lints]
workspace = true
```

The member manifest `crates/rstest-xfail-macros/Cargo.toml`:

```toml
[package]
name = "rstest-xfail-macros"
description = "Procedural macro implementation of the #[xfail] attribute for rstest-xfail"
version.workspace = true
edition.workspace = true
license.workspace = true
repository.workspace = true
readme.workspace = true
keywords.workspace = true
categories.workspace = true

[lib]
proc-macro = true

[dependencies]

[lints]
workspace = true
```

The member manifest `crates/rstest-xfail/Cargo.toml`:

```toml
[package]
name = "rstest-xfail"
description = "Expected failure macro attributes for rstest, async tests and rstest-bdd"
version.workspace = true
edition.workspace = true
license.workspace = true
repository.workspace = true
readme.workspace = true
keywords.workspace = true
categories.workspace = true

[dependencies]
# Only the macro crate is named here. A dependency on `rstest-xfail-core` is
# deliberately absent until the facade re-exports core types (roadmap 1.2.x):
# the core exposes no public items yet, so declaring the edge now would be a
# dependency no target can use, which Cargo reports as `unused_dependencies`.
rstest-xfail-macros.workspace = true

[dev-dependencies]
rstest = "0.23"
googletest = "0.13"
pretty_assertions = "1"
insta = "1"
serde_json = "1"
serial_test = { version = "3", features = ["file_locks"] }
eyre = "0.6"
cap-std = "4"
camino = "1"

[lints]
workspace = true
```

Resolve the `dev-dependencies` to current caret versions at implementation time
with

```bash
cargo add --dev rstest googletest pretty_assertions insta serde_json eyre \
  serial_test --features serial_test/file_locks
cargo add --dev cap-std camino
```

then record the resolved versions in `Surprises & discoveries`. The string form
`insta::assert_snapshot!` used below needs no `insta` feature flag; do not add
one. No feature flag is required for the `googletest` matchers `contains`,
`eq`, and `not`.

The `file_locks` feature is required, not optional: it supplies
`serial_test::file_serial`, which the `cargo metadata` tests need because the
gate runs `cargo nextest` and gives every test its own process, so a plain
`serial` in-process lock would serialize nothing across them. `eyre` carries
the per-stage failure context in those same tests.

The crate roots expose exactly these public items.

`crates/rstest-xfail-core/src/lib.rs` (no public items; crate documentation
only):

```rust
//! Core outcome and policy types and runtime classification for `rstest-xfail`.
//!
//! This crate is an intentional placeholder while the workspace skeleton is
//! established. It exposes no public items yet. The classification vocabulary
//! described in the design (`XfailPolicy`, `BodyOutcome`, and related types)
//! arrives in a later task (roadmap 1.2.x), at which point the facade's
//! re-export scope (design §14) is decided.
```

`crates/rstest-xfail-macros/src/lib.rs`:

```rust
//! Procedural macro implementation for `rstest-xfail`.
//!
//! This crate currently provides a no-op placeholder `#[xfail]` attribute so
//! the workspace skeleton links and the facade can re-export the attribute. The
//! real argument parsing and function rewriting described in the design arrive
//! in a later task.

use proc_macro::TokenStream;

/// Placeholder `#[xfail]` attribute macro.
///
/// For now it returns the annotated item unchanged. It must never absorb or
/// alter the body: a passing body still passes and a failing body still fails.
/// The real implementation (roadmap 2.1.x) will parse `reason`, `strict`,
/// `mode`, and `contains`, then rewrite the function body to classify its
/// outcome.
#[proc_macro_attribute]
pub fn xfail(_args: TokenStream, item: TokenStream) -> TokenStream { item }
```

`crates/rstest-xfail/src/lib.rs`:

```rust
//! Expected-failure macro attributes for `rstest`, async tests, and
//! `rstest-bdd`.
//!
//! This facade re-exports the public surface intended for ordinary users. At
//! the workspace-skeleton phase that surface is the single placeholder
//! `#[xfail]` attribute from `rstest-xfail-macros`. The stable types from
//! `rstest-xfail-core` are re-exported once they exist (roadmap 1.2.x).

pub use rstest_xfail_macros::xfail;
```

This is the entire facade surface: one macro re-export. A `pub use` re-export
does not need its own `///` doc, so `missing_docs` is satisfied by the
documentation on the original item.

## Plan of work

Work proceeds in four stages with go/no-go validation at each boundary. Commit
after each green stage.

### Stage A — understand and propose (no code changes)

Read the signposted documents. Confirm the manifest and surface design above
against the current `Cargo.toml`, `Makefile`, and `.cargo/config.toml`. This
plan is the Stage A artefact; it must be approved before Stage B (see
`Approval gate` in the `execplans` skill).

### Stage B — de-risk and write red tests

This stage is partly a prototyping milestone (the Cranelift spike) and partly
the Red step of Red-Green-Refactor.

First, de-risk R1: prove a `proc-macro = true` crate builds under the pinned
nightly with the Cranelift dev profile (Concrete steps). If it fails, apply the
fallback and re-run; if the fallback also fails, stop (T-STOP-1).

Then establish the red tests against the *current* single-package layout so
they fail for the right reason before the workspace exists. Add the test-only
`dev-dependencies` to the current root `Cargo.toml`, then:

- Add `tests/workspace_members.rs` in its final form (Concrete steps). Against
  the single package, `cargo metadata` reports one member, so the set assertion
  fails with the diff `left: {"rstest-xfail"}` — not a parse error.
- Add a *minimal* `tests/public_surface.rs` containing only
  `use rstest_xfail::xfail;` and a trivial test that applies `#[xfail]`.
  Against the current crate, `rstest_xfail::xfail` does not exist, so it fails
  to compile with `unresolved import rstest_xfail::xfail`, the correct red for
  a reachability contract. The snapshot and body-pass-through assertions are
  added in Stage D, not now.

### Stage C — implement the workspace (minimal change to go green)

1. Create the three member directories under `crates/` with the manifests and
   crate roots from `Interfaces and dependencies`. Author the files directly at
   the quoted paths; do not use `cargo new`, because the manifests are bespoke
   (inherited metadata and lints).
2. Rewrite the root `Cargo.toml` into the virtual workspace manifest, migrating
   the lint tables and package metadata, and move the test-only
   `dev-dependencies` from the root into `crates/rstest-xfail/Cargo.toml`.
3. Run `cargo metadata --no-deps --offline --format-version 1` to confirm the
   virtual manifest and `resolver = "3"` are accepted before going further.
4. Delete the root `src/lib.rs` and remove the root `src/` directory.
5. Move `tests/stub.rs` to `crates/rstest-xfail/tests/stub.rs` unchanged, and
   move `tests/workspace_members.rs` and `tests/public_surface.rs` to
   `crates/rstest-xfail/tests/`. Remove the now-empty root `tests/` directory.

Both red tests now pass. Run `make test` to confirm.

### Stage D — refactor, document, and finalize

1. Repoint the Makefile `TARGET` default to `librstest_xfail.rlib` and confirm
   `make build` and `make release` produce that artefact.
2. Expand `crates/rstest-xfail/tests/public_surface.rs` to its final form (the
   `insta` snapshot plus the body-pass-through assertion) and generate the
   snapshot. Add the `rstest` parameterized presence test and the D1 purity
   test to `crates/rstest-xfail/tests/workspace_members.rs`.
3. Write `docs/adr-002-cargo-workspace-and-crate-boundaries.md`.
4. Update `docs/repository-layout.md`, `docs/developers-guide.md`,
   `docs/contents.md`, and add the one-line realization note plus ADR reference
   to `docs/xfail-design.md` §5.
5. Run the full gate (`make check-fmt`, `make lint`, `make test`,
   `make markdownlint`, `make nixie`, `make audit`), then
   `coderabbit review --agent`, and clear all concerns.
6. Tick the 1.1.1 checkbox in `docs/roadmap.md` (the `- [ ] 1.1.1.` line).
7. Open a draft pull request titled
   `Convert the crate into a Cargo workspace (1.1.1)` whose body links this
   execplan and the roadmap §1.1.1 item, following the `pr-creation` skill.

## Concrete steps

All commands run from the repository root unless stated otherwise.

### Cranelift procedural-macro validation and fallback

After the macros crate skeleton exists. These are the commands as originally
run, on the toolchain pinned at the time (`nightly-2026-05-28`); they are
historical spike evidence, recorded so the result can be audited. The pin on
the delivered branch is `nightly-2026-10-11`, and the equivalent current
commands are the same three with the pinned toolchain, which the `make` gates
invoke without naming a version:

```text
cargo +nightly-2026-05-28 build -p rstest-xfail-macros
cargo +nightly-2026-05-28 build -p rstest-xfail
cargo +nightly-2026-05-28 test -p rstest-xfail --no-run
```

All three use the dev profile and therefore exercise Cranelift on the
procedural-macro crate. If any fail with a codegen-backend error, add the
following to `.cargo/config.toml` and re-run, so only the macros crate uses the
LLVM backend:

```toml
[profile.dev.package.rstest-xfail-macros]
codegen-backend = "llvm"
```

Apply this override only if validation fails; do not add it pre-emptively.

### The member-set and core-purity tests

The test file is committed at `crates/rstest-xfail/tests/workspace_members.rs`;
it is the authoritative form and is not duplicated here. Its shape at 1.1.1 is:
an `INTENDED_EDGES` table naming the one declared intra-workspace edge (the
facade to the macros crate), a `workspace_metadata` helper that shells out to
`cargo metadata` and returns `eyre::Result` with per-stage context, and four
serialized tests: the member set matches exactly, the core declares no
dependencies at all (D1), the declared edge set equals `INTENDED_EDGES`, and
each intended member is present.

The matchers are imported narrowly (`contains`, `eq`, `empty`, `assert_that`,
and `GoogleTestSupport`) rather than via `use googletest::prelude::*`, because
the glob brings a single-parameter `Result` alias into scope that would clash
with the helper signatures, and because the format-arguments form of
`assert_that!` requires `GoogleTestSupport` explicitly. `--no-deps` keeps each
package's declared `dependencies` array available while omitting the resolved
graph, which is what both the member-set and D1 checks need.

### The facade public-surface test

`crates/rstest-xfail/tests/public_surface.rs` (final form, added in Stage D and
then strengthened — see the `Surprises & discoveries` entry on the derived
surface). The shipped test **derives** the surface from the facade's own
`src/lib.rs` and asserts the derived set against `INTENDED_PUBLIC_SURFACE`
before snapshotting the derived value, so an unintended export fails instead of
being mirrored into the expectation. The Stage D sketch below hard-coded the
snapshot input and could not detect one; it is retained here only to show the
shape the test grew from.

```rust
//! Documents the facade's public surface for roadmap task 1.1.1.
//!
//! The surface is *derived* from the facade's own source rather than restated,
//! so an unintended re-export fails here instead of being mirrored into the
//! expectation. Two assertions carry the contract: the derived set must equal
//! the intended set, and — as a reviewer-facing record — an `insta` snapshot
//! captures the derived names.

use rstest_xfail::xfail;

/// The facade's intended public surface, one path per line, sorted.
const INTENDED_PUBLIC_SURFACE: &str = "rstest_xfail::xfail";

#[test]
fn facade_public_surface_is_documented() -> eyre::Result<()> {
    let derived = exported_paths(&facade_source()?)?.join("\n");
    pretty_assertions::assert_eq!(derived, INTENDED_PUBLIC_SURFACE);
    insta::assert_snapshot!("facade_public_surface", derived);
    Ok(())
}

// Applying the placeholder attribute proves it is reachable through the facade
// and, critically, that the no-op passes the body through unchanged rather than
// absorbing it. The design forbids a rewritten body from ever masking its real
// outcome; 2.1.x replaces this no-op before any classification logic exists.
#[xfail]
const fn annotated_body_runs() -> i32 { 2 + 2 }

#[test]
fn placeholder_macro_passes_body_through() {
    use pretty_assertions::assert_eq;

    assert_eq!(annotated_body_runs(), 4);
}
```

`facade_source()` reads the crate source through `cap_std::fs::Dir` and
`camino::Utf8Path` rather than `std::fs`, which is what the whitaker
`no_std_fs_operations` lint requires (see `Surprises & discoveries`); the full
source of the derivation helpers lives in the file itself.

Generate the snapshot once with
`INSTA_UPDATE=always cargo test -p rstest-xfail --test public_surface` (or
`cargo insta accept`), review the emitted file, and commit it. Do not
hand-author the snapshot header; let `insta` write
`crates/rstest-xfail/tests/snapshots/public_surface__facade_public_surface.snap`
and review only that its payload reads `rstest_xfail::xfail`. The one-line
surface is intentionally tiny at 1.1.1 and grows in later tasks; it is not an
incomplete test.

### Test-tool applicability

These deferrals are deliberate scoping, not omissions.

- `rstest` — applies; used for the parameterized presence test.
- `rstest-bdd` — deferred. There is no runtime behaviour to narrate as
  Given/When/Then; the `cargo metadata` end-to-end test is the correct
  observable check. Revisit when `#[xfail]` produces user-visible outcomes
  (2.x).
- `proptest` — deferred. A fixed three-member set has no input domain over
  which a property holds.
- `kani` — deferred. There is no `unsafe` code or state machine to model-check;
  the contract is enforced by Cargo's resolver and rustc's import resolution.
- `verus` — deferred. There is no function or lemma to prove; a proof here
  would restate an assumed property, which AGENTS.md disallows.

### The ADR

Create `docs/adr-002-cargo-workspace-and-crate-boundaries.md` following the
style guide's required ADR sections. It records only the workspace and boundary
decision, not strictness (1.1.2) or async (1.1.3):

- **Status:** Accepted, 2026-06-24, "Adopt a three-crate Cargo workspace under
  `crates/` with a pure core".
- **Date:** 2026-06-24.
- **Context and problem statement:** the single crate cannot let downstream
  consumers (notably `rstest-bdd`) reuse classification logic without importing
  procedural-macro expansion machinery; design §5 mandates a split.
- **Decision outcome:** three crates — `rstest-xfail-core` (library),
  `rstest-xfail-macros` (procedural macro), `rstest-xfail` (facade) — under
  `crates/`, with a virtual workspace root, `[workspace.lints]` inheritance,
  and dependency rule D1.
- **Known risks and limitations:** the Cranelift-on-procedural-macro build
  risk (R1) and placeholder churn until 1.2.x (R6) are noted as follow-ups. The
  facade re-export scope (design §14) is recorded as a deferred decision, not
  decided here.

Add a one-line pointer to this ADR from `docs/xfail-design.md` §5 and link it
from `docs/contents.md` under a new `## Decision records` group.

### Documentation edits

- `docs/repository-layout.md` — replace the `src/` and `tests/` leaves with the
  `crates/*` subtree; restate the root `Cargo.toml` entry as the virtual
  workspace manifest; add per-crate path-responsibility bullets and the D1
  ownership boundary; restate the source and integration-test ownership rules
  per crate.
- `docs/developers-guide.md` — add a short "Workspace layout" note: three
  crates, `cargo` operates across all members by default, target one crate with
  `-p <crate>`, and lint and dependency policy are inherited from
  `[workspace.lints]` and `[workspace.dependencies]`.
- `docs/contents.md` — add an `## Execution plans` group listing this plan, and
  a `## Decision records` group listing the new ADR.
- `docs/xfail-design.md` — add one informative sentence at the top of §5
  noting the skeleton is realized by this plan and crate roots are placeholders
  until 1.2.x/2.1.x; do not alter the normative crate table.
- `docs/users-guide.md` — add a short "rendered projects are a workspace" note.
  The `make` targets are already described in template-neutral language and no
  public API changes at 1.1.1, but the guide did name `src/lib.rs` as the
  library layout, and this conversion deletes that root path and moves the
  crate roots under `crates/*/src/`. Anyone following the guide to locate or
  edit the library would be misdirected, so the layout sentence is corrected,
  and the three members are named as placeholder stubs. A fuller user-guide
  treatment still waits on real public API at 2.1.x.

No Mermaid diagram is added to the edited documentation beyond Figure 1 in this
plan, so `make nixie` validates the existing diagram and passes. The optional
boundary diagram may be added with the ADR if a reviewer wants it, but it is
not required for 1.1.1.

## Validation and acceptance

Acceptance is phrased as observable behaviour. Run from the repository root.

Red-Green-Refactor evidence to record:

- **Red.** Before the `[workspace]` table exists,
  `cargo test --test workspace_members` fails with the member-set diff
  `left: {"rstest-xfail"}`, and `cargo test --test public_surface` fails to
  compile with `unresolved import rstest_xfail::xfail`. Rust's stable harness
  has no strict expected-failure marker for these reds, so the compile-fail
  import and the value diff are the observable substitutes (Decision log).
- **Green.** After Stage C, `make test` passes: the member-set test, the D1
  purity test, the three `rstest` cases, and the reachability test pass, and
  `cargo test --doc --workspace --all-features` passes.
- **Refactor.** After Stage D, the snapshot and body-pass-through assertions
  are added and the full gate stays green.

Quality criteria (what "done" means):

- **Tests.** `make test` exits 0. The `workspace_members` and `public_surface`
  tests pass; doctests pass. The disposable `stub.rs` placeholder described in
  the plan was deleted during Stage D, so it is no longer part of this
  criterion.
- **Lint.** `make lint` exits 0 with no `unwrap_used`, `expect_used`,
  `missing_docs`, or `missing_crate_level_docs` diagnostics across all targets
  and features.
- **Format.** `make check-fmt` exits 0.
- **Markdown and diagrams.** `make markdownlint` and `make nixie` pass for the
  new and edited documentation.
- **Audit.** `make audit` runs once at the workspace root and passes.
- **Boundary (D1).** The `core_declares_no_dependencies` test passes, and
  `cargo tree -p rstest-xfail-core` shows no dependency on
  `rstest-xfail-macros`, `rstest-xfail`, `syn`, `quote`, or `proc-macro2`.
- **CodeRabbit.** `coderabbit review --agent` reports no outstanding concerns,
  run only after the deterministic gates above are green.

The literal roadmap criterion, checkable without the test harness:

```text
cargo metadata --no-deps --offline --format-version 1 > /tmp/meta.json
python3 - <<'PY'
import json
meta = json.load(open("/tmp/meta.json"))
ids = set(meta["workspace_members"])
names = [p["name"] for p in meta["packages"] if p["id"] in ids]
print(sorted(names))
PY
```

Expected output:

```text
['rstest-xfail', 'rstest-xfail-core', 'rstest-xfail-macros']
```

Task 1.1.1 is done when this prints the three names; `make check-fmt`,
`make lint`, `make test`, `make markdownlint`, `make nixie`, and `make audit`
each exit 0; the `public_surface` test derives only `rstest_xfail::xfail` from
the facade source and its snapshot reads the same; and the D1 purity test
passes.

## Idempotence and recovery

The conversion is a structural edit under version control, so recovery is
`git restore` or `git checkout` of the affected files. Each stage is committed
separately, so a failed stage can be rolled back without losing earlier work.
Re-running the validation commands is safe and non-destructive. The
`INSTA_UPDATE=always` snapshot creation is idempotent: re-running regenerates
the same snapshot from the same `INTENDED_PUBLIC_SURFACE` constant. The
Cranelift fallback edit to `.cargo/config.toml` is additive and can be removed
if a later toolchain fixes the backend.

## Artefacts and notes

Record the Cranelift spike result, the resolved `dev-dependency` versions, and
the first `make build` artefact name here as they are produced, so a future
reader does not have to re-derive them.

- Cranelift spike: passed. A bare `proc-macro = true` crate with a
  `#[proc_macro_attribute]` no-op built, and a test that expands and runs the
  attribute through a bin target, passed under `nightly-2026-05-28` with the
  dev Cranelift profile. No LLVM fallback override added.
- Resolved `dev-dependency` versions: `rstest 0.26.1`, `googletest 0.13.0`,
  `pretty_assertions 1.4.1`, `insta 1.48.0`, `serde_json 1.0.151`,
  `serial_test 4.0.1`, `eyre 0.6.14`, `cap-std 4.0.3`, `camino 1.2.6`.
- First `make build` artefact name after the conversion:
  `target/debug/librstest_xfail.rlib` (underscore). The facade rlib is
  `librstest_xfail.rlib`; the Makefile `TARGET` default was repointed from the
  obsolete hyphenated `librstest-xfail.rlib`.

## Outcomes & retrospective

Task 1.1.1 is delivered. `cargo metadata` lists exactly the three workspace
members (`rstest-xfail`, `rstest-xfail-core`, `rstest-xfail-macros`), the
facade re-exports only `rstest_xfail::xfail` (derived-surface test + snapshot),
and constraint D1 is enforced by the `core_declares_no_dependencies` test. All
deterministic gates and a 0-finding CodeRabbit review pass.

Deviations from the plan, all recorded above:

- The root `tests/` directory is retained because `tests/workflow_contracts/`
  is a separate, still-valid mutation-testing contract suite; only the Rust
  integration tests moved into the facade crate.
- googletest resolved to 0.13 and its container matchers require `Copy`
  containers; the D1/presence assertions use `assert_that!` over
  `&BTreeSet<String>` rather than the plan's `verify_that!` form. The
  assertions' meaning is unchanged.
- The final public_surface test applies the placeholder attribute to a
  `const fn` solely to satisfy `clippy::missing_const_for_fn`; this does not
  change the reachability or body-pass-through contract.

Lesson for 1.2.x and 2.1.x: the workspace skeleton, D1 purity gate, and the
surface snapshot give the follow-up tasks a stable boundary to build on. The
googletest API drift is a reminder to pin mutually consistent matcher APIs in
the plan's reviewed snippets.

## Revision note

Initial draft, 2026-06-24. Authored from the technical design §§5-6, the
roadmap §1.1.1, and a planning team analysis covering the workspace manifest,
the test strategy, and the architecture, documentation, and risk surface, then
revised after a community-of-experts review. The review removed a fictitious
placeholder core type (it prejudged design §14), fixed two lint and compilation
defects in the test snippets (`unfulfilled_lint_expectations` on a used import;
a `Result` alias clash from a `googletest` glob import), added an automated D1
purity gate, hardened the placeholder-macro test to prove genuine body
pass-through, corrected the red-stage sequencing, captioned the risk table,
added the draft-PR delivery step, and enumerated the actual gate set in the
acceptance criteria.

The plan was approved and fully implemented: Stages C and D are complete and
task 1.1.1 is delivered, as recorded in the outcomes and retrospective above.
The pull request carrying it is **draft** while this was a pre-implementation
plan; draft status tracks the pull request lifecycle, not implementation
completeness, and is independent of the "No implementation has begun" statement
that applied only to the original draft of this plan. Pull request #112 is the
current carrier; pull request #12 was closed as superseded once the branch was
rebased and could no longer be fast-forwarded.

### Post-review revisions

After review feedback on pull request #12 the branch was rebased onto `main`
(bringing in the shared build standard, the CV-005 workflow contracts, and the
`nightly-2026-10-11` toolchain bump) and the following changes were applied.
Pull request #12 was then closed as superseded, because its head commit
predated the rebase and could not be fast-forwarded; the rebased history and
these revisions are carried by pull request #112.

- `workspace_members.rs` now asserts an **empty** direct dependency set for
  `rstest-xfail-core` instead of testing a forbidding-name blacklist, so the D1
  gate cannot be satisfied by a dependency the blacklist happens not to name.
- `workspace_members.rs` also pins the complete intra-workspace dependency
  edge set, which catches a new edge anywhere in the graph rather than only in
  the core.
- `workspace_metadata` and its helpers return `eyre::Result` with per-stage
  context, so a failure names whether `cargo metadata`, JSON parsing, or
  package lookup failed.
- The `rstest` parameterized cases carry a serialization attribute, matching
  the module's stated serialization guarantee. (That attribute is
  `file_serial`; see the formal-review entry below.)
- The generated `stub.rs` placeholder test was deleted; the substantive
  workspace tests supersede it.
- `rstest_xfail::xfail` carries a Rustdoc comment at the facade boundary.
- The ADR gained a `Requirements` section with functional and technical
  subsections and a table caption, and all ADR headings use sentence case.
- The `Makefile` artefact rule gained a `FORCE` prerequisite so Make always
  delegates the freshness decision to Cargo; previously an existing artefact
  suppressed every later rebuild.
- That fix was first written by declaring the artefact targets `.PHONY`, which
  suppressed Make's implicit-rule search: mark a target phony and Make skips
  implicit rules for it, so the `target/%/$(TARGET)` pattern rule stopped
  matching and `make build` and `make release` became silent no-ops. The
  repository's `build_standard_test.py` contract test caught it in CI by
  asserting that `make release` still assigns `RUSTFLAGS`, and the rule now
  uses a `FORCE` prerequisite, which forces the rebuild without making the
  artefact phony.
- `homepage` was removed from `[workspace.package]` and every member manifest.
  Cargo warns that `package.homepage` is redundant with `package.repository`
  when both are set, and `repository` already carries the canonical project URL.
- The facade no longer declares a dependency on `rstest-xfail-core`, and the
  `[workspace.dependencies]` entry for the core was dropped with it. The core
  exposes no public items at 1.1.1, so the edge was a dependency no target
  could use, which Cargo reports as an unused dependency (and as an unused
  workspace dependency once the member edge is gone). The edge returns with the
  core vocabulary at roadmap 1.2.x; the `INTENDED_EDGES` table in
  `workspace_members.rs` is where it is re-declared, and the D1 gate is
  unaffected because D1 constrains the core's own dependencies.
- The final reconciling pass corrected plan text that still named artefacts the
  implemented branch does not have. The crate-boundary ADR is
  `adr-002-cargo-workspace-and-crate-boundaries.md` (`adr-001` having gone to
  the shared CV-005 contract library on `main`), the D1 gate is named
  `core_declares_no_dependencies`, and the deferred `stub.rs` placeholder is
  described as deleted rather than as still passing. Acceptance criteria that
  named a test or file the branch no longer carries would otherwise have made a
  completed task look incomplete.
- The ExecPlan completeness assessment confirmed no blocking defect and named
  three documentation corrections, all applied here. The plan's header now reads
  `Status: COMPLETE` rather than `DRAFT`, matching the delivered outcomes.
  `repository-layout.md` no longer lists the deleted `tests/stub.rs`. The
  Cranelift spike commands are labelled as historical evidence on the pin that
  was current when the spike ran, with the inherited `nightly-2026-10-11` pin
  named as the branch's actual toolchain, so the commands cannot be mistaken
  for current instructions. The spike's result and the fallback procedure are
  unchanged.
- CodeRabbit's formal review then raised three findings, all applied here.
  The `cargo metadata` tests had used `serial_test::serial`, which is inert
  under the gate: `make test` selects `cargo nextest` whenever it is installed
  (and CI installs it), nextest runs each test in its own process, and an
  in-process lock therefore serializes nothing across them. They now use
  `file_serial`, which takes an advisory file lock, with the `file_locks`
  feature enabled on `serial_test`. This plan's own manifest block had also
  omitted `eyre` and the `file_locks` feature, so a reader building from it
  would have hit unresolved imports in the tests the block accompanies; both
  are now shown. Finally, the artefact rule's `FORCE` prerequisite is declared
  `.PHONY`, so a stray file named `FORCE` cannot satisfy it and silently demote
  the rule back to a timestamp comparison. The two documentation gates this
  repair itself tripped (`mdtablefix` reflow, `MD040` on the new fence) were
  fixed before commit.
- The Codex connector raised a further P2 finding that CodeRabbit did not: this
  plan deferred the user guide on the grounds that it "names no crate or
  dependency snippet", but `docs/users-guide.md` did name `src/lib.rs` as the
  library layout, and this conversion deletes that root path. The guide now
  states that a rendered project is a Cargo workspace and names the three
  member crates and their placeholder status, and the deferral note above
  records the corrected reasoning. The finding was valid; the plan's stated
  reason for skipping the file was not.
