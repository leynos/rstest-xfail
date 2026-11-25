# Architectural decision record (ADR) 0003: Strict XPASS default and non-strict policy

## Status

Accepted, 2026-11-25. Expected-failure markers are strict by default: an
unexpected pass (XPASS) fails the test and the suite. Version 1 also ships a
local, opt-in `strict = false` setting that keeps XPASS classification but lets
the marked test pass as far as the harness is concerned.

## Date

2026-11-25.

## Context and problem statement

`rstest-xfail` marks a test body as an expected failure (XFAIL) so the body
keeps running while its current failure is tolerated. When that body passes
instead, the result is an unexpected pass (XPASS). The policy question is what
an XPASS should do to the suite, and whether version 1 offers any way to relax
it.

The terms of reference require strict XPASS by default so a fixed bug fails the
suite and prompts removal of the marker, and they exclude silently non-strict
behaviour because it hides fixed bugs (terms of reference §§6.1-6.2). At the
time this record was drafted, section 9 left open whether `strict = false`
would ship in version 1 or be deferred. The technical design proposes both
`Strictness::Strict` and `Strictness::NonStrict` (§6), documents `strict` as
defaulting to `true` (§7), and had deferred the release decision (§14). Roadmap
task 1.1.2 requires an accepted record that answers the version 1 question and
names the consequence for Continuous Integration (CI) users.

Stock Rust test harnesses have no XFAIL or XPASS summary category. A test that
returns `()` or `Ok(())` passes, and a panic or `Err` fails: the classifier and
its adapters decide which harness outcome a classification maps to. That
freedom makes the XPASS policy a real choice rather than a harness constraint.

pytest is comparative prior art, not the authority for this project's default.
It reports XFAIL and XPASS without failing the suite unless `strict = True` is
set, and it offers an `xfail_strict` configuration default. `rstest-xfail`
adopts the vocabulary but not that default.

## Decision drivers

- A fixed bug should fail a suite, not leave a stale marker in place.
- Adopters migrating a suite of known-failing tests need a staged cleanup path
  that keeps the marker and its reason visible while the suite stays workable.
- The stock harness cannot report XPASS on its own, so any relaxed setting must
  still be explicit, reported by an adapter, and impossible to confuse with a
  permitted failure.
- Classification must remain independent of harness mapping so that
  `rstest-bdd` and other adapters reuse one policy (ADR 0002).
- The version 1 contract should be small, reviewable, and settled before
  downstream users depend on macro arguments.

## Requirements

### Functional requirements

- An omitted `strict` argument behaves exactly like `strict = true`.
- Version 1 accepts `strict = false` as a local, per-marker opt-out. There is
  no global, workspace, or environment override.
- The test body executes under either setting. Non-strict never means skipping,
  ignoring, or shortening the body.
- A permitted failure remains XFAIL under both settings.
- A failure that does not satisfy the configured failure mode or message
  condition is an unexpected failure and fails the harness under both settings.
- Under `strict = false`, an XPASS keeps its XPASS classification and is
  reported by the adapter even though the marked test passes the harness.
- An adapter emits a concise XPASS diagnostic under `strict = false`. The
  diagnostic is best effort: a harness may capture or hide output from
  successful tests.

### Technical requirements

- Classification depends only on the raw body outcome and the configured
  failure mode and message policy. It does not read strictness.
- Strictness maps a classification to a harness result in the adapter.
  `XfailOutcome` retains the classification for reporting and downstream
  adapters.
- `Strictness::Strict` is the default for the core policy and for the macro
  argument parser, whose only route to `Strictness::NonStrict` is an explicit
  `strict = false`. The core exposes the vocabulary to adapters but adds no
  global, workspace, or environment default switch.
- Adapters panic on every unexpected failure, matching the design requirement
  that a mismatched failure can never be rewritten into a passing test.

## Options considered

### Option A: Strict-only version 1

Defer `strict = false` to a later release. This gives the smallest contract and
the strongest CI feedback: every XPASS fails. The cost is that a project
adopting `rstest-xfail` must triage or remove each marker whose test starts to
pass (XPASS) before its suite can be green, and the `strict` argument would
accept only `true` if it shipped at all.

### Option B: Explicit opt-out with a strict default

Ship `strict = false` in version 1, keep strict XPASS as the default, and
document the CI consequence. This preserves pytest's two-policy vocabulary and
permits staged adoption: known-failing tests keep executing, and recovered
cases can still be reported while markers are cleaned up. The cost is weaker
stale-marker detection for opted-out tests and a larger version 1 contract.

### Option C: Non-strict default

Mirror pytest's default and fail the suite only for explicit `strict = true`.
Rejected by the terms of reference: silently non-strict xfail hides fixed bugs
and is an explicit non-goal.

| Dimension               | Option A: strict only    | Option B: explicit opt-out | Option C: non-strict default |
| ----------------------- | ------------------------ | -------------------------- | ---------------------------- |
| Default XPASS result    | Fails suite              | Fails suite                | Passes suite                 |
| Stale-marker detection  | Always                   | Always unless opted out    | Hidden by default            |
| Migration from pytest   | Triage each XPASS marker | Opt out while cleaning up  | None                         |
| Version 1 contract size | Smallest                 | Two policies, one default  | Two policies, one default    |
| Terms-of-reference fit  | Meets                    | Meets                      | Violates §6.2                |

_Table 1: Comparison of strictness options for the version 1 contract._

## Decision outcome

Adopt Option B.

- Strict XPASS is the default. A body that passes under an xfail marker fails
  the test and therefore the suite.
- `strict = false` ships in version 1. It is local to one marker, opt-in only,
  executes the body, retains XPASS classification, and relaxes only the
  marker's harness failure. It does not weaken XFAIL, and it does not accept a
  mismatched failure.
- No global or environment setting changes the default. A project that wants a
  different default cannot configure it; it must annotate the affected markers.
- The core classifies; the adapter maps. The same `XfailOutcome` is produced
  regardless of strictness, so `rstest-bdd` can report an XPASS even when a
  non-strict adapter lets its scenario succeed.
- On XFAIL, an adapter emits a concise diagnostic that includes `XFAIL` and the
  reason. On strict XPASS it panics with `XPASS` and the reason. On non-strict
  XPASS it emits the same XPASS information and lets the marked test pass. On
  an unexpected failure it panics with the reason, observed detail, and policy
  mismatch under both settings.

The complete mapping is:

| Body observation         | Classification    | Strict harness result | Non-strict harness result |
| ------------------------ | ----------------- | --------------------- | ------------------------- |
| Pass (`()` or `Ok`)      | XPASS             | Fail                  | Pass                      |
| Permitted panic or `Err` | XFAIL             | Pass                  | Pass                      |
| Wrong failure mode       | UnexpectedFailure | Fail                  | Fail                      |
| Message mismatch         | UnexpectedFailure | Fail                  | Fail                      |

_Table 2: Classification and harness result by strictness setting._

### Policy invariants

Three invariants state the policy precisely. They are normative for later
implementation and verification; this documentation task does not compile or
prove them.

- **P1, default equivalence:** an omitted strictness and an explicit
  `strict = true` produce identical classification and harness outcomes for the
  same body observation and failure policy.
- **P2, limited relaxation:** changing strict to non-strict changes the harness
  result only for XPASS. XFAIL and unexpected failure keep their results.
- **P3, failure preservation:** no failure-mode or message mismatch becomes a
  success under either setting.

Witnesses: a successful unit return (XPASS), a permitted panic (XFAIL), a
wrong-mode `Err` (unexpected failure), and a failure message missing the
required substring (unexpected failure). The last two reject the incorrect
claim that non-strict accepts mismatches. A suite that also contains an
unrelated failing test rejects the claim that non-strict XPASS guarantees a
green CI run.

### Consequence for CI users

Under the strict default, a fixed bug fails CI until its marker is removed.
That is the intended signal. Under `strict = false`, the marked test passes, so
a suite can stay green after its bug is fixed; the stale marker is visible only
through the adapter's XPASS diagnostic, which the harness may not display for a
successful test. A non-strict opt-out therefore trades away automatic detection
of fixed bugs for that marker. Unrelated failures still fail the suite, so
non-strict XPASS does not make CI green in general; it removes one signal.

## Goals and non-goals

Goals:

- Settle the version 1 strictness question with an explicit default, an
  explicit opt-out, and a stated CI consequence.
- Keep classification independent of harness mapping so all adapters share one
  policy.
- Keep the stock Rust harness and its reporting semantics.

Non-goals:

- Implementing `Strictness`, the classifier, or the `#[xfail]` macro. Roadmap
  1.2.x and 2.1.x own that work.
- Global, workspace, or environment configuration of strictness.
- Native libtest XFAIL and XPASS summary categories.
- Promising visible diagnostics for successful tests. Harness capture rules are
  outside this project's control.
- The async strategy and the `rstest-bdd` macro syntax, which have their own
  roadmap tasks.

## Migration plan

1. Ratify this record and synchronize the design, terms of reference, user
   guide, and developer guide (roadmap task 1.1.2, documentation only).
2. Implement the core policy vocabulary with a strict default and a reachable
   non-strict value in roadmap task 1.2.1.
3. Accept `strict` in the macro argument parser, defaulting to `true`, in
   roadmap task 2.1.1.
4. Cover the table above with classifier tests and end-to-end child test
   processes in roadmap tasks 1.2.3 and 2.1.2. The adapter tests must observe
   the process exit status for strict XPASS, non-strict XPASS, and both
   mismatch cases.

No compatibility layer or data migration is required: no implementation exists
at the time of this decision.

## Known risks and limitations

- Non-strict XPASS can leave a stale marker after its bug is fixed. The opt-out
  is explicit, the adapter reports XPASS, and reviewers should treat opted-out
  markers as cleanup debt.
- The harness may hide diagnostics for successful tests, so the non-strict
  XPASS report is not guaranteed to appear in CI logs.
- libtest has no XPASS bucket, so a non-strict XPASS is summarized as an
  ordinary pass.
- An adapter that treats non-strict as permission to accept any failure would
  break P3. The table and the failure-preservation invariant exist to make that
  error reviewable.

## Outstanding decisions

None for the version 1 strictness question. The message-matching argument name,
async support, and the `rstest-bdd` macro surface remain open in their own
roadmap tasks and do not change this decision.

## Architectural rationale

The decision keeps the pure core responsible for classification and leaves
harness policy to adapters, consistent with ADR 0002. Strictness is a property
of the policy applied by an adapter, not of the observation, so a downstream
consumer such as `rstest-bdd` can keep reporting XPASS without re-deriving the
classification. Choosing strict by default matches the project goal of exposing
fixed bugs, while the explicit opt-out preserves the pytest-style staged
adoption path without making silence the default.

## References

- pytest, "How to use skip and xfail to deal with tests that cannot succeed",
  `strict` parameter, accessed 2026-11-25:
  <https://docs.pytest.org/en/stable/how-to/skipping.html#strict-parameter>.
- Rust Reference, "Testing attributes", accessed 2026-11-25:
  <https://doc.rust-lang.org/reference/attributes/testing.html>.
- [Terms of reference](../terms-of-reference.md) §§6, 9.
- [Technical design](../xfail-design.md) §§6-7, 11-14.
- [Roadmap](../roadmap.md) task 1.1.2.
- [ADR 0002: Cargo workspace and crate boundaries](../adr-002-cargo-workspace-and-crate-boundaries.md).
