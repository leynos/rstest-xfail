//! Documents the facade's public surface for roadmap task 1.1.1.
//!
//! The surface is *derived* from the facade's own source rather than restated,
//! so an unintended re-export fails here instead of being mirrored into the
//! expectation. Two assertions carry the contract: the derived set must equal
//! the intended set, and — as a reviewer-facing record — an `insta` snapshot
//! captures the derived names.
//!
//! The derivation parses the source with `syn` rather than scanning lines. A
//! line scanner only sees the forms it was written to expect, so a valid
//! declaration it does not recognise — `pub` on one line and `fn` on the next,
//! say — adds an export while leaving the derived set unchanged. Parsing to an
//! item list removes that class of evasion: an item form the walker cannot
//! attribute to exactly one name is reported as an error, so the derived
//! surface cannot quietly shrink.
//!
//! The derivation still reads source, not compiled metadata. A compiled-API
//! oracle (rustdoc JSON via `cargo-public-api`) is version-locked to the pinned
//! nightly unstable format and stays deferred, with the `SemVer` lock, to the
//! publishing-boundary roadmap item.
//!
//! There is no classifier behaviour at this stage (roadmap 1.2.x); this test
//! validates structure only.

use camino::Utf8Path;
use cap_std::{ambient_authority, fs::Dir};
use eyre::{Result, bail};
use rstest_xfail::xfail;
use syn::{
    Attribute,
    ImplItem,
    Item,
    ItemImpl,
    ItemMacro,
    ItemMod,
    ItemUse,
    Meta,
    UseTree,
    Visibility,
    punctuated::Punctuated,
};

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

/// Reports whether a visibility makes an item part of the public surface.
///
/// Only a bare `pub` counts. A restricted form such as `pub(crate)` or
/// `pub(super)` names a narrower audience, so it is not part of the surface
/// this test documents.
const fn is_public(visibility: &Visibility) -> bool { matches!(visibility, Visibility::Public(_)) }

/// Reports whether a `cfg` predicate mentions `test`.
///
/// `cfg` predicates nest (`all`, `any`, `not`), so this walks the parsed
/// predicate rather than pattern-matching on its text.
fn mentions_test(predicate: &Meta) -> bool {
    match predicate {
        Meta::Path(path) => path.is_ident("test"),
        Meta::List(list) => list
            .parse_args_with(Punctuated::<Meta, syn::Token![,]>::parse_terminated)
            .is_ok_and(|nested| nested.iter().any(mentions_test)),
        Meta::NameValue(_) => false,
    }
}

/// Reports whether an item is gated behind `#[cfg(test)]`.
///
/// A test-only item is compiled out of the published library, so it is not part
/// of the public surface. Without this, every `#[cfg(test)] pub fn` in the
/// facade would fail the equality assertion below.
fn is_test_only(attrs: &[Attribute]) -> bool {
    attrs
        .iter()
        .filter(|attribute| attribute.path().is_ident("cfg"))
        .any(|attribute| {
            attribute
                .parse_args::<Meta>()
                .is_ok_and(|predicate| mentions_test(&predicate))
        })
}

/// Appends the names one `use` declaration binds to `out`.
fn collect_use(use_item: &ItemUse, out: &mut Vec<String>) -> Result<()> {
    if is_public(&use_item.vis) && !is_test_only(&use_item.attrs) {
        bindings(&use_item.tree, out)?;
    }
    Ok(())
}

/// Appends every name a `use` tree binds.
///
/// A glob re-export hides the whole surface behind one token and is reported
/// rather than skipped: it cannot be attributed to a name, and silently
/// ignoring it is exactly the shrink this test exists to prevent.
fn bindings(tree: &UseTree, out: &mut Vec<String>) -> Result<()> {
    match tree {
        UseTree::Path(path) => bindings(&path.tree, out)?,
        UseTree::Name(name) => out.push(name.ident.to_string()),
        UseTree::Rename(rename) => out.push(rename.rename.to_string()),
        UseTree::Group(group) => {
            for nested in &group.items {
                bindings(nested, out)?;
            }
        }
        UseTree::Glob(_) => bail!("a glob re-export hides the public surface"),
    }
    Ok(())
}

/// Appends the public names a module contributes.
///
/// A public module is itself a public path, and its public items are reached
/// through it. Both are recorded; the nested names lose their module
/// qualification, which is harmless here because the surface is flat.
fn collect_module(module: &ItemMod, out: &mut Vec<String>) -> Result<()> {
    let is_exposed = is_public(&module.vis) && !is_test_only(&module.attrs);
    if is_exposed {
        out.push(module.ident.to_string());
    }
    match &module.content {
        Some((_, items)) => collect_items(items, out),
        // A `pub mod foo;` puts its items in a file this test does not read, so
        // recording only the module name would under-report the surface.
        None if is_exposed => bail!(
            "`pub mod {};` keeps its items in another file this test does not read",
            module.ident
        ),
        None => Ok(()),
    }
}

/// Reports whether an associated item is public and therefore part of the
/// surface.
///
/// Split from [`exposes_public_member`] because the lint policy caps a
/// condition at two branches; spelling each arm here keeps both functions
/// simple and readable.
const fn is_public_member(item: &ImplItem) -> bool {
    match item {
        ImplItem::Const(member) => is_public(&member.vis),
        ImplItem::Fn(member) => is_public(&member.vis),
        ImplItem::Type(member) => is_public(&member.vis),
        _ => false,
    }
}

/// Reports whether an `impl` block exposes any public associated item.
fn exposes_public_member(block: &ItemImpl) -> bool { block.items.iter().any(is_public_member) }

/// Rejects an `impl` block that exposes public associated items.
///
/// An inherent `pub fn` inside an `impl` is public surface, but this test names
/// items by their own identifier and cannot express a `Type::method` path, so
/// the form is reported instead of under-reporting. A trait `impl` declares no
/// visibility of its own and adds no name beyond the type, so it is skipped.
fn check_impl_block(block: &ItemImpl) -> Result<()> {
    if exposes_public_member(block) {
        bail!("an `impl` block exposes a public associated item this test cannot name");
    }
    Ok(())
}

/// Rejects a `macro_rules!` that exports a name at the crate root.
fn check_macro(declaration: &ItemMacro) -> Result<()> {
    let is_exported = declaration
        .attrs
        .iter()
        .any(|attribute| attribute.path().is_ident("macro_export"));
    if is_exported {
        bail!("a `#[macro_export]` macro adds a root name this test cannot enumerate");
    }
    Ok(())
}

/// Appends the name of a plain named item, if it is public.
///
/// The keyword set is closed on purpose: an unrecognised form is reported
/// rather than skipped, so this test cannot silently stop watching the surface.
/// Extend the match when the facade legitimately gains a new item kind.
fn collect_named(item: &Item, out: &mut Vec<String>) -> Result<()> {
    let (visibility, name, attrs) = match item {
        Item::Const(declared) => (&declared.vis, &declared.ident, declared.attrs.as_slice()),
        Item::Enum(declared) => (&declared.vis, &declared.ident, declared.attrs.as_slice()),
        Item::ExternCrate(declared) => (&declared.vis, &declared.ident, declared.attrs.as_slice()),
        Item::Fn(declared) => (
            &declared.vis,
            &declared.sig.ident,
            declared.attrs.as_slice(),
        ),
        Item::Static(declared) => (&declared.vis, &declared.ident, declared.attrs.as_slice()),
        Item::Struct(declared) => (&declared.vis, &declared.ident, declared.attrs.as_slice()),
        Item::Trait(declared) => (&declared.vis, &declared.ident, declared.attrs.as_slice()),
        Item::TraitAlias(declared) => (&declared.vis, &declared.ident, declared.attrs.as_slice()),
        Item::Type(declared) => (&declared.vis, &declared.ident, declared.attrs.as_slice()),
        Item::Union(declared) => (&declared.vis, &declared.ident, declared.attrs.as_slice()),
        _ => bail!(
            "the facade uses an item form this test cannot classify; extend `collect_named` \
             rather than letting the surface go unwatched"
        ),
    };
    if is_public(visibility) && !is_test_only(attrs) {
        out.push(name.to_string());
    }
    Ok(())
}

/// Appends the public names one item contributes to `out`.
fn collect_item(item: &Item, out: &mut Vec<String>) -> Result<()> {
    match item {
        Item::Use(use_item) => collect_use(use_item, out),
        Item::Mod(module) => collect_module(module, out),
        Item::Impl(block) => check_impl_block(block),
        Item::Macro(declaration) => check_macro(declaration),
        // `syn` could not interpret the tokens. Skipping them would be the
        // silent shrink this test exists to prevent.
        Item::Verbatim(_) => bail!("`syn` could not interpret an item in the facade source"),
        _ => collect_named(item, out),
    }
}

/// Appends the public names a whole file's items contribute to `out`.
fn collect_items(items: &[Item], out: &mut Vec<String>) -> Result<()> {
    for item in items {
        collect_item(item, out)?;
    }
    Ok(())
}

/// Extracts the public item names the facade exposes, as user-visible paths.
///
/// The names are sorted and de-duplicated. An empty result is not an error
/// here: the equality assertion against [`INTENDED_PUBLIC_SURFACE`] in
/// [`facade_public_surface_is_documented`] is what stops the surface silently
/// shrinking, and it needs to be the one that reports it.
fn exported_paths(source: &str) -> Result<Vec<String>> {
    let file = syn::parse_file(source).map_err(|error| eyre::eyre!("failed to parse: {error}"))?;
    let mut names: Vec<String> = Vec::new();
    collect_items(&file.items, &mut names)?;
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
