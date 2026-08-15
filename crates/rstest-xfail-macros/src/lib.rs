//! Procedural macro implementation for `rstest-xfail`.
//!
//! This crate currently provides a no-op placeholder `#[xfail]` attribute so
//! the workspace skeleton links and the facade can re-export the attribute. The
//! real argument parsing and function rewriting described in the design arrive
//! in a later task.

use proc_macro::TokenStream;

/// Placeholder `#[xfail]` attribute macro.
///
/// For now it returns the annotated item unchanged. It must never absorb or
/// alter the body: a passing body still passes and a failing body still fails.
/// The real implementation (roadmap 2.1.x) will parse `reason`, `strict`,
/// `mode`, and `contains`, then rewrite the function body to classify its
/// outcome.
#[proc_macro_attribute]
pub fn xfail(_args: TokenStream, item: TokenStream) -> TokenStream { item }
