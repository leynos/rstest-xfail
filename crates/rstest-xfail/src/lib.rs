//! Expected-failure macro attributes for `rstest`, async tests, and
//! `rstest-bdd`.
//!
//! This facade re-exports the public surface intended for ordinary users. At
//! the workspace-skeleton phase that surface is the single placeholder
//! `#[xfail]` attribute from `rstest-xfail-macros`. The stable types from
//! `rstest-xfail-core` are re-exported once they exist (roadmap 1.2.x).

pub use rstest_xfail_macros::xfail;
