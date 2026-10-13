//! Source-level derivation of the facade's public surface.
//!
//! The surface is *derived* from the facade's own source rather than restated,
//! so an unintended re-export fails a test instead of being mirrored into an
//! expectation. The derivation parses the source with `syn` and walks the item
//! list. A line scanner only sees the forms it was written to expect, so a
//! valid declaration it does not recognise — `pub` on one line and `fn` on the
//! next, say — would add an export while leaving the derived set unchanged.
//!
//! The walk is deliberately fail-closed: an item form that cannot be
//! attributed to exactly one name is reported rather than skipped, so the
//! derived surface cannot quietly shrink.
//!
//! The derivation reads source, not compiled metadata. A compiled-API oracle
//! (rustdoc JSON via `cargo-public-api`) is version-locked to the pinned
//! nightly unstable format and stays deferred, with the `SemVer` lock, to the
//! publishing-boundary roadmap item.
//!
//! `cargo` treats every top-level file in `tests/` as its own test binary, so
//! this shared code lives in a subdirectory. It is compiled into whichever
//! binaries declare it and is never part of the published crate.

use camino::Utf8Path;
use cap_std::{ambient_authority, fs::Dir};
use eyre::{Result, bail};
use syn::{
    Attribute,
    ImplItem,
    Item,
    ItemImpl,
    ItemMacro,
    ItemMod,
    ItemUse,
    Meta,
    MetaList,
    UseTree,
    Visibility,
    punctuated::Punctuated,
};

/// Reads the facade crate's source root.
///
/// The manifest directory is the facade crate's, so the path does not depend on
/// the test binary's working directory. The directory is opened as a `cap_std`
/// capability so the read names the surface it is allowed to touch, rather than
/// reaching for the ambient filesystem.
pub(crate) fn facade_source() -> Result<String> {
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
/// this derivation documents.
const fn is_public(visibility: &Visibility) -> bool { matches!(visibility, Visibility::Public(_)) }

/// The truth values a `cfg` predicate can still take once `test` is disabled.
///
/// `cfg` is evaluated during compilation, so deciding whether an item is
/// test-only means asking whether its predicate can still hold with `test`
/// off. Atoms other than `test` are settled by the target and the build flags,
/// which a source oracle cannot see, so they count as either outcome rather
/// than being guessed: guessing "this item is excluded" is how an oracle
/// silently stops watching an export.
#[derive(Clone, Copy)]
struct Outcomes {
    /// The predicate can hold with `test` disabled.
    can_hold: bool,
    /// The predicate can fail with `test` disabled.
    can_fail: bool,
}

impl Outcomes {
    /// An atom this oracle cannot resolve, such as `unix` or `target_os`.
    const UNCERTAIN: Self = Self {
        can_hold: true,
        can_fail: true,
    };

    /// A predicate that is false whenever `test` is disabled.
    const NEVER_HOLDS: Self = Self {
        can_hold: false,
        can_fail: true,
    };
}

/// Swaps a predicate's two outcomes, which is what `not` does.
const fn negate(inner: Outcomes) -> Outcomes {
    Outcomes {
        can_hold: inner.can_fail,
        can_fail: inner.can_hold,
    }
}

/// Reports the truth values `predicate` can take once `test` is disabled.
fn outcomes_without_test(predicate: &Meta) -> Outcomes {
    match predicate {
        Meta::Path(path) if path.is_ident("test") => Outcomes::NEVER_HOLDS,
        Meta::Path(_) | Meta::NameValue(_) => Outcomes::UNCERTAIN,
        Meta::List(list) => combine(list),
    }
}

/// Reports the truth values a `cfg` combinator's operands imply.
///
/// `all` holds only if every operand can hold, and fails if any operand can
/// fail; `any` is the mirror image; `not` swaps the two. Operands are treated
/// as independent, which over-approximates what a shared atom can do. That is
/// the safe direction here: the derivation then keeps an export it is unsure
/// about rather than dropping it from the watched surface.
///
/// A combinator this oracle does not know — `version(..)`, say — and one whose
/// operands do not parse both report [`Outcomes::UNCERTAIN`].
fn combine(list: &MetaList) -> Outcomes {
    let Ok(operands) = list.parse_args_with(Punctuated::<Meta, syn::Token![,]>::parse_terminated)
    else {
        return Outcomes::UNCERTAIN;
    };
    let parts: Vec<Outcomes> = operands.iter().map(outcomes_without_test).collect();
    match list.path.get_ident().map(ToString::to_string).as_deref() {
        Some("all") => Outcomes {
            can_hold: parts.iter().all(|part| part.can_hold),
            can_fail: parts.iter().any(|part| part.can_fail),
        },
        Some("any") => Outcomes {
            can_hold: parts.iter().any(|part| part.can_hold),
            can_fail: parts.iter().all(|part| part.can_fail),
        },
        Some("not") => parts.first().copied().map_or(Outcomes::UNCERTAIN, negate),
        _ => Outcomes::UNCERTAIN,
    }
}

/// Reports whether an item is compiled out of a normal library build.
///
/// An item is test-only when its predicate *cannot hold* with `test` disabled,
/// not merely when the predicate mentions `test`. Both `#[cfg(not(test))]` and
/// `#[cfg(any(test, unix))]` mention `test` and both exist in a normal build,
/// so an occurrence check would drop them and let the derived surface shrink
/// without the equality assertion noticing. A predicate that will not parse is
/// treated as satisfiable, for the same reason.
fn is_test_only(attrs: &[Attribute]) -> bool {
    attrs
        .iter()
        .filter(|attribute| attribute.path().is_ident("cfg"))
        .any(|attribute| {
            attribute
                .parse_args::<Meta>()
                .is_ok_and(|predicate| !outcomes_without_test(&predicate).can_hold)
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
/// ignoring it is exactly the shrink this derivation exists to prevent.
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
        // A `pub mod foo;` puts its items in a file this derivation does not
        // read, so recording only the module name would under-report.
        None if is_exposed => bail!(
            "`pub mod {};` keeps its items in another file this derivation does not read",
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
/// An inherent `pub fn` inside an `impl` is public surface, but this
/// derivation names items by their own identifier and cannot express a
/// `Type::method` path, so the form is reported instead of under-reporting. A
/// trait `impl` declares no visibility of its own and adds no name beyond the
/// type, so it is skipped.
fn check_impl_block(block: &ItemImpl) -> Result<()> {
    if exposes_public_member(block) {
        bail!("an `impl` block exposes a public associated item this derivation cannot name");
    }
    Ok(())
}

/// Rejects a macro form this derivation cannot attribute to names.
///
/// `syn` puts two forms under `Item::Macro`. A `macro_rules!` definition names
/// itself in `ident`, and adding `#[macro_export]` puts that name at the crate
/// root. An item-position invocation such as `reexports!();` has no `ident` at
/// all: its tokens are expanded by the compiler, so the expansion may add
/// public items this source-level walk never reads. Both are reported rather
/// than skipped, for the same reason as the other fail-closed arms here.
fn check_macro(declaration: &ItemMacro) -> Result<()> {
    let is_exported = declaration
        .attrs
        .iter()
        .any(|attribute| attribute.path().is_ident("macro_export"));
    if is_exported {
        bail!("a `#[macro_export]` macro adds a root name this derivation cannot enumerate");
    }
    if declaration.ident.is_none() {
        bail!(
            "an item-position macro invocation may expand to public items this derivation cannot \
             enumerate"
        );
    }
    Ok(())
}

/// Appends the name of a plain named item, if it is public.
///
/// The keyword set is closed on purpose: an unrecognised form is reported
/// rather than skipped, so the derivation cannot silently stop watching the
/// surface. Extend the match when the facade legitimately gains a new item
/// kind.
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
            "the facade uses an item form this derivation cannot classify; extend `collect_named` \
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
        // silent shrink this derivation exists to prevent.
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
/// here: the equality assertion in the contract test is what stops the surface
/// silently shrinking, and it needs to be the one that reports it.
pub(crate) fn exported_paths(source: &str) -> Result<Vec<String>> {
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
