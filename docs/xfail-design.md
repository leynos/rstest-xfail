# rstest-xfail technical design

Status: Draft v0.1.

Audience: maintainers and implementers of `rstest-xfail` and downstream
`rstest-bdd` expected-failure support.

Companion documents:

- [Terms of reference](terms-of-reference.md).
- [Roadmap](roadmap.md).
- [Repository layout](repository-layout.md).
- [Documentation style guide](documentation-style-guide.md).

Last substantive revision: 2026-06-07.

## 1. Problem statement

Rust developers using `rstest` need pytest-style expected failures without
leaving the stock Rust test harness. `#[should_panic]` is insufficient because
it requires a `()` return type, only treats panic as success, and does not
distinguish a known failing test from a test that should panic as part of the
specified behaviour. `#[ignore]` is also insufficient because it prevents the
test from running.

`rstest-xfail` provides a small attribute macro for ordinary tests and a shared
runtime classifier for downstream frameworks. The classifier is split into
`rstest-xfail-core` so `rstest-bdd` can classify scenario-step outcomes without
depending on proc-macro expansion.

## 2. Evidence and constraints

The design rests on five ecosystem facts:

| Fact                                                                                                                          | Design consequence                                                                                           | Source                               |
| ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------ |
| Rust tests pass or fail through `Termination`; `Result<(), E>` is a supported test return shape.                              | The classifier must treat both `()` and `Result<T, E>` as observable body outcomes.                          | Rust Reference testing attributes    |
| `#[should_panic]` requires a `()` return type.                                                                                | `rstest-xfail` cannot be a thin alias for `#[should_panic]`.                                                 | Rust Reference testing attributes    |
| `catch_unwind` catches unwinding panics but not aborting panics, and panic hooks run before the panic is caught.              | Panic classification is useful but bounded; the design must not promise quiet output or abort recovery.      | Rust standard library `catch_unwind` |
| `rstest` documents per-case attributes and async tests with explicit or implicit runtime test attributes.                     | The macro should compose with `rstest` by rewriting the function body and leaving runtime attributes intact. | `rstest` attribute documentation     |
| pytest treats xfail as an executed expected failure and XPASS as an unexpected pass, with strict mode able to fail the suite. | `rstest-xfail` should make strict XPASS the default and document the reporting difference caused by libtest. | pytest xfail documentation           |

## 3. Goals and non-goals

Goals:

- Classify sync test bodies that return `()` or `Result<T, E>`.
- Classify assertion panics as expected failures when they unwind.
- Rewrite annotated functions to return `()` and panic on strict XPASS.
- Preserve `rstest` fixture, case, values, and async runtime integration.
- Provide a core crate that downstream libraries can use directly.
- Keep user-facing syntax explicit and reviewable.

Non-goals:

- Native libtest xfail summary categories.
- A custom test harness.
- Catching aborting panics, process exits, or timeout kills.
- Runtime selection for async tests.
- Automatic semantic inspection of arbitrary error types.

## 4. Terminology

| Term               | Definition                                                                                                                       |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| Expected failure   | A test body outcome that fails in a way permitted by its xfail configuration.                                                    |
| XFAIL              | The reported expected-failure state. Under libtest this is still an `ok` test unless an adapter records richer output elsewhere. |
| XPASS              | A test marked xfail that observed a passing body outcome. In strict mode this panics and fails the test.                         |
| Unexpected failure | A failing body outcome that does not satisfy the xfail policy, such as the wrong failure mode or a failed message match.         |
| Body outcome       | The raw result of executing the original user body before xfail policy is applied.                                               |
| Xfail policy       | Reason, strictness, mode, and optional message matching rules used to classify the body outcome.                                 |
| Adapter            | Code that maps the shared core classifier into a surface: proc macro, async helper, or `rstest-bdd` step integration.            |

## 5. Architecture

The repository should become a Cargo workspace with three crates:

| Crate                 | Kind           | Responsibility                                                                                      |
| --------------------- | -------------- | --------------------------------------------------------------------------------------------------- |
| `rstest-xfail-core`   | Library        | Owns outcome types, policy types, body-result conversion traits, and sync classification functions. |
| `rstest-xfail-macros` | Proc macro     | Parses `#[xfail(...)]`, rewrites functions, and emits calls into the runtime crate.                 |
| `rstest-xfail`        | Facade library | Re-exports `#[xfail]` and public core types for normal users.                                       |

The split keeps the proc macro out of downstream runtime integrations.
`rstest-bdd` should depend on `rstest-xfail-core` when it wants classification
semantics, not on `rstest-xfail-macros`.

`rstest-xfail` must not implement BDD-specific attributes. `rstest-bdd` owns the
`#[given]`, `#[when]`, `#[then]`, and any xfail-aware BDD macro surface; this
workspace supplies only the reusable classification logic that those macros
consume.

### 5.1. Data flow

1. A user writes `#[xfail(reason = "...")]` on a test function.
2. `rstest-xfail-macros` parses the attribute into a compile-time policy
   expression.
3. The macro stores the original return type and original body.
4. The macro rewrites the function to return `()`.
5. The rewritten body calls
   `rstest_xfail::expect_fail(policy, || -> Original { original_body })`.
6. `rstest-xfail-core` catches unwinding panics, converts non-panicking return
   values into body outcomes, and applies policy.
7. The adapter maps the classified outcome back to harness behaviour:
   - `Xfail` prints or records expected-failure detail and lets the rewritten
     test return `()`.
   - strict `Xpass` panics so the harness fails the test.
   - `UnexpectedFailure` panics with the original failure detail so the harness
     still fails the test.

An unexpected failure is still a failure. A body that fails with the wrong
mode, or whose rendered panic or error message does not satisfy `contains`,
must never be reported as a passing test after the macro rewrites the function
to return `()`.

Async functions follow the same policy boundary, but the body executes through
an async helper:

```rust
rstest_xfail::expect_fail_async(policy, async move {
    original_body
})
.await
```

The macro must preserve the user's runtime test attribute such as
`#[tokio::test]`. It must not install one.

## 6. Core crate contract

`rstest-xfail-core` owns the stable classification vocabulary:

```rust
pub struct XfailPolicy {
    pub reason: &'static str,
    pub strict: Strictness,
    pub mode: FailureMode,
    pub expected_message: Option<&'static str>,
}

pub enum Strictness {
    Strict,
    NonStrict,
}

pub enum FailureMode {
    Any,
    Panic,
    Result,
}

pub enum BodyOutcome {
    Passed,
    Panicked { message: Option<String> },
    ReturnedError { message: String },
}

pub enum XfailOutcome {
    Xfail { reason: &'static str, detail: Option<String> },
    Xpass { reason: &'static str },
    UnexpectedFailure { reason: &'static str, detail: Option<String> },
}
```

The first implementation may keep fields private and expose constructors if
that produces a cleaner public API. The important contract is that adapters can
ask the core to classify a body outcome without knowing how the outcome was
observed.

`UnexpectedFailure` is a failing outcome, not a reporting category that keeps
the suite green. Adapters must convert it to a harness failure after recording
or rendering the mismatch detail.

### 6.1. Body-result conversion

The core crate uses a trait to avoid syntactic detection of result aliases:

```rust
pub trait IntoBodyOutcome {
    fn into_body_outcome(self) -> BodyOutcome;
}

impl IntoBodyOutcome for () {
    fn into_body_outcome(self) -> BodyOutcome { BodyOutcome::Passed }
}

impl<T, E> IntoBodyOutcome for Result<T, E>
where
    E: core::fmt::Debug,
{
    fn into_body_outcome(self) -> BodyOutcome {
        match self {
            Ok(_) => BodyOutcome::Passed,
            Err(error) => BodyOutcome::ReturnedError {
                message: format!("{error:?}"),
            },
        }
    }
}
```

This intentionally treats `Ok(T)` as pass, not only `Ok(())`. The Rust harness
accepts return types implementing `Termination`, but the xfail body is no
longer returned to libtest after macro rewriting. Accepting `Result<T, E>`
inside the classifier keeps the design flexible for helper functions while the
macro examples should still document `Result<(), E>` as the ordinary test shape.

### 6.2. Panic observation

The sync adapter uses `std::panic::catch_unwind` with `AssertUnwindSafe`.
`catch_unwind` is not a general exception mechanism; in this design it is a
test harness adapter for the specific panic-as-test-failure convention used by
Rust assertions.

The core must extract panic payloads conservatively:

- `&'static str` and `String` payloads become messages.
- Other payloads become `None` or a stable placeholder.
- Dropping the panic payload must happen in one place so future hardening can
  address payload drop panics.

The macro must not replace the global panic hook by default. Hook mutation is
global process state and would be noisy in parallel tests.

## 7. Attribute macro contract

The user-facing macro accepts explicit named arguments:

```rust
#[xfail(reason = "BUG-123: parser accepts empty input")]
#[xfail(reason = "BUG-123", strict = true)]
#[xfail(reason = "BUG-123", mode = "panic")]
#[xfail(reason = "BUG-123", mode = "result")]
#[xfail(reason = "BUG-123", contains = "invalid input")]
```

Rules:

- `reason` is required and must be a string literal.
- `strict` defaults to `true`.
- `mode` defaults to `"any"`.
- `contains` matches the panic or error message after outcome observation.
- Unknown arguments are compile errors.
- `#[xfail]` on a non-function item is a compile error.
- `#[xfail]` on functions with unsupported signatures is a compile error with
  a diagnostic that names the unsupported construct.

The macro should preserve:

- visibility,
- function name,
- generics,
- where clauses,
- argument list,
- inert attributes such as `#[allow(...)]`,
- doc comments,
- runtime test attributes, and
- `rstest` attributes that have not yet expanded.

The macro removes only its own active attribute and rewrites the body.

## 8. `rstest` composition

`rstest` documents that attributes before a `#[case]` apply to that generated
case and attributes after the final case apply to all generated cases. That
supports two user-facing patterns:

```rust
#[rstest]
#[case::normal("abc", true)]
#[xfail(reason = "BUG-123: empty input still passes validation")]
#[case::known_bug("", false)]
fn validates_input(#[case] input: &str, #[case] expected: bool) {
    assert_eq!(validate(input), expected);
}
```

```rust
#[rstest]
#[case(1)]
#[case(2)]
#[xfail(reason = "BUG-456: all generated cases document the same bug")]
fn generated_cases_are_expected_to_fail(#[case] value: u32) {
    assert_eq!(0, value);
}
```

The compatibility suite must include both attribute orders:

- `#[rstest]` outside `#[xfail]`, where `rstest` sees and forwards the xfail
  attribute to generated functions.
- `#[xfail]` outside `#[rstest]`, if the macro can preserve enough shape for
  `rstest` to expand afterwards.

The documented supported order should be the order proven stable by `trybuild`
and runtime tests. If only one order is reliable, the macro must diagnose or
document the other as unsupported.

## 9. Async design

Async support must not choose a runtime. Users continue to write the runtime
attribute required by their test framework:

```rust
#[rstest]
#[case("bad-input")]
#[xfail(reason = "BUG-789: async parser accepts bad input")]
#[tokio::test]
async fn rejects_bad_input(#[case] input: &str) -> anyhow::Result<()> {
    parse_async(input).await?;
    Ok(())
}
```

There are two implementation paths:

| Path                     | Mechanism                                                               | Benefit                                                      | Cost                                                                                          |
| ------------------------ | ----------------------------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| Runtime-wrapper catching | Let the runtime macro produce a sync wrapper and catch at that wrapper. | Avoids a future-catching dependency.                         | Depends heavily on macro expansion order and may miss failures inside generated runtime code. |
| Future-level catching    | Use `FutureExt::catch_unwind` in the rewritten async body.              | Classifies failures where they occur and keeps policy local. | Requires an optional dependency and unwind-safety handling for futures.                       |

The design chooses future-level catching behind an `async` feature for v1 if
the spike confirms compatibility with the supported runtime macros. If the
spike exposes brittle macro ordering, v1 should document sync-only macro
support and ship async support as an explicit helper until the macro contract
is proven.

## 10. `rstest-bdd` integration

`rstest-bdd` owns the BDD attribute implementation. It should not rely on
stacking `#[xfail]` from this crate with `#[then]` as the primary integration. A
`Then` function is registered into a scenario runtime; expected failure is
scenario execution policy.

The preferred BDD surface is native metadata on the BDD macro implemented in
`rstest-bdd`:

```rust
#[then(
    "the report includes harness stderr",
    xfail = "BUG-456: report tab does not include harness stderr"
)]
fn report_includes_harness_stderr(state: &ScenarioState) -> anyhow::Result<()> {
    assert!(state.report().contains("stderr"));
    Ok(())
}
```

An alternate `rstest-bdd` compatibility surface may be:

```rust
#[then_xfail(
    "the report includes harness stderr",
    reason = "BUG-456: report tab does not include harness stderr"
)]
fn report_includes_harness_stderr(state: &ScenarioState) -> anyhow::Result<()> {
    assert!(state.report().contains("stderr"));
    Ok(())
}
```

The `rstest-bdd` adapter should:

- execute the step body,
- classify panic or `Err` through `rstest-xfail-core`,
- record XFAIL in BDD reporting,
- fail the scenario on strict XPASS, and
- preserve ordinary skip behaviour for explicit BDD skips.

`StepExecution::Skipped` is not an xfail substitute. Skip means the scenario
requested no further execution; xfail means the relevant behaviour executed and
failed in an expected way.

## 11. Reporting

The stock harness cannot report an expected-failure bucket. The facade adapter
therefore has two obligations:

- On XFAIL, emit a concise diagnostic that includes `XFAIL` and the reason.
- On strict XPASS, panic with a concise diagnostic that includes `XPASS` and
  the reason.
- On `UnexpectedFailure`, panic with a concise diagnostic that includes the
  xfail reason, the observed failure detail, and the policy mismatch. Examples
  include `mode = "panic"` receiving `Result::Err`, `mode = "result"` receiving
  a panic, or `contains = "..."` not matching the rendered failure message.

The core crate should return structured `XfailOutcome` values and leave output
policy to adapters. That keeps BDD reporting independent from libtest output
and avoids baking `eprintln!` into the reusable core.

## 12. Verification strategy

The correctness property is small enough to state precisely:

| Property                                                                            | Verification method                                               |
| ----------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| A passing body classified under strict xfail becomes XPASS and fails through panic. | Unit tests over core classification plus runtime macro tests.     |
| A panicking body classified under default mode becomes XFAIL.                       | Unit tests using `catch_unwind` and runtime macro tests.          |
| A `Result::Err` body classified under default mode becomes XFAIL.                   | Unit tests over `IntoBodyOutcome` and runtime macro tests.        |
| `mode = "panic"` rejects `Result::Err` as unexpected failure and fails the harness. | Unit tests over policy classification plus runtime macro tests.   |
| `mode = "result"` rejects panic as unexpected failure and fails the harness.        | Unit tests over policy classification plus runtime macro tests.   |
| `contains = "..."` mismatch becomes unexpected failure and fails the harness.       | Unit tests for panic and error messages plus runtime macro tests. |
| `rstest` per-case xfail affects only the intended generated case.                   | `trybuild` compile tests plus black-box generated-test fixtures.  |
| Async xfail works with each supported runtime macro and documented attribute order. | Feature-gated `trybuild` cases and runtime tests.                 |

The combinatorial surface is the interaction between return style, failure
style, strictness, mode, message matching, `rstest` case placement, and async
runtime macro order. The implementation must include a compact matrix rather
than only one example per feature.

## 13. Risks and trade-offs

| Risk                                                                       | Consequence                                                                    | Mitigation                                                                                      |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| Proc-macro stacking differs across `rstest`, runtime macros, and `xfail`.  | Valid-looking examples fail to compile or classify at the wrong layer.         | Treat supported attribute order as a tested contract and reject or document unsupported orders. |
| Panic hooks print noise before caught panics.                              | XFAIL output may contain panic-hook text.                                      | Do not mutate global hooks by default; document the behaviour.                                  |
| Non-strict XPASS hides fixed bugs.                                         | Stale xfails accumulate.                                                       | Default to strict and require explicit opt-out if non-strict ships.                             |
| Unexpected failures are treated as expected failures after body rewriting. | A mismatched mode or `contains` policy can make a genuinely failing test pass. | Require adapters to panic on `UnexpectedFailure` and cover that path in runtime macro tests.    |
| Message matching on `Debug` output is brittle.                             | Error formatting changes can flip classification.                              | Document `contains` as a convenience, not a semantic error contract.                            |
| `rstest-xfail` implements BDD macro syntax directly.                       | `rstest-xfail` and `rstest-bdd` diverge, and BDD ownership becomes unclear.    | Keep classification in core and implement BDD attributes in `rstest-bdd`.                       |

## 14. Deferred decisions

- Whether non-strict XPASS ships in v1 or remains deferred.
- Whether async support is enabled by default or feature-gated.
- The exact BDD macro syntax.
- Whether the facade crate re-exports all core types or only stable policy
  constructors.
- Whether future versions should emit machine-readable output for external
  reporters.

## 15. References

- `rstest` attribute macro documentation, accessed 2026-06-07:
  <https://docs.rs/rstest/latest/rstest/attr.rstest.html>.
- Rust Reference testing attributes, accessed 2026-06-07:
  <https://doc.rust-lang.org/reference/attributes/testing.html>.
- Rust Reference attributes, accessed 2026-06-07:
  <https://doc.rust-lang.org/reference/attributes.html>.
- Rust standard library `catch_unwind`, accessed 2026-06-07:
  <https://doc.rust-lang.org/std/panic/fn.catch_unwind.html>.
- pytest skip and xfail documentation, accessed 2026-06-07:
  <https://docs.pytest.org/en/stable/how-to/skipping.html>.
- `rstest-bdd` crate documentation, accessed 2026-06-07:
  <https://docs.rs/rstest-bdd>.
- `rstest-bdd-macros` `then` macro documentation, accessed 2026-06-07:
  <https://docs.rs/rstest-bdd-macros/latest/rstest_bdd_macros/attr.then.html>.
