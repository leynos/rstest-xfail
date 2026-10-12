# Architectural decision record (ADR) 002: Cargo workspace and crate boundaries

## Status

Accepted, 2026-10-12. The repository adopts a three-crate Cargo workspace under
`crates/` with a virtual manifest at the root and a pure core leaf.

## Date

2026-10-12.

## Context and problem statement

The single `rstest-xfail` package cannot let downstream consumers (notably
`rstest-bdd`) reuse classification logic without importing procedural-macro
expansion machinery. The technical design (xfail-design.md §5) mandates a split
so that `rstest-bdd` can depend on a pure core crate rather than on the
proc-macro adapter.

## Requirements

### Functional requirements

- Expose the intended user-facing surface through one facade crate, so ordinary
  users name a single dependency and import `rstest_xfail::xfail`.
- Keep the classification vocabulary importable by downstream libraries, such
  as `rstest-bdd`, without importing procedural-macro expansion machinery.
- Let the facade reach both the core vocabulary and the procedural macro
  through declared, one-way dependency edges. Only the facade-to-macros edge is
  declared at task 1.1.1: the core exposes no public items yet, so an edge to
  it would be a dependency no target could use, which Cargo reports as an
  unused dependency. The facade-to-core edge arrives with the core vocabulary
  in roadmap 1.2.x.

### Technical requirements

- Enforce dependency rule D1: the core depends on no sibling crate and on no
  procedural-macro tooling (`syn`, `quote`, `proc-macro2`).
- Inherit package metadata, lint policy, and shared dependency declarations
  across all members from the virtual workspace root, so the three crates
  cannot drift apart.
- Keep accepting the Cranelift-backed procedural-macro build, or document a
  fallback, because the development profile compiles with the Cranelift
  code-generation backend.

## Decision drivers

- Keep the procedural macro out of downstream runtime integrations.
- Let the core classification vocabulary be reusable from `rstest-bdd` and any
  future adapter without pulling in macro-expansion tooling.
- Keep the lint, metadata, and dependency policy consistent across the three
  crates through workspace inheritance.

## Options considered

### Option A: Keep the single package

Rejected. There is no usable boundary: `rstest-bdd` would either depend on the
proc-macro crate or duplicate the classification logic.

### Option B: Three crates under `crates/` with a virtual workspace root

Accepted. The three crates are peers with one-way dependency edges and a pure
core leaf.

### Option C: Make the facade the root package

Rejected. The core has no dependency on the facade, so nesting it under the
facade would misrepresent the dependency graph.

## Decision outcome

Adopt a virtual workspace manifest at the repository root with three members
under `crates/`:

- `rstest-xfail-core` — library owning outcome types, policy types,
  body-result conversion traits, and sync classification functions.
- `rstest-xfail-macros` — procedural macro parsing `#[xfail(...)]` and
  rewriting functions into calls on the core.
- `rstest-xfail` — facade re-exporting `#[xfail]` and the public core types.

The workspace inherits package metadata from `[workspace.package]`, lints from
`[workspace.lints]`, and dependency declarations from
`[workspace.dependencies]`. Dependency rule D1 is enforced: the core must
depend on none of its siblings and on no procedural-macro tooling (`syn`,
`quote`, `proc-macro2`).

## Goals and non-goals

Goals:

- Establish the three-crate boundary and the D1 purity gate.
- Ship the facade surface (`rstest_xfail::xfail`) at task 1.1.1.

Non-Goals:

- Deciding the facade re-export scope for the stable core types (design §14);
  that is deferred.
- Recording strictness policy (roadmap 1.1.2) or the async strategy
  (roadmap 1.1.3); those are separate ADRs.

## Migration plan

1. Rewrite the root manifest as a virtual workspace and add the three member
   crates (done in task 1.1.1).
2. Move the integration tests into the facade crate and add the D1 purity and
   public-surface tests (done in task 1.1.1).
3. Follow-up tasks fill in the core vocabulary (1.2.x) and the macro rewriting
   (2.1.x), then decide the facade re-export scope.

## Known risks and limitations

- Cranelift-on-procedural-macro build risk (R1 in the execplan) is retired by
  the spike but may resurface on later toolchains; the `.cargo/config.toml`
  dev-profile override is the documented fallback.
- Placeholder churn until 1.2.x: the core crate and the `#[xfail]` attribute
  are placeholders and will be replaced by real implementations without
  changing the boundaries recorded here.

## Architectural rationale

The pure-core leaf keeps classification semantics importable by downstream
libraries without pulling in procedural-macro expansion, and the workspace
inheritance keeps lint and dependency policy from drifting across members. This
aligns with the project goal of a reviewable, testable expected-failure
contract that `rstest-bdd` can consume directly.
