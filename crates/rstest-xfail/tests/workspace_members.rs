//! End-to-end checks over `cargo metadata` for roadmap task 1.1.1: the
//! workspace exposes exactly the three intended members, the core crate is a
//! pure leaf (constraint D1), and the intra-workspace dependency graph matches
//! the intended boundaries. These shell out to `cargo metadata`, so they are
//! serialized to bound package-cache lock contention.
//!
//! They use `file_serial` rather than `serial`. The gate runs `cargo nextest`,
//! which gives every test its own process, so an in-process lock serializes
//! nothing across them; `file_serial` takes an advisory file lock instead and
//! still holds under a plain `cargo test` single-process run.
//!
//! The failure diagnostics use `eyre` context so a failure names the stage that
//! failed — spawning `cargo metadata`, parsing its JSON, or locating a package
//! — rather than surfacing a bare `serde_json` or I/O error.

use std::{collections::BTreeSet, process::Command};

use eyre::{Context, ContextCompat, eyre};
use googletest::prelude::{GoogleTestSupport, assert_that, contains, empty, eq};
use rstest::rstest;
use serial_test::file_serial;

/// The single member allowed to hold a dependency edge to a sibling crate.
const FACADE: &str = "rstest-xfail";

/// A dependency edge expected in the workspace graph, as `(dependent, dependency)`.
type DependencyEdge = (&'static str, &'static str);

/// The dependency edges the workspace graph is intended to have.
///
/// The facade has no edge to `rstest-xfail-core` while the core exposes no
/// public items: the dependency would be one no target could use, which Cargo
/// reports as an unused dependency. The edge arrives with the core vocabulary
/// (roadmap 1.2.x), and this table is where it gets declared.
const INTENDED_EDGES: [DependencyEdge; 1] = [(FACADE, "rstest-xfail-macros")];

/// Runs `cargo metadata` and returns the parsed JSON document.
///
/// Returns `Result` so the helper stays outside the `expect`-in-tests
/// allowance; helpers must propagate errors rather than panic. `--offline` and
/// `CARGO_NET_OFFLINE` avoid any registry refresh and reduce lock contention.
fn workspace_metadata() -> eyre::Result<serde_json::Value> {
    let cargo = std::env::var("CARGO").unwrap_or_else(|_| "cargo".to_owned());
    let output = Command::new(cargo)
        .args([
            "metadata",
            "--no-deps",
            "--offline",
            "--format-version",
            "1",
        ])
        .env("CARGO_NET_OFFLINE", "1")
        .output()
        .wrap_err("failed to run `cargo metadata --no-deps --offline --format-version 1`")?;
    if !output.status.success() {
        return Err(eyre!(
            "`cargo metadata` exited with {}: {}",
            output.status,
            String::from_utf8_lossy(&output.stderr)
        ));
    }
    serde_json::from_slice(&output.stdout)
        .wrap_err("failed to parse the `cargo metadata` JSON document")
}

/// Extracts the set of member package names from a `cargo metadata` document.
///
/// Indexing a `serde_json::Value` is panic-free: a missing key yields
/// `Value::Null`, which `as_array` then reports as `None`. This is a
/// third-party `Index` impl and is not flagged by `clippy::indexing_slicing`.
fn member_names(metadata: &serde_json::Value) -> eyre::Result<BTreeSet<String>> {
    let member_ids: BTreeSet<&str> = metadata["workspace_members"]
        .as_array()
        .wrap_err("workspace_members is not an array")?
        .iter()
        .filter_map(|id| id.as_str())
        .collect();
    let packages = metadata["packages"]
        .as_array()
        .wrap_err("packages is not an array")?;
    let names = packages
        .iter()
        .filter(|pkg| pkg["id"].as_str().is_some_and(|id| member_ids.contains(id)))
        .filter_map(|pkg| pkg["name"].as_str().map(str::to_owned))
        .collect();
    Ok(names)
}

/// Reads a named package's declared dependency names from a metadata document.
fn declared_dependencies(
    metadata: &serde_json::Value,
    package: &str,
) -> eyre::Result<BTreeSet<String>> {
    let packages = metadata["packages"]
        .as_array()
        .wrap_err("packages is not an array")?;
    let found = packages
        .iter()
        .find(|pkg| pkg["name"].as_str() == Some(package))
        .wrap_err_with(|| format!("package `{package}` not found in metadata"))?;
    let deps = found["dependencies"]
        .as_array()
        .wrap_err("dependencies is not an array")?
        .iter()
        .filter_map(|dep| dep["name"].as_str().map(str::to_owned))
        .collect();
    Ok(deps)
}

/// Extracts the declared dependency edges between workspace members.
///
/// `cargo metadata --no-deps` lists every member's dependencies, including
/// ones that resolve to a registry. Only edges whose dependency name is itself
/// a member name are of interest here; those are the edges that make up the
/// intra-workspace graph.
fn declared_edges(metadata: &serde_json::Value) -> eyre::Result<BTreeSet<(String, String)>> {
    let members = member_names(metadata)?;
    let mut edges = BTreeSet::new();
    for member in &members {
        for dependency in declared_dependencies(metadata, member)? {
            if members.contains(&dependency) {
                edges.insert((member.clone(), dependency));
            }
        }
    }
    Ok(edges)
}

#[test]
#[file_serial]
fn workspace_has_exactly_three_intended_members() -> eyre::Result<()> {
    use pretty_assertions::assert_eq;

    let metadata = workspace_metadata()?;
    let actual = member_names(&metadata)?;
    let expected: BTreeSet<String> = ["rstest-xfail", "rstest-xfail-core", "rstest-xfail-macros"]
        .into_iter()
        .map(str::to_owned)
        .collect();

    assert_eq!(actual, expected, "workspace member set must match exactly");
    Ok(())
}

/// Enforces constraint D1: the core is a pure leaf.
///
/// The assertion is that the core declares *no* dependencies at all, rather
/// than that it avoids a named blacklist. A blacklist would silently accept any
/// newly added crate; an empty-set assertion cannot.
#[test]
#[file_serial]
fn core_declares_no_dependencies() -> eyre::Result<()> {
    let metadata = workspace_metadata()?;
    let deps = declared_dependencies(&metadata, "rstest-xfail-core")?;
    assert_that!(
        &deps,
        empty(),
        "rstest-xfail-core must stay a pure leaf (constraint D1)"
    );
    Ok(())
}

/// Pins the whole intra-workspace dependency graph, not only the core's edges.
///
/// D1 governs the core, but the boundary is also a statement about who may
/// depend on whom: the facade owns the edge to the macro crate, and no member
/// depends on the facade. Asserting the complete edge set catches a new
/// dependency edge anywhere in the workspace, which per-crate checks would miss.
#[test]
#[file_serial]
fn workspace_dependency_graph_matches_the_intended_boundaries() -> eyre::Result<()> {
    use pretty_assertions::assert_eq;

    let metadata = workspace_metadata()?;
    let actual = declared_edges(&metadata)?;
    let expected: BTreeSet<(String, String)> = INTENDED_EDGES
        .into_iter()
        .map(|(from, to)| (from.to_owned(), to.to_owned()))
        .collect();

    assert_eq!(
        actual, expected,
        "the intra-workspace dependency graph must match the intended boundaries"
    );
    Ok(())
}

#[rstest]
#[file_serial]
#[case("rstest-xfail-core")]
#[case("rstest-xfail-macros")]
#[case("rstest-xfail")]
fn each_intended_member_is_present(#[case] expected: &str) -> eyre::Result<()> {
    let metadata = workspace_metadata()?;
    let names = member_names(&metadata)?;
    assert_that!(&names, contains(eq(expected)));
    Ok(())
}
