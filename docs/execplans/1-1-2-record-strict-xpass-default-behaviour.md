# Record strict XPASS default behaviour (1.1.2)

Status: COMPLETE

This ExecPlan is a living document. Keep its constraints, tolerances, risks,
progress, discoveries, decisions, conformance basis, verification, and outcomes
current. Explicit approval was granted on 2026-11-25. Both milestones are
delivered: ADR 0003 is accepted, the policy documents are synchronized, and
roadmap task 1.1.2 is checked.

## Purpose / big picture

Settle expected-failure policy before downstream users depend on the core
vocabulary or macro arguments. An expected failure (XFAIL) means an executed
test failed in an allowed way. An unexpected pass (XPASS) means that an
expected-to-fail body passed, often because its bug has been fixed.

Recommend strict XPASS by default, with an explicit `strict = false` opt-out in
v1. Strict XPASS fails the test and consequently the suite; non-strict XPASS
does not itself fail the suite. The latter can leave continuous integration
(CI) green despite a stale expected-failure marker. Approval of this plan
accepts this recommendation for the subsequent ADR work.

Success is an accepted ADR answering the v1 question, consistent design and
user guidance, and a completed roadmap entry. This documentation task changes
no runtime behaviour: the current macro remains a placeholder.

## Constraints

- Wait for explicit user approval before creating the ADR or changing policy
  documents. Publishing this plan and its index entry is authorized now.
- Restrict implementation to documentation. Do not modify Rust, manifests,
  lockfiles, build configuration, or dependencies. Do not implement roadmap
  1.2.x, macro parsing, async support, or downstream BDD integration.
- Preserve strict-by-default, stock Rust harness compatibility, and the pure
  core boundary in ADR 002. Non-strict must never mean ignoring the body or
  accepting an unexpected failure.
- Distinguish planned v1 policy from currently available functionality. Do not
  claim that the placeholder enforces the policy.
- Keep roadmap 1.1.2 unchecked until the ADR and associated documentation are
  delivered and verified. Do not mark later tasks complete.
- Follow `AGENTS.md` and the documentation style guide. Run gates sequentially
  with logs under `/tmp`; retain shared Cargo caches and compiler admission.

## Tolerances (exception triggers)

Stop, record the deviation, and obtain approval if the agreed v1 decision must
change, any executable file or dependency needs modification, or policy would
extend to another roadmap task. The expected implementation touches seven
policy documents plus this living plan; more than nine documentation files
requires a scope review. Stop after three unsuccessful fixes for the same
validation failure. Disk exhaustion or unhealthy compiler admission is an
environment blocker, not permission to bypass a gate. No elapsed-time limit
applies. Set status BLOCKED for an unapproved architectural deviation.

## Risks

- High impact, medium likelihood: non-strict XPASS leaves stale markers
  unnoticed. Mitigate with an explicit local opt-out, strict default, and a
  prominent CI warning; do not promise visible successful-test diagnostics.
- Medium impact, medium likelihood: a policy document appears to announce an
  implemented feature. Label examples as planned v1 behaviour and retain the
  scaffold limitation in the users' guide.
- High impact, low likelihood: adapters conflate non-strict with accepting any
  failure. Publish the complete outcome table and mismatch examples below.
- Medium impact, medium likelihood: concurrent work takes ADR number 0003.
  Recheck names, choose the next free number, and update all links together. Do
  not overwrite another decision.

## Progress

- [x] (2026-10-20) Inspect branch ownership and rename the task branch.
- [x] (2026-10-20) Inspect requirements with two Wyvern agents and exchange
  references through context packs.
- [x] (2026-10-20) Check primary pytest and Rust references with Firecrawl.
- [x] (2026-10-20) Review through all six Logisphere expert perspectives and
  incorporate their contract, adoption, and evidence-retention findings.
- [x] (2026-11-04) Restore the missing uncommitted draft from the conversation
  and refresh repository evidence with Wyvern.
- [x] (2026-11-04) Refresh all six expert perspectives; preserve the reviewed
  design and add executable gate-status capture.
- [x] (2026-11-04) Complete the reviewed draft and validate the unchanged
  Rust baseline: lint passed, 24 tests passed, and all doctest suites passed.
- [x] (2026-11-25) Fetch the live PR target and confirm the explicit rebase
  is already up to date; preserve recovery refs and inspect the child patch.
- [x] (2026-11-25) Revalidate the current target: 24 tests and all doctest
  suites passed; typecheck, rustdoc, Clippy, and Whitaker passed.
- [x] (2026-11-25) Obtain explicit plan approval; implementation authorized.
- [x] (2026-11-25) EP-M1: accept ADR 0003 and synchronize the policy
  documents. Gates `make check-fmt`, `make typecheck`, `make lint`, `make test`,
  `make markdownlint` (with spelling), `make nixie`,
  `make test-workflow-contracts`, and `git diff --check` all exited zero.
- [x] (2026-11-25) EP-M2: reconcile evidence, mark roadmap 1.1.2 done, and
  re-run the full gate sequence. All eight gates exited zero; logs and statuses
  are retained as `/tmp/<gate>-rstest-xfail-1-1-2-epm2.out` and `.status`.

## Surprises & discoveries

The core is a placeholder, while design §6 already proposes both
`Strictness::Strict` and `Strictness::NonStrict`. The terms of reference and
design nevertheless leave v1 non-strict availability open. An enum in a draft
is not evidence of an accepted or implemented policy.

The actual Makefile is richer than the abbreviated commands in `AGENTS.md`:
`make lint` includes rustdoc, Clippy, and Whitaker; `make test` prefers nextest
and separately runs doctests. Use the targets without substituting shortcuts.
`make markdownlint` also runs spelling and may regenerate `typos.toml`.

On resumption, the renamed branch remained at the original baseline but the
uncommitted plan and temporary logs were absent. Earlier validation reports in
the conversation are historical evidence, not validation of the restored file.
Preserve gate exit codes in status files as well as foreground tool results.

The 2026-11-25 refresh found PR #156 still targeting the open spelling-policy
PR #155, rather than `main`. The fetched target remains the direct parent of
this branch, so the rebase made no changes and encountered no conflicts. `main`
has since adopted `docs/adrs/adr-nnnn-title-slug.md` and
`docs/rfcs/rfc-nnnn-title-slug.md`; the spelling-policy target has not. The
style guide itself remains `docs/documentation-style-guide.md` on both.

At EP-M1 the target's style guide still documents the older
`docs/adr-NNN-short-description.md` convention, so the branch now contains both
`docs/adr-001...`, `docs/adr-002...` and the new `docs/adrs/adr-0003...`
record. Inbound links to ADR 002 use
`../adr-002-cargo-workspace-and-crate-boundaries.md`, which resolves at this
target; the documentation migration will re-point them. `mdtablefix` reflowed
the wide option and verification tables, which is expected formatting rather
than a content change. The eight-gate run spent most of its wall-clock queued
for compile admission but reported no faults.

`mapsplice` 0.1.0 could not make the EP-M2 roadmap edit. `replace` and `delete`
failed with `dangling_dependency` even on a minimal three-task roadmap, and
`insert` reflowed nested bullets and rewrote a `Requires 1.1.1 and 1.1.2`
reference to the shifted number. The roadmap tick was therefore made as a
one-character direct edit, verified by `git diff` to change only the 1.1.2
checkbox. This is a tool defect to report, not a roadmap-content change.

## Decision log

- 2026-10-20: recommend explicit non-strict support in v1 while retaining the
  strict default. This preserves the proposed two-policy vocabulary and permits
  staged adoption: known-failing tests keep executing while recovered cases
  remain green during marker cleanup. The cost is weaker stale-marker detection
  and a v1 policy commitment. Strict-only v1 is a credible alternative,
  recommended by one reconnaissance reviewer: it gives stronger CI feedback, a
  smaller contract, and the option to add opt-out later. Neither alternative is
  mandated by the terms of reference. Approval settles the choice.
- 2026-10-20: keep 1.1.2 documentation-only. Record semantic obligations before
  implementation, without speculative Rust or Verus scaffolding.
- 2026-10-20: follow the repository's `docs/adr-NNN-...md` naming and required
  headings. The `arch-decision-records` skill's Y-statement can summarize the
  decision inside that structure; repository conventions take precedence.
- 2026-11-04: restore the reviewed policy and proof boundaries, including raw
  observation versus policy normalization, separate macro/default test
  ownership, phase-specific logs, and a configurable ADR audit path.

- 2026-11-25: preserve PR #156's actual target rather than silently retargeting
  the stack to `main`. Use the revised four-digit ADR convention for the new
  record, as requested, superseding the 2026-10-20 naming decision. Resolve
  existing ADR references through the contents index when the prerequisite
  branch incorporates the documentation migration. Do not migrate existing
  records as part of this policy task.
- 2026-11-25: plan approved and implementation authorized. The agreed v1
  decision is an explicit `strict = false` opt-out with strict XPASS by
  default. EP-M1 and EP-M2 may now proceed as written; no tolerance deviation
  is requested.
- 2026-11-25: EP-M1 accepts ADR 0003 at
  `docs/adrs/adr-0003-strict-xpass-default-and-non-strict-policy.md` and
  synchronizes the design, terms of reference, user guide, developer guide, and
  contents index. The terms-of-reference §9 strictness question is resolved in
  place; the other open questions are preserved. The change remains
  documentation-only, so no compatibility layer, migration, or public-interface
  change applies.
- 2026-11-25: EP-M2 records the `mapsplice` 0.1.0 failure and applies the
  equivalent minimal checkbox edit directly. Only roadmap 1.1.2 is checked;
  1.1.3, later tasks, and every `Requires` reference are unchanged. No
  tolerance trigger applies: scope, policy, and public interfaces are
  unaffected.

## Outcomes & retrospective

The plan delivered a bounded documentation decision and its acceptance
evidence. Approval was granted on 2026-11-25. No ADR had been accepted and no
feature implemented at approval time. Expert review found no blocking design
defect; its precision and delivery findings were incorporated. The delivered
outcome is a settled policy, not working macros; classifier and adapter
execution remain later roadmap work.

EP-M1 delivered on 2026-11-25. Evidence:

- E1: `docs/adrs/adr-0003-strict-xpass-default-and-non-strict-policy.md`
  records Status "Accepted, 2026-11-25", adopts Option B, and states that
  `strict = false` ships in version 1 while strict XPASS stays the default. Its
  options table rejects the non-strict default, and "Consequence for CI users"
  names the stale-marker and green-suite risk.
- E2: Table 2 in the ADR, design §§6-7 and 11-14, the users' guide section
  "Expected-failure policy (planned version 1)", and the developer guide
  section "Expected-failure classification and harness mapping" agree on all
  eight table cells. The witnesses (successful return, permitted panic,
  wrong-mode `Err`, missing substring) and the unrelated-failure case are
  recorded in the ADR's "Policy invariants".
- E3: the diff is documentation only: no Rust, manifest, lockfile, build
  configuration, or dependency file changed. The ADR and developer guide
  document the core-classification and adapter-mapping boundary.
- E4: roadmap 1.1.2 is checked, 1.1.3 and later tasks are untouched, every
  `Requires` reference still resolves, and the full eight-gate sequence passed
  again. Relative links in the ADR and the synchronized documents resolve.

Gate evidence for EP-M1: `make check-fmt`, `make typecheck`, `make lint`,
`make test`, `make markdownlint` (which runs spelling), `make nixie`,
`make test-workflow-contracts`, and `git diff --check` all exited zero. Logs
and immediate statuses are retained as
`/tmp/<gate>-rstest-xfail-1-1-2-epm1.out` and `.status`. `make test` ran 24
tests and the doctest suites; Markdown lint reported 0 issues in 23 files;
spelling did not regenerate `typos.toml`; `nixie` validated every diagram; and
the workflow contracts passed 91 pytest cases plus the CV-005 check.

CodeRabbit CLI 0.9.7 reviewed commit `2add935` against `fba3fca` and raised two
minor findings, both accepted. The user guide now says a non-strict XPASS can
leave CI green when no other test fails, and the ADR's strict-only migration
cost now names XPASS markers rather than every known failure, including the
matching Table 1 row. The repair re-ran the affected Markdown gates; it did not
touch Rust, so the compile and test gates remain valid for the unchanged
sources.

A second CLI pass over `fba3fca..57a9c8a` repeated neither finding and raised
two consistency points, both accepted. Design §6 now distinguishes the
user-facing default from an adapter's deliberate programmatic choice, so the
`XfailPolicy` sketch no longer contradicts the marker-only route to
`Strictness::NonStrict`. The ADR context now frames the terms-of-reference and
design positions in the past tense, at the time of drafting, so an accepted
record does not read as an open question. A third pass repeated none of those
and raised one related point for the developer guide, which now scopes the
marker-only rule to the macro surface. It also raised the unspecified
`#[should_panic]` combination; design §7 now rejects that combination at
compile time and §12 carries the matching `trybuild` row. This is a
clarification of the existing unsupported-construct rule, required by failure
preservation (P3), not a change to the v1 strictness decision. A fourth pass
reported zero findings over the exact repaired content, and no policy content
changed.

EP-M2 re-ran the full eight-gate sequence on the final documentation set after
the roadmap tick: `make check-fmt`, `make typecheck`, `make lint`, `make test`,
`make markdownlint` (with spelling), `make nixie`,
`make test-workflow-contracts`, and `git diff --check` all exited zero.
`make test` again ran 24 tests and the doctest suites; the workflow contracts
passed 91 pytest cases plus the CV-005 check; spelling did not regenerate
`typos.toml`; and no gate changed a tracked file. The EP-M2 review raised one
minor developer-guide finding, accepted: the classification section now labels
its contract as planned, because the crate roots remain placeholders.
Publication and hosted CI/review state are recorded by PR delivery, not by this
local plan.

The hosted ExecPlan assessment (Assessment-ID `xpass-1.1.2-4367f96-20261125-1`)
returned "mostly complete" with two in-scope documentation gaps, both accepted.
Design §4 now separates the classification inputs from the strictness that maps
a classification to a harness result, and the adapter data-flow list in §5.1
now includes the non-strict XPASS case. Neither change alters policy.

## Context and orientation

`docs/contents.md` indexes the project. `docs/repository-layout.md` describes
three crates: `rstest-xfail-core` owns classification, `rstest-xfail-macros`
will parse attributes, and `rstest-xfail` exposes the facade. Their
`crates/*/src/lib.rs` files are scaffolding from task 1.1.1. No classifier
implementation is available for this task to test or prove.

`docs/terms-of-reference.md` §§6–9 establishes strict defaults and asks whether
non-strict ships. `docs/xfail-design.md` §§6–7 proposes policy vocabulary and
syntax, §11 describes reporting, §12 verification, and §14 leaves the release
choice open. `docs/adr-002-cargo-workspace-and-crate-boundaries.md` establishes
ownership and explicitly defers strictness to this task.

## Conformance basis

The current PR target, fetched on 2026-11-25, is
`origin/refresh-spelling-policy-20261104` at
`0a423825c79490e3d0c568c3160e70b26f9917dc`. This is also the exclusive replay
boundary: the sole child commit before this refresh was
`30c8ad71cb0dc92296d87f676dd168e978c35c6c`, containing only this plan and its
index entry. Recovery refs under `refs/recovery/20261125-xpass/` retain
`old-head`, `old-base`, and `target`. The explicit rebase onto this target
reported that the branch was already up to date. No lockfile was changed.

The original inspected baseline was `09f41344ffde8d5bb870215bb95f051a6e2323a0`;
the target adds only the generated spelling-policy prerequisite. The design
remains Draft v0.1, last substantive revision 2026-06-07. Previous gate results
remain historical; validate the updated plan afresh before committing it.

For the requested naming refresh, the separately fetched `origin/main` at
`1ff6d06524e5b9bc3cea7e7cf73fa88efe82d4e8` supplies the revised style-guide
conventions. Its ADR 002 is
`docs/adrs/adr-0002-cargo-workspace-and-crate-boundaries.md`; the PR target
still has `docs/adr-002-cargo-workspace-and-crate-boundaries.md`. Resolve the
existing record through `docs/contents.md` at implementation time and use
`docs/adrs/adr-0003-strict-xpass-default-and-non-strict-policy.md` for the
proposed new record, subject to number availability. This observation does not
claim that `main` was integrated or change the PR's target.

- C1: roadmap 1.1.2 and terms-of-reference §9 require a v1 yes/no decision and
  CI consequence. EP-M1 discharges this with accepted ADR text (evidence E1).
- C2: terms-of-reference §§6–8 and design §§7, 11 require strict default and
  stock harness semantics. EP-M1 discharges this with the outcome table and
  consistent user/design guidance (E2).
- C3: design §§5–6 and ADR 002 require shared core classification and adapter
  ownership. EP-M1 documents that boundary without changing code (E3).
- C4: documentation style and roadmap completion rules require consistent
  links, status, and validation. EP-M2 discharges this with gates and the
  checked roadmap entry (E4).

No proof standard or Verus target exists at this baseline. Do not invent one
for a prose decision. Recheck conformance and record any proposed deviation at
each milestone before continuing.

At EP-M1 (2026-11-25): C1 is satisfied by the Accepted status and decision in
ADR 0003; C2 by the outcome table agreed across the ADR, design, user guide,
and developer guide; C3 by the unchanged source tree and the documented
core/adapter boundary.

At EP-M2 (2026-11-25): C4 is satisfied by the checked roadmap entry, the
completed gate sequence, and resolving links. C1-C3 remain satisfied with no
change to source or dependencies. All four criteria are discharged.

## Verification plan

### Abstract policy specification

Use this implementation-independent model before editing the policy documents.
Let O be a raw observed body outcome and P the failure-mode/message policy.
Normalize N(P, O) to pass, permitted failure, or mismatched failure. A
permitted failure satisfies both the configured failure kind and any message
condition. Let S be strict or non-strict. Preconditions are a valid policy, a
body that executes and terminates, and an observable return or unwinding panic.
Aborts, process exits, and timeouts are outside this model. Reason text is
explanatory metadata, not a classification input.

Classification C(P, O), defined through N(P, O), is XPASS for pass, XFAIL for
permitted failure, and UnexpectedFailure for mismatched failure. Classification
is independent of S. Harness failure H(S, C) is true for UnexpectedFailure or
strict XPASS; otherwise it is false. These are proposed specifications, not
claims that current code implements or has proved them.

| Body observation         | Classification    | Strict harness result | Non-strict harness result |
| ------------------------ | ----------------- | --------------------- | ------------------------- |
| Pass (`()` or `Ok`)      | XPASS             | Fail                  | Pass                      |
| Permitted panic or `Err` | XFAIL             | Pass                  | Pass                      |
| Wrong failure mode       | UnexpectedFailure | Fail                  | Fail                      |
| Message mismatch         | UnexpectedFailure | Fail                  | Fail                      |

The later representation relationship maps concrete `BodyOutcome` values to O,
mode/message predicates to N(P, O), and `Strictness` to S. `XfailOutcome`
retains classification independently of adapter exit behaviour. Downstream BDD
can therefore still report XPASS when a non-strict adapter succeeds.

### Obligations and proof sketch

P1 (default equivalence): omitted strictness and explicit true have identical
classification and harness outcomes. Expand the default to strict and compare
the same P and O; do not assume the desired equality as a premise.

P2 (limited relaxation): changing strict to non-strict changes the harness
result only when C is XPASS. Split on the three classifications; XFAIL and
UnexpectedFailure must retain their results.

P3 (failure preservation): no mode or message mismatch becomes success under
either policy. Normalize a mismatched failure, then derive H from the
UnexpectedFailure branch independently of S.

These are candidate semantic lemmas for later executable work, not compiled
theorems introduced in 1.1.2. Review the table's eight cells and default
equivalence against every affected document. E2 records that review, including
witnesses: a successful unit return, permitted panic, wrong-mode `Err`, and a
failure message missing the required substring. The latter two reject the
incorrect claim that non-strict accepts mismatches. A suite with another
failing test rejects the claim that non-strict XPASS guarantees green CI.

For E1, inspect the ADR for an unambiguous v1 yes/no and CI trade-off. For E3,
inspect the diff for unchanged code and clear ownership. For E4, run the gates
below and check links and roadmap status. An omitted decision, contradictory
cell, broken link, or source change fails these checks. They establish prose
consistency, not runtime correctness; the witnesses make that review concrete.

External assumptions are documented Rust harness treatment of normal returns
and panics, and observation of recoverable outcomes. The model does not prove
panic recovery, output visibility, macro expansion, or CI configuration. pytest
is comparative prior art, not authority for this project's default.

### Proportionate testing and formal verification

No Verus milestone is warranted for this documentation-only task: no executable
kernel, representation, or unbounded invariant is introduced. Do not add
`assume`, `admit`, trusted bodies, or empty proof harnesses. If later work
selects P1–P3 for formal verification, its approved plan must specify
substantive Verus proofs from the classification definitions, satisfiable
premises, representation correspondence, and an explicit verification command.
Solver plumbing and auxiliary lemmas should follow actual verification
conditions. Formal results must never substitute for executable integration and
externally visible tests.

Later 1.2.x classifier work should use `rstest` tables with `googletest`
assertions and `pretty_assertions` for structured comparisons. Cover Strict and
NonStrict with passing, allowed-failure, wrong-mode, and message-mismatch
observations. Core policy-construction tests check defaults where exposed;
later macro tests check omitted strictness versus explicit true and false. Do
not invent an optional core state merely to represent attribute syntax. Use
`proptest` for broad message/policy relations if introduced; use Kani only for
a justified bounded exhaustive obligation.

Later macro work needs compile tests and end-to-end child test processes to
check exit status for strict XPASS, non-strict XPASS, and mismatches. Use
`rstest-bdd` when a downstream scenario adapter exists, preserving its
ownership boundary. Use focused `insta` snapshots only when diagnostic output
variants exist. No BDD feature file, snapshots, property harness, dependency,
or runtime regression test belongs in this prose change. Red-Green-Refactor is
unavailable for prose: the observable substitute is the unresolved policy
question before EP-M1 and a cross-reviewed, consistent decision afterwards.

## Plan of work and milestones

### EP-M1: ratify and synchronize the policy

After approval, verify the branch and clean worktree, then read the references
below. Check ADR numbering and create
`docs/adrs/adr-0003-strict-xpass-default-and-non-strict-policy.md` if 0003 is
free. Follow the style guide's Status, Date, and Context and Problem Statement
headings; add drivers, alternatives, decision, and consequences. Record the
approval date and Accepted status only after approval. Compare strict-only v1,
explicit opt-out v1, and non-strict default (rejected by C2).

State that `strict = false` ships in v1, is local and opt-in, executes the
body, retains XPASS classification, and relaxes only its harness failure. Do
not add global or environment overrides. Explain missed fixed bugs and stale
markers in opted-out tests; unrelated failures still fail the suite. Do not
promise successful-test diagnostics are always visible.

Synchronize `docs/xfail-design.md` §§6–7, 11–14 with the ADR and approved
policy, updating its substantive revision date. Resolve the corresponding §9
question in `docs/terms-of-reference.md` with a decision and link, preserving
other open questions. Add planned-v1 guidance and the CI warning to
`docs/users-guide.md`, retaining the placeholder caveat. In
`docs/developers-guide.md`, describe core classification versus adapter harness
mapping and downstream BDD reuse; no new helper is authorized. Index the ADR in
`docs/contents.md` and update this plan.

Acceptance E1–E3 requires the explicit decision, agreement on all outcome
cells, working relative links, no conflicting unresolved strictness question,
and unchanged source/dependencies. Run the full gate sequence before committing
this coherent documentation change. Confirm C1–C3, unchanged public interfaces,
trust boundaries and persisted formats, and current trace links. Leave the
roadmap checkbox for EP-M2. Repair documents and rerun affected gates on
failure. No compatibility layer or data migration is required.

### EP-M2: reconcile and record completion

Review the full diff and each upstream requirement. Record actual gate results,
review conclusions, and accepted deviations in this plan. Use the `mapsplice`
skill to mark only 1.1.2 `[x]` (done) in `docs/roadmap.md` once E1–E3 are
satisfied. Preserve later dependencies. Run all gates again for this milestone
and commit the completion record.

Acceptance E4 is the completed entry backed by the accepted ADR, synchronized
upstream documents, and successful gates. Confirm C1–C4 and all trace links;
reconcile any changed assumption with the terms of reference and design. Only
then mark this plan COMPLETE. The delivered outcome is a settled policy, not
working macros. Classifier and adapter execution remain later roadmap work. On
a failed check, leave the milestone incomplete and repair before committing.

## Concrete steps and acceptance commands

Run from the repository root. Establish a baseline before implementation and
record pre-existing failures honestly. After every major milestone, delegate
checks to `scrutineer`; formatting may be run by the implementing agent first.
Use the clean command environment specified in `AGENTS.md` for Git-backed
tools. Never bypass compiler admission or create an isolated Cargo cache.

Execute these lines separately, in order, stopping on failure. Choose a fresh
phase/attempt name every time. Record each pipeline's exit status immediately
in a matching status file as well as retaining its log.

```bash
git branch --show-current
git status --short
set -o pipefail
phase=baseline-attempt1
make fmt 2>&1 | tee /tmp/fmt-rstest-xfail-1-1-2-${phase}.out
make check-fmt 2>&1 | tee /tmp/check-fmt-rstest-xfail-1-1-2-${phase}.out
make typecheck 2>&1 | tee /tmp/typecheck-rstest-xfail-1-1-2-${phase}.out
make lint 2>&1 | tee /tmp/lint-rstest-xfail-1-1-2-${phase}.out
make test 2>&1 | tee /tmp/test-rstest-xfail-1-1-2-${phase}.out
make markdownlint 2>&1 | tee /tmp/markdownlint-rstest-xfail-1-1-2-${phase}.out
make nixie 2>&1 | tee /tmp/nixie-rstest-xfail-1-1-2-${phase}.out
git diff --check
```

For each gate above, use this capture pattern in place of the bare pipeline,
changing the target and filenames together. Do not rerun a successful gate
merely to demonstrate the example. Stop on a nonzero status before the next
gate; retain the failed log and status for diagnosis.

```bash
set -o pipefail
make lint 2>&1 | tee "/tmp/lint-rstest-xfail-1-1-2-${phase}.out"
gate_status=$?
printf '%s\n' "$gate_status" > "/tmp/lint-rstest-xfail-1-1-2-${phase}.status"
test "$gate_status" -eq 0
```

Expect exit zero, unchanged formatting, no lint findings, passing workspace
tests/doctests, clean Markdown/spelling, and valid diagrams. Inspect formatter
changes and preserve unrelated work. Never hand-edit generated `typos.toml`;
unrelated regeneration requires the repository's separate base PR workflow. A
missing outer-shell status is not evidence of success: retain status files so a
long-lived execution session cannot discard the result.

The PR target's `make typecheck` runs `cargo check` with all targets and
features, denying warnings. Include it in each milestone's sequential gates;
Clippy remains an additional lint check, not a substitute for this target.

For the document audit, substitute the actual ADR filename below and read every
matching passage; search output alone does not establish agreement or links.

```bash
adr_path=docs/adrs/adr-0003-strict-xpass-default-and-non-strict-policy.md
rg -n 'strict|XPASS|NonStrict' docs/terms-of-reference.md docs/xfail-design.md \
  docs/users-guide.md docs/developers-guide.md "$adr_path"
rg -n '1\.1\.2' docs/roadmap.md
git diff --stat
git diff --check
```

Resolve each new relative link to an existing document. Record E1–E4 with
relevant passages and actual command results. Inspect and commit the exact diff
with the `commit-message` skill after gates pass.

## Idempotence and recovery

Rereading documents and rerunning gates is safe. Resume the selected ADR rather
than creating a duplicate on retry. Preserve other agents' changes. If rollback
is required, use an ordinary reviewed revert of this task's commits; never
reset shared history. Preserve failed logs and report environment blockers
accurately. Do not repeat a healthy queued build. Correct a failed gate before
rerunning it.

## Interfaces and dependencies

No public signature, concrete enum, dependency, shared abstraction, or utility
library changes in this task. `Strictness`, `BodyOutcome`, and `XfailOutcome`
remain design vocabulary. Document their future responsibilities in the design
and developer guide; test them when the respective implementations land.

## References and skills

Start with [documentation contents](../contents.md). Follow the
[documentation style guide](../documentation-style-guide.md), then consult the
[technical design](../xfail-design.md) and
[developer guide](../developers-guide.md).

The
[dependency-injection guide](../reliable-testing-in-rust-via-dependency-injection.md)
keeps future tests independent of global state. The
[doctest guide](../rust-doctest-dry-guide.md) governs executable examples. The
[complexity guide](../complexity-antipatterns-and-refactoring-strategies.md)
helps separate classification from adapter responsibilities.

Use `execplans` to maintain this document, `codegraph-mcp` for relationships,
`rust-router` for Rust guidance, `arch-decision-records` for rationale,
`rust-verification` for proportionate evidence, and `logisphere-experts` for
review. Use `firecrawl-mcp` for remote research, `mapsplice` for roadmap edits,
`commit-message` for commits, and `pr-creation` for draft publication.

Primary sources checked through Firecrawl on 2026-10-20:

- [pytest xfail documentation](https://docs.pytest.org/en/stable/how-to/skipping.html#strict-parameter):
  strict XPASS fails the suite; non-strict XPASS does not itself fail it.
- [Rust testing reference](https://doc.rust-lang.org/reference/attributes/testing.html):
  ordinary unit returns pass; panics and unsuccessful termination fail ordinary
  tests. This plan promises no native XFAIL summary category.

## Revision notes

2026-10-20: draft and expert review separated policy ratification from
executable classification, clarified the abstract model and test ownership,
documented adoption trade-offs, and preserved logs and ADR paths across retries.

2026-11-04: restored the reviewed draft after workspace resumption, refreshed
repository evidence, and explicitly required durable gate status records.
Implementation scope and the approval gate remain unchanged.

2026-11-04: recorded fresh lint and test evidence for the restored plan; 24
tests and all doctest suites passed. Final prose checks precede publication.

2026-11-25: refreshed the exact PR target and recovery evidence, recorded the
conflict-free no-op rebase, and reconciled the proposed ADR path with the newer
style-guide convention on `main` while retaining valid target references. Added
the existing typecheck target to milestone gates. Policy scope, proof strategy,
and the explicit implementation-approval boundary remain unchanged.

2026-11-25: fresh `make test`, `make typecheck`, and `make lint` passed. The
test target ran 24 tests and three empty doctest suites. Logs and immediate
exit statuses are retained as `/tmp/xpass-rebase-20261125-<target>.out` and
`.status`. Final formatting, Markdown/spelling, and diagram checks gate the
plan-refresh commit. No runtime changes or implementation approval followed
from this validation.

2026-11-25: approval granted and EP-M1 delivered. ADR 0003 is accepted at
`docs/adrs/adr-0003-strict-xpass-default-and-non-strict-policy.md`; the design,
terms of reference, user guide, developer guide, and contents index are
synchronized; and all eight EP-M1 gates passed. Decision scope, the strict
default, and the explicit non-strict opt-out are unchanged from the approved
plan.

2026-11-25: EP-M2 delivered. Roadmap 1.1.2 is checked, the full eight-gate
sequence passed again on the final documentation set, and this plan is
COMPLETE. Recorded the `mapsplice` 0.1.0 failure and the equivalent minimal
checkbox edit, which changed no other roadmap content.
