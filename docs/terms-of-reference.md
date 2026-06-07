# rstest-xfail terms of reference

Status: Draft v0.1.

Audience: maintainers, contributors, and reviewers deciding whether the
`rstest-xfail` design is solving the right problem.

Companion documents:
[technical design](xfail-design.md), [roadmap](roadmap.md), [documentation contents](contents.md),
and [documentation style guide](documentation-style-guide.md).

Last substantive revision: 2026-06-07.

## 1. Background and motivation

Rust's stock test harness recognises passing tests, failing tests, and ignored
tests. It also recognises `#[should_panic]`, but that marker means "panic is
success" and requires the test function to return `()`. That does not model the
pytest-style expected-failure workflow where the test still runs, expected
failure keeps the suite green, and an unexpected pass draws attention to a bug
that may have been fixed.

`rstest` already gives Rust projects a parameterized test style close to what
Python users know from pytest. Its current attribute model supports per-case
attributes, `Result`-returning tests, and async tests with explicit or implicit
runtime test attributes. The missing piece is an expected-failure marker that
works with those forms without asking projects to replace libtest, replace
`rstest`, or rewrite failing assertions into manual helper calls.

`rstest-bdd` has the same motivation at scenario-step level. A `Then` step can
encode behaviour that is known to be wrong today but should stay executable.
Skipping the step loses evidence; accepting the failure as a normal failure
blocks delivery; treating it as an expected failure preserves the regression
signal while keeping the suite useful.

## 2. Domain

The domain is Rust test authoring for library, application, and
behaviour-driven test suites.

Relevant conventions:

- Rust's built-in harness executes functions marked with `#[test]` and
  classifies the returned value through `Termination`.
- `Result<(), E>` tests are a normal Rust harness pattern: `Ok(())` passes and
  `Err(E)` fails.
- Assertion-style failures usually arrive as unwinding panics.
- `rstest` expands one parameterized function into independent generated tests,
  and supports applying attributes to specific generated cases.
- Async `rstest` cases depend on a runtime test attribute such as
  `#[tokio::test]`, because `rstest` does not choose an async runtime for the
  user.
- `rstest-bdd` registers Gherkin step functions and executes them through a
  step registry, so a step outcome is part of scenario execution policy rather
  than only a function-level libtest result.

Prior art:

- `pytest.mark.xfail` defines the user-facing vocabulary: `XFAIL` for expected
  failure and `XPASS` for unexpected pass.
- Rust's `#[should_panic]` is a partial substitute for panic-only tests, but it
  does not cover `Result` tests and cannot express strict XPASS semantics
  without making every pass look like a panic mismatch.
- The separate `rustest` crate advertises xfail-style support through a custom
  harness. `rstest-xfail` deliberately targets `rstest` and libtest-compatible
  workflows instead.

## 3. Market context

The current default is one of four workarounds:

| Alternative                   | What it gives users                             | Deficiency                                                                           |
| ----------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------ |
| `#[ignore = "..."]`           | Keeps a known-bad test compiled.                | Does not execute the test, so it cannot detect a fix.                                |
| `#[should_panic]`             | Lets a panic-only failing test pass.            | Rejects `Result` tests and does not report expected failure intent clearly.          |
| Manual `catch_unwind` helpers | Can invert assertion failures in one test body. | Repeats boilerplate and does not integrate cleanly with `rstest` cases or BDD steps. |
| Custom test harnesses         | Can report native xfail buckets.                | Require a larger adoption decision than most `rstest` projects want.                 |

The gap is an ergonomics and correctness gap. Users can express "this should
fail today" by hand, but the expression is verbose, inconsistent, and easy to
forget when the bug is fixed.

## 4. Users and stakeholders

| Group                    | Role and context                                                    | Cares about                                                                  | Will dislike                                                                    | Current alternative                                |
| ------------------------ | ------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------- |
| `rstest` users           | Rust developers writing parameterized unit and integration tests.   | Marking individual known-bad cases without losing execution.                 | Replacing their test harness or splitting tests into helper wrappers.           | `#[should_panic]`, `#[ignore]`, or manual helpers. |
| Async test authors       | Rust developers using runtime macros such as `#[tokio::test]`.      | Preserving runtime-specific setup while classifying expected failures.       | A macro that assumes one runtime or blocks async support behind awkward syntax. | Manual helpers inside async bodies.                |
| `rstest-bdd` maintainers | Maintainers integrating expected failure into scenario execution.   | A shared classifier that keeps BDD semantics consistent with ordinary tests. | Depending on a proc macro crate when only runtime classification is needed.     | Bespoke BDD-only outcome code.                     |
| Reviewers and CI owners  | People reading test output and deciding whether a suite is healthy. | Strict XPASS failures that expose fixed bugs and stale xfails.               | Expected failures hidden as ordinary passing tests with no message.             | Manual policy in reviews.                          |

Non-users:

- Projects that need a native test-summary xfail bucket from libtest. The stock
  harness does not expose such a state.
- Projects that already use a custom harness and want all reporting behaviour
  centralized there.
- Tests that abort the process rather than unwind, because `catch_unwind`
  cannot recover from aborting panics.

## 5. Job to be done

When a Rust developer has a test that documents a known bug or missing feature,
they want to keep the test executing while treating its current failure as
expected, so they can notice when the implementation starts passing and remove
the expected-failure marker.

When an `rstest` user has one failing case among many parameterized cases, they
want to mark only that generated case, so they can keep healthy cases as normal
tests and avoid broad `should_panic` annotations.

When an `rstest-bdd` maintainer adds expected-failure support to scenario
steps, they want the same outcome classification used by ordinary tests, so BDD
reporting and macro-level test behaviour do not diverge.

## 6. Scope

### 6.1. Goals

- Provide an attribute macro for ordinary sync tests that classifies both panic
  failures and `Result::Err` returns as expected failures.
- Support `rstest` generated tests, including per-case use where `rstest`
  forwards attributes to generated cases.
- Support async tests without choosing a runtime for users.
- Export `rstest-xfail-core` as a runtime-only crate that owns outcome
  classification and can be consumed by `rstest-bdd`.
- Make strict XPASS the default so a fixed bug fails the suite and prompts
  removal of the expected-failure marker.
- Preserve compatibility with Rust's default harness instead of requiring a
  bespoke runner.

### 6.2. Non-goals

- Native libtest summary categories for `XFAIL` and `XPASS` are out of scope.
  The design may print clear messages, but libtest will still summarize strict
  expected failures as passing tests and strict unexpected passes as failures.
- Replacing `rstest`, `rstest-bdd`, or async runtime macros is out of scope.
- Catching aborting panics, process exits, segmentation faults, or timeouts is
  out of scope for v1.
- Inferring project-specific error taxonomies from arbitrary error types is out
  of scope. Matching can use rendered panic or error messages, not semantic
  downcasting across all possible error types.
- Making xfail silently non-strict by default is out of scope because it hides
  fixed bugs.

## 7. Success criteria

User-facing success:

- A user can write `#[xfail(reason = "...")]` on a sync test returning `()` or
  `Result<(), E>` and get the expected fail or strict XPASS behaviour.
- A user can place `#[xfail(reason = "...")]` before a specific `#[case]` in an
  `rstest` test and affect only that case.
- A user can mark async tests using the documented attribute order while keeping
  their chosen runtime test macro.
- `rstest-bdd` can depend on `rstest-xfail-core` without depending on the
  proc-macro crate.

Operational success:

- The workspace builds with strict lint settings and denies warnings.
- Macro expansion failures are compile-time diagnostics with actionable spans.
- The public examples compile under the repository's documented gates.

Strategic success:

- The project establishes one shared xfail vocabulary for `rstest`,
  async tests, and `rstest-bdd`.
- The core crate boundary lets downstream libraries reuse classification logic
  without duplicating policy.

## 8. Constraints and assumptions

### 8.1. Hard constraints

- The crate must work with Rust's stock test harness.
- The public classification logic must live in an exported
  `rstest-xfail-core` crate.
- The user-facing attribute macro must support `rstest` and async tests.
- Documentation and code must follow this repository's strict lint,
  formatting, and documentation policy.

### 8.2. Assumptions

- Tests that fail through assertions do so by unwinding panic. If a project
  builds tests with `panic = "abort"` or aborts through foreign code, xfail
  cannot classify that failure.
- `rstest` continues to preserve function attributes in the documented per-case
  positions. If that contract changes, per-case xfail composition needs a
  compatibility update.
- Async users can supply the runtime test attribute required by their runtime.
  If they cannot, `rstest-xfail` cannot make an async function executable on
  its own.
- `rstest-bdd` maintainers can add native xfail metadata to their macro and
  runtime surface. If not, the standalone attribute macro remains possible but
  more fragile because it depends on proc-macro stacking.

### 8.3. Dependencies

- Rust standard library panic and test harness behaviour.
- `rstest` macro expansion and per-case attribute forwarding.
- `syn`, `quote`, and `proc-macro2` for the proc-macro crate.
- `futures-util` or an equivalent optional dependency if async classification
  catches panics inside the future rather than only outside the runtime wrapper.
- `rstest-bdd` for the downstream integration that consumes
  `rstest-xfail-core`.

## 9. Open questions

| Question                                                                                   | Why it matters                                                                                     | Resolution path                                                                         |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Should v1 expose `strict = false`, or reserve non-strict XPASS for a later release?        | Non-strict XPASS mirrors pytest but weakens CI feedback.                                           | Decide in an Architecture Decision Record (ADR) before stabilizing the macro arguments. |
| Should message matching be called `contains`, `expected`, or `matches`?                    | The name affects user intuition and compatibility with Rust's `#[should_panic(expected = "...")]`. | Prototype macro syntax and review examples in the user's guide.                         |
| Should async xfail require an `async` feature using `FutureExt::catch_unwind`?             | The dependency changes the core surface and feature matrix.                                        | Spike sync wrapper and future-level catching with `trybuild` cases.                     |
| Should `rstest-bdd` expose `#[then(..., xfail = "...")]`, `#[then_xfail(...)]`, or both?   | Macro syntax becomes part of the BDD user-facing API.                                              | Decide in the `rstest-bdd` integration design before implementation.                    |
| Should xfail messages use `eprintln!`, `tracing`, or return structured records to callers? | Output policy affects libtest noise and downstream reporting.                                      | Let `rstest-xfail-core` return records and keep printing in adapters.                   |

## Appendix A. References

- `rstest` attribute macro documentation, accessed 2026-06-07:
  <https://docs.rs/rstest/latest/rstest/attr.rstest.html>.
- Rust Reference testing attributes, accessed 2026-06-07:
  <https://doc.rust-lang.org/reference/attributes/testing.html>.
- Rust standard library `catch_unwind`, accessed 2026-06-07:
  <https://doc.rust-lang.org/std/panic/fn.catch_unwind.html>.
- pytest skip and xfail documentation, accessed 2026-06-07:
  <https://docs.pytest.org/en/stable/how-to/skipping.html>.
- `rstest-bdd` crate documentation, accessed 2026-06-07:
  <https://docs.rs/rstest-bdd>.
