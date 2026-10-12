//! Documents the facade's public surface for roadmap task 1.1.1.
//!
//! The surface is *derived* from the facade's own source rather than restated,
//! so an unintended re-export fails here instead of being mirrored into the
//! expectation. Two assertions carry the contract: the derived set must equal
//! the intended set, and — as a reviewer-facing record — an `insta` snapshot
//! captures the derived names.
//!
//! The derivation reads source, not compiled metadata. A compiled-API oracle
//! (rustdoc JSON via `cargo-public-api`) is version-locked to the pinned
//! nightly unstable format and is deferred, with the `SemVer` lock, to the
//! publishing-boundary roadmap item. A form this cannot attribute to exactly
//! one item is an error rather than a silent omission, so the derived surface
//! cannot quietly shrink and pass.
//!
//! There is no classifier behaviour at this stage (roadmap 1.2.x); this test
//! validates structure only.

use camino::Utf8Path;
use cap_std::{ambient_authority, fs::Dir};
use eyre::{Result, bail};
use rstest_xfail::xfail;

/// The facade's intended public surface, one path per line, sorted. Update this
/// list and review the snapshot only when the public contract intentionally
/// changes.
const INTENDED_PUBLIC_SURFACE: &str = "rstest_xfail::xfail";

/// Reads the facade crate's source root.
///
/// The manifest directory is the facade crate's, so the path does not depend on
/// the test binary's working directory. The directory is opened as a `cap_std`
/// capability so the read names the surface it is allowed to touch, rather than
/// reaching for the ambient filesystem.
fn facade_source() -> Result<String> {
    let root = Utf8Path::new(env!("CARGO_MANIFEST_DIR"));
    let dir = Dir::open_ambient_dir(root, ambient_authority())
        .map_err(|error| eyre::eyre!("failed to open {root}: {error}"))?;
    dir.read_to_string("src/lib.rs")
        .map_err(|error| eyre::eyre!("failed to read {root}/src/lib.rs: {error}"))
}

/// Reports whether a character may appear in an exported name.
///
/// Kept apart from [`is_identifier`] so that neither predicate has to nest one
/// connective inside another; `CodeScene` flags that nesting as a complexity
/// biomarker, and the split is clearer to read either way.
fn is_name_char(character: char) -> bool { character.is_alphanumeric() || character == '_' }

/// Reports whether `name` is a non-empty run of name characters.
fn is_identifier(name: &str) -> bool { !name.is_empty() && name.chars().all(is_name_char) }

/// Returns the name a `use` item binds, following an `as` rename.
fn leaf_name(item: &str) -> Result<String> {
    if item.contains(['{', '}']) {
        bail!("a nested brace list in `{item}` names more than one item");
    }
    let (path, alias) = match item.split_once(" as ") {
        Some((path, alias)) => (path.trim(), Some(alias.trim())),
        None => (item, None),
    };
    let name = alias.unwrap_or_else(|| path.rsplit("::").next().unwrap_or(path));
    if !is_identifier(name) {
        bail!("could not read an exported name from `{item}`");
    }
    Ok(name.to_owned())
}

/// Returns the names one `use` item re-exports.
fn re_exported_names(item: &str) -> Result<Vec<String>> {
    let declaration = item.trim().trim_end_matches(';').trim();
    if declaration.contains('*') {
        bail!("a glob re-export (`{declaration}`) hides the public surface");
    }
    let listed = match declaration.split_once('{') {
        Some((_, rest)) => rest
            .rsplit_once('}')
            .map(|(inner, _)| inner)
            .ok_or_else(|| eyre::eyre!("unterminated brace list in `{declaration}`"))?,
        None => declaration,
    };
    listed
        .split(',')
        .map(|leaf| leaf_name(leaf.trim()))
        .collect()
}

/// Returns the name a `pub` item declares.
///
/// The keyword set is closed on purpose: an unrecognised form is reported
/// rather than skipped, so this test cannot silently stop watching the surface.
fn declared_name(declaration: &str) -> Result<String> {
    let (keyword, rest) = declaration
        .split_once(char::is_whitespace)
        .ok_or_else(|| eyre::eyre!("unrecognised item `pub {declaration}`"))?;
    if !matches!(
        keyword,
        "fn" | "struct" | "enum" | "trait" | "const" | "static" | "type" | "mod" | "union"
    ) {
        bail!("`pub {keyword}` is not a form this test attributes to exactly one item");
    }
    let name = rest
        .split(|c: char| !is_name_char(c))
        .next()
        .unwrap_or_default();
    if name.is_empty() {
        bail!("could not read an item name from `pub {declaration}`");
    }
    Ok(name.to_owned())
}

/// Reports whether a trimmed line carries no exported name of its own.
///
/// Comments and attributes declare nothing, so they are skipped. This is a
/// named predicate rather than a compound condition because the lint policy
/// caps a condition at two branches.
fn carries_no_declaration(line: &str) -> bool { line.starts_with("//") || line.starts_with('#') }

/// Extracts the public item names the facade exposes, as user-visible paths.
fn exported_paths(source: &str) -> Result<Vec<String>> {
    let mut names: Vec<String> = Vec::new();
    for raw in source.lines() {
        let line = raw.trim();
        // A `pub(crate)` item is not part of the surface, so it matches neither
        // prefix below and is skipped.
        if line.is_empty() || carries_no_declaration(line) {
            continue;
        }
        if let Some(rest) = line.strip_prefix("pub use ") {
            names.extend(re_exported_names(rest)?);
        } else if let Some(rest) = line.strip_prefix("pub ") {
            names.push(declared_name(rest)?);
        }
    }
    if names.is_empty() {
        bail!("no public items found in the facade source");
    }
    names.sort();
    names.dedup();
    Ok(names
        .into_iter()
        .map(|name| format!("rstest_xfail::{name}"))
        .collect())
}

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
