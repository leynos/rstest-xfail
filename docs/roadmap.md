# rstest-xfail roadmap

This roadmap sequences the work needed to implement the expected-failure design
described in [terms of reference](terms-of-reference.md) and
[technical design](xfail-design.md). Phases are GIST ideas, steps are
workstreams that validate each idea, and tasks are review-sized execution units.

The roadmap does not promise dates. It records build order, dependencies, and
acceptance criteria for the `rstest-xfail` workspace and the downstream
`rstest-bdd` core-classification integration.

## 1. Foundational phase: settle contracts before macro expansion

Idea: if the project settles the outcome vocabulary, crate boundary, and
supported macro orders before feature work starts, the implementation can grow
through tested vertical slices instead of repeatedly reworking public APIs.

This phase turns the design into a buildable workspace and proves the smallest
core classification contract without depending on procedural macro expansion.

### 1.1. Ratify public policy and workspace shape

This step answers which APIs are stable enough for downstream use. It informs
all macro and BDD work because both depend on the core outcome vocabulary.

- [ ] 1.1.1. Convert the crate into a Cargo workspace with
  `rstest-xfail-core`, `rstest-xfail-macros`, and the `rstest-xfail` facade.
  - See xfail-design.md §§5-6.
  - Success: `cargo metadata` shows all three workspace crates and the facade
    re-exports only the intended public surface.
- [ ] 1.1.2. Record an ADR for strict XPASS default behaviour and the initial
  non-strict policy.
  - See terms-of-reference.md §§6-9 and xfail-design.md §§7, 14.
  - Success: the ADR states whether `strict = false` ships in v1 and names the
    consequence for CI users.
- [ ] 1.1.3. Record an ADR for the async support strategy.
  - Requires 1.1.1.
  - See xfail-design.md §9.
  - Success: the ADR chooses feature-gated future-level catching, sync-only v1,
    or another documented path with compatibility criteria.

### 1.2. Implement the core classifier

This step answers whether the shared runtime contract can classify panic and
`Result` outcomes without macro knowledge. It unlocks every adapter.

- [ ] 1.2.1. Implement `XfailPolicy`, `FailureMode`, `Strictness`,
  `BodyOutcome`, and `XfailOutcome` in `rstest-xfail-core`.
  - Requires 1.1.1 and 1.1.2.
  - See xfail-design.md §6.
  - Success: constructors enforce required reason text and reject invalid
    message-matching state.
- [ ] 1.2.2. Implement `IntoBodyOutcome` for `()` and `Result<T, E>`.
  - Requires 1.2.1.
  - See xfail-design.md §6.1.
  - Success: aliases such as `anyhow::Result<()>` classify through the generic
    `Result<T, E>` implementation without macro syntax detection.
- [ ] 1.2.3. Implement sync panic observation and policy classification.
  - Requires 1.2.1 and 1.2.2.
  - See xfail-design.md §§6.2, 11-12.
  - Success: tests cover pass, panic, `Err`, strict XPASS, mode filtering, and
    message matching.

## 2. Vertical slice: synchronous `rstest` users can mark expected failures

Idea: if the first public macro works for sync tests and per-case `rstest`
generation, the project already solves the highest-frequency user problem
without async or BDD complexity.

This phase delivers the facade crate, the `#[xfail]` macro, and documented sync
usage.

### 2.1. Build the proc-macro adapter

This step answers whether function rewriting can preserve the user function
shape that `rstest` and libtest expect.

- [ ] 2.1.1. Implement `#[xfail(...)]` argument parsing in
  `rstest-xfail-macros`.
  - Requires 1.2.1.
  - See xfail-design.md §7.
  - Success: `trybuild` cases cover required `reason`, unknown arguments,
    invalid `mode`, and unsupported item targets.
- [ ] 2.1.2. Rewrite sync function bodies into calls to
  `rstest_xfail::expect_fail`.
  - Requires 2.1.1 and 1.2.3.
  - See xfail-design.md §§5.1, 7.
  - Success: generated code preserves attributes, generics, visibility, where
    clauses, arguments, and doc comments.
- [ ] 2.1.3. Re-export the macro and stable core types from the facade crate.
  - Requires 2.1.2.
  - See xfail-design.md §5.
  - Success: user examples import only `rstest_xfail::xfail` for ordinary use.

### 2.2. Prove `rstest` composition

This step answers which macro order and per-case placement are supported. It
turns the design's macro-order risk into an explicit compatibility contract.

- [ ] 2.2.1. Add `trybuild` fixtures for supported and unsupported attribute
  orders with `#[rstest]`.
  - Requires 2.1.2.
  - See xfail-design.md §8.
  - Success: the fixture names and diagnostics identify the documented order.
- [ ] 2.2.2. Add runtime tests for per-case xfail and all-case xfail.
  - Requires 2.2.1.
  - See xfail-design.md §§8, 12.
  - Success: only the marked generated cases invert outcome classification.
- [ ] 2.2.3. Update the user's guide with sync and `rstest` examples.
  - Requires 2.2.2.
  - See terms-of-reference.md §§5-7.
  - Success: examples cover assertion failure, `Result::Err`, strict XPASS,
    and per-case `rstest` placement.

## 3. Vertical slice: async tests keep runtime ownership

Idea: if async expected failures work without selecting a runtime, the macro
can serve real-world `rstest` suites while respecting Rust async ecosystem
boundaries.

This phase adds async support only after the sync contract is proven.

### 3.1. Validate the async catching strategy

This step answers whether future-level catching is compatible with the
supported runtime macro order and whether the dependency belongs behind a
feature flag.

- [ ] 3.1.1. Spike `expect_fail_async` behind the chosen async feature.
  - Requires 1.1.3 and 1.2.3.
  - See xfail-design.md §9.
  - Success: the helper classifies passing, panicking, and `Err` futures
    without installing a runtime.
- [ ] 3.1.2. Add compatibility fixtures for `tokio`, `async-std`, and the
  documented `rstest` async attribute order.
  - Requires 3.1.1.
  - See xfail-design.md §§8-9, 12.
  - Success: unsupported macro orders fail with compile-time diagnostics or
    are excluded from documented support.

### 3.2. Publish async user surface

This step turns the async spike into a stable user-facing contract.

- [ ] 3.2.1. Extend `#[xfail]` rewriting for async functions.
  - Requires 3.1.2.
  - See xfail-design.md §§7, 9.
  - Success: async functions preserve their return type inside the generated
    future and expose `()` to the runtime test wrapper.
- [ ] 3.2.2. Add async examples and feature notes to the user's guide and
  developer's guide.
  - Requires 3.2.1.
  - See terms-of-reference.md §§6-8.
  - Success: docs state the runtime ownership rule and supported attribute
    order.

## 4. Vertical slice: `rstest-bdd` consumes shared xfail semantics

Idea: if `rstest-bdd` can classify expected failures through
`rstest-xfail-core`, ordinary tests and BDD scenarios share one policy without
forcing BDD users through a standalone attribute macro.

This phase designs and implements the downstream integration boundary.

### 4.1. Add BDD-facing core adapters

This step answers what `rstest-bdd` needs from the core crate beyond ordinary
test classification.

- [ ] 4.1.1. Add core helpers that classify pre-observed `BodyOutcome` values
  without executing a closure.
  - Requires 1.2.3.
  - See xfail-design.md §§6, 10-11.
  - Success: BDD code can pass step `Err`, panic, or success outcomes into the
    classifier directly.
- [ ] 4.1.2. Stabilize structured outcome accessors for external reporters.
  - Requires 4.1.1.
  - See xfail-design.md §§10-11.
  - Success: downstream adapters can report XFAIL and XPASS without parsing
    display strings.

### 4.2. Integrate with `rstest-bdd`

This step answers whether expected failure is scenario execution policy and
which macro syntax expresses it.

- [ ] 4.2.1. Decide and document the `rstest-bdd` macro syntax.
  - Requires 4.1.2.
  - See terms-of-reference.md §9 and xfail-design.md §10.
  - Success: the decision names whether `#[then(..., xfail = "...")]`,
    `#[then_xfail(...)]`, or both ship.
- [ ] 4.2.2. Implement BDD expected-failure execution through
  `rstest-xfail-core`.
  - Requires 4.2.1.
  - See xfail-design.md §10.
  - Success: `Then` steps record XFAIL, strict XPASS fails the scenario, and
    explicit BDD skips remain skips.
- [ ] 4.2.3. Add BDD reporting examples and compatibility notes.
  - Requires 4.2.2.
  - See xfail-design.md §§10-11.
  - Success: documentation explains why `StepExecution::Skipped` is not an
    xfail substitute.

## 5. Hardening phase: make the compatibility matrix boring

Idea: if the macro and core pass a compact but representative matrix of failure
modes, return styles, and macro orders, users can trust xfail markers as
regression signals rather than as fragile test-suite exceptions.

This phase closes the risks that remain after the vertical slices.

### 5.1. Cover the interaction matrix

This step answers whether feature combinations behave according to the design,
not only the happy-path examples.

- [ ] 5.1.1. Add a generated matrix for strictness, mode, message matching,
  and body outcome.
  - Requires phase 3.
  - See xfail-design.md §12.
  - Success: each matrix row asserts the exact `XfailOutcome` and adapter
    behaviour.
- [ ] 5.1.2. Add compile-fail tests for unsupported macro placements and
  unsupported signatures.
  - Requires 2.2.1 and 3.1.2.
  - See xfail-design.md §§7-9.
  - Success: diagnostics are stable enough for review and teach the supported
    syntax.

### 5.2. Prepare release documentation

This step answers whether a new user can adopt the crate without reading the
design document.

- [ ] 5.2.1. Replace the generated README with a user-facing crate overview.
  - Requires 2.2.3 and 3.2.2.
  - See terms-of-reference.md §§4-7.
  - Success: README shows the smallest sync, `rstest`, and async examples and
    links to the user's guide.
- [ ] 5.2.2. Update repository layout and developer workflow documentation for
  the workspace crates and test suites.
  - Requires phases 1-4.
  - See xfail-design.md §5.
  - Success: docs describe ownership boundaries for core, macros, facade,
    `trybuild`, and BDD integration tests.

## 6. Deferred extensions

Idea: if the core v1 promise is already trustworthy under libtest, later
extensions can be judged by reporting value rather than by pressure to fix the
basic expected-failure workflow.

### 6.1. Rich reporting adapters

This step covers reporting improvements that need more than libtest's default
output.

- [ ] 6.1.1. Evaluate nextest, JUnit, or custom reporter output for native
  XFAIL and XPASS buckets.
  - Requires phase 5.
  - See terms-of-reference.md §6.2 and xfail-design.md §11.
  - Success: the evaluation names one supported reporter path or explicitly
    defers richer reporting.

### 6.2. Conditional xfail

This step covers pytest-like condition support after the base marker is stable.

- [ ] 6.2.1. Design conditional xfail syntax and compile-time limitations.
  - Requires phase 5.
  - See pytest prior art cited in xfail-design.md §15.
  - Success: the proposal distinguishes compile-time conditions from runtime
    imperative xfail and avoids evaluating arbitrary runtime expressions in
    macro metadata.
