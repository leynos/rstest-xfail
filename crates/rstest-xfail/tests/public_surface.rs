//! Documents the facade's public surface for roadmap task 1.1.1.
//!
//! It asserts reachability — the intended public item resolves through the
//! `rstest_xfail` facade path — and records the intended surface as a
//! reviewer-facing `insta` snapshot. The snapshot is a hand-maintained record
//! of intent, not an automated completeness guarantee: it cannot detect an
//! unintended re-export that is also added to the constant. A rigorous surface
//! and `SemVer` lock is deferred to the publishing-boundary roadmap item. There
//! is no classifier behaviour at this stage (roadmap 1.2.x); this test
//! validates structure only.

use rstest_xfail::xfail;

/// The facade's intended public surface, one path per line, sorted. Update this
/// list and review the snapshot only when the public contract intentionally
/// changes.
const INTENDED_PUBLIC_SURFACE: &str = "rstest_xfail::xfail";

#[test]
fn facade_public_surface_is_documented() {
    insta::assert_snapshot!("facade_public_surface", INTENDED_PUBLIC_SURFACE);
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
