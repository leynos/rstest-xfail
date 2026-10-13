//! Pins the facade's public surface for roadmap task 1.1.1.
//!
//! Two assertions carry the contract: the derived set must equal the intended
//! set, and — as a reviewer-facing record — an `insta` snapshot captures the
//! derived names. The derivation itself lives in `support`, because a source
//! oracle is large enough to obscure the contract it protects when the two sit
//! in one file.
//!
//! There is no classifier behaviour at this stage (roadmap 1.2.x); this test
//! validates structure only.

mod support;

use eyre::Result;
use rstest_xfail::xfail;
use support::{exported_paths, facade_source};

/// The facade's intended public surface, one path per line, sorted. Update this
/// list and review the snapshot only when the public contract intentionally
/// changes.
const INTENDED_PUBLIC_SURFACE: &str = "rstest_xfail::xfail";

#[test]
fn facade_public_surface_is_documented() -> Result<()> {
    let derived = exported_paths(&facade_source()?)?.join("\n");
    pretty_assertions::assert_eq!(
        derived,
        INTENDED_PUBLIC_SURFACE,
        "the facade exposes a public item outside the intended surface"
    );
    insta::assert_snapshot!("facade_public_surface", derived);
    Ok(())
}

/// A `pub` separated from its item keyword by a newline is still one item.
///
/// A line scanner keyed on the literal prefixes `pub use ` and `pub ` sees no
/// declaration here at all, so this export would slip through unnoticed.
#[test]
fn a_split_visibility_is_still_detected() {
    let source = "pub\nfn unintended_export() {}\n";
    let derived = exported_paths(source).expect("a split `pub` must still parse");
    assert!(
        derived.contains(&"rstest_xfail::unintended_export".to_owned()),
        "a split `pub` hid an export; derived surface was {derived:?}"
    );
}

/// An ordinary added export is attributed to its name.
#[test]
fn an_added_export_is_attributed() {
    let derived = exported_paths("pub const EXPORTED: u8 = 1;\n").expect("a plain item must parse");
    assert_eq!(derived, vec!["rstest_xfail::EXPORTED".to_owned()]);
}

/// A renamed re-export is recorded under the name it binds, not its source.
#[test]
fn a_renamed_re_export_reports_the_bound_name() {
    let derived = exported_paths("pub use rstest_xfail_macros::xfail as expect_failure;\n")
        .expect("a renamed re-export must parse");
    assert_eq!(derived, vec!["rstest_xfail::expect_failure".to_owned()]);
}

/// A braced group binds every leaf, including a renamed one.
#[test]
fn a_braced_group_reports_each_leaf() {
    let derived = exported_paths("pub use rstest_xfail_macros::{alpha, beta as gamma};\n")
        .expect("a braced group must parse");
    assert_eq!(
        derived,
        vec![
            "rstest_xfail::alpha".to_owned(),
            "rstest_xfail::gamma".to_owned()
        ]
    );
}

/// A glob re-export cannot be attributed to a name, so it is an error.
#[test]
fn a_glob_re_export_is_rejected() {
    let source = "pub use rstest_xfail_macros::*;\n";
    let reported = exported_paths(source)
        .expect_err("a glob re-export must be rejected rather than skipped")
        .to_string();
    assert!(
        reported.contains("glob re-export"),
        "the error must name the offending form, got: {reported}"
    );
}

/// A test-only item is compiled out of the published library.
#[test]
fn a_test_only_export_is_not_surface() {
    let derived = exported_paths("#[cfg(test)]\npub fn test_helper() {}\n")
        .expect("a cfg-gated item must parse");
    assert!(
        derived.is_empty(),
        "a `#[cfg(test)]` item is not public surface, got {derived:?}"
    );
}

/// A predicate that requires `test` alongside another condition is test-only.
///
/// `all` holds only if every operand holds, so `all(test, unix)` can never hold
/// with `test` disabled: the item is absent from a normal build.
#[test]
fn a_conjunction_requiring_test_is_not_surface() {
    let derived = exported_paths("#[cfg(all(test, unix))]\npub fn test_helper() {}\n")
        .expect("a nested cfg predicate must parse");
    assert!(
        derived.is_empty(),
        "`all(test, unix)` cannot hold without `test`, got {derived:?}"
    );
}

/// A predicate that *negates* `test` is not test-only.
///
/// This is the defect an occurrence check produces: `not(test)` mentions
/// `test`, so a check that asks only whether the name appears would drop this
/// function from the surface even though it is compiled into every normal
/// library build. Its sibling below covers the `any` form.
#[test]
fn a_negated_test_predicate_is_surface() {
    let derived = exported_paths("#[cfg(not(test))]\npub fn unintended_export() {}\n")
        .expect("a negated cfg predicate must parse");
    assert_eq!(
        derived,
        vec!["rstest_xfail::unintended_export".to_owned()],
        "`not(test)` holds in a normal build, so this export is surface"
    );
}

/// An alternative that merely *mentions* `test` is not test-only.
///
/// `any` holds if at least one operand holds, and `unix` can hold on its own,
/// so this function exists in a normal Unix build. Treating the mention of
/// `test` as sufficient would hide it.
#[test]
fn a_disjunction_that_does_not_require_test_is_surface() {
    let derived = exported_paths("#[cfg(any(test, unix))]\npub fn another_export() {}\n")
        .expect("a disjunctive cfg predicate must parse");
    assert_eq!(
        derived,
        vec!["rstest_xfail::another_export".to_owned()],
        "`any(test, unix)` can hold without `test`, so this export is surface"
    );
}

/// A restricted visibility is not the public surface.
#[test]
fn a_restricted_visibility_is_not_surface() {
    let derived = exported_paths("pub(crate) fn internal_helper() {}\n")
        .expect("a restricted item must parse");
    assert!(
        derived.is_empty(),
        "a `pub(crate)` item is not public surface, got {derived:?}"
    );
}

/// An item form the walker cannot classify is reported, not skipped.
///
/// `Item::Verbatim` is `syn`'s escape hatch for tokens it will not interpret —
/// a `macro` 2.0 declaration lands there. Treat it as an error so a future
/// syntax change cannot silently shrink the derived surface.
#[test]
fn an_unimplemented_syntax_item_is_reported() {
    let source = "pub macro exported_like { () => {} }\n";
    let reported = exported_paths(source)
        .expect_err("an item `syn` cannot interpret must be reported, not skipped")
        .to_string();
    assert!(
        reported.contains("could not interpret"),
        "the error must say the item was uninterpretable, got: {reported}"
    );
}

// Applying the placeholder attribute proves it is reachable through the facade
// and, critically, that the no-op passes the body through unchanged rather than
// absorbing it. The design forbids a rewritten body from ever masking its real
// outcome; 2.1.x replaces this no-op before any classification logic exists.
// `const` keeps `clippy::missing_const_for_fn` satisfied: the placeholder
// passes the body through unchanged, so a `const` body is a faithful probe.
#[xfail]
const fn annotated_body_runs() -> i32 { 2 + 2 }

#[test]
fn placeholder_macro_passes_body_through() {
    use pretty_assertions::assert_eq;

    assert_eq!(annotated_body_runs(), 4);
}
