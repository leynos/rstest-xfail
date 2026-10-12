//! Expected-failure macro attributes for `rstest`, async tests, and
//! `rstest-bdd`.
//!
//! This facade re-exports the public surface intended for ordinary users. At
//! the workspace-skeleton phase that surface is the single placeholder
//! `#[xfail]` attribute from `rstest-xfail-macros`. The stable types from the
//! core crate are re-exported once they exist (roadmap 1.2.x), at which point
//! the facade takes its dependency on `rstest-xfail-core`.

/// Marks a test as an expected failure.
///
/// This is the placeholder re-export of the procedural macro implemented by
/// `rstest-xfail-macros` and is the surface ordinary users import. It currently
/// returns the annotated item unchanged; the argument parsing, classification,
/// and reporting described in the design arrive with roadmap 2.1.x.
pub use rstest_xfail_macros::xfail;
