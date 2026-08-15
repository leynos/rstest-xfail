//! End-to-end checks over `cargo metadata` for roadmap task 1.1.1: the
//! workspace exposes exactly the three intended members, and the core crate
//! depends on none of its siblings or on procedural-macro tooling (constraint
//! D1). These shell out to `cargo metadata`, so they are serialized to bound
//! package-cache lock contention.

use std::{collections::BTreeSet, process::Command};

use googletest::prelude::{assert_that, contains, eq, not};
use rstest::rstest;
use serial_test::serial;

/// Runs `cargo metadata` and returns the parsed JSON document.
///
/// Returns `Result` so the helper stays outside the `expect`-in-tests
/// allowance; helpers must propagate errors rather than panic. `--offline` and
/// `CARGO_NET_OFFLINE` avoid any registry refresh and reduce lock contention.
fn workspace_metadata() -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    let cargo = std::env::var("CARGO").unwrap_or_else(|_| "cargo".to_owned());
    let output = Command::new(cargo)
        .args(["metadata", "--no-deps", "--offline", "--format-version", "1"])
        .env("CARGO_NET_OFFLINE", "1")
        .output()?;
    if !output.status.success() {
        return Err(format!(
            "cargo metadata failed: {}",
            String::from_utf8_lossy(&output.stderr)
        )
        .into());
    }
    Ok(serde_json::from_slice(&output.stdout)?)
}

/// Extracts the set of member package names from a `cargo metadata` document.
///
/// Indexing a `serde_json::Value` is panic-free: a missing key yields
/// `Value::Null`, which `as_array` then reports as `None`. This is a
/// third-party `Index` impl and is not flagged by `clippy::indexing_slicing`.
fn member_names(
    metadata: &serde_json::Value,
) -> Result<BTreeSet<String>, Box<dyn std::error::Error>> {
    let member_ids: BTreeSet<&str> = metadata["workspace_members"]
        .as_array()
        .ok_or("workspace_members is not an array")?
        .iter()
        .filter_map(|id| id.as_str())
        .collect();
    let packages = metadata["packages"]
        .as_array()
        .ok_or("packages is not an array")?;
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
) -> Result<BTreeSet<String>, Box<dyn std::error::Error>> {
    let packages = metadata["packages"]
        .as_array()
        .ok_or("packages is not an array")?;
    let found = packages
        .iter()
        .find(|pkg| pkg["name"].as_str() == Some(package))
        .ok_or("package not found in metadata")?;
    let deps = found["dependencies"]
        .as_array()
        .ok_or("dependencies is not an array")?
        .iter()
        .filter_map(|dep| dep["name"].as_str().map(str::to_owned))
        .collect();
    Ok(deps)
}

#[test]
#[serial]
fn workspace_has_exactly_three_intended_members()
-> Result<(), Box<dyn std::error::Error>> {
    use pretty_assertions::assert_eq;

    let metadata = workspace_metadata()?;
    let actual = member_names(&metadata)?;
    let expected: BTreeSet<String> =
        ["rstest-xfail", "rstest-xfail-core", "rstest-xfail-macros"]
            .into_iter()
            .map(str::to_owned)
            .collect();

    assert_eq!(actual, expected, "workspace member set must match exactly");
    Ok(())
}

#[test]
#[serial]
fn core_has_no_forbidden_dependencies()
-> Result<(), Box<dyn std::error::Error>> {
    let metadata = workspace_metadata()?;
    let deps = declared_dependencies(&metadata, "rstest-xfail-core")?;
    for forbidden in ["rstest-xfail-macros", "rstest-xfail", "syn", "quote", "proc-macro2"] {
        // `&BTreeSet<String>` is a `Copy` container whose items are `&String`;
        // `&String: PartialEq<&str>` holds, so `eq(forbidden)` matches.
        assert_that!(&deps, not(contains(eq(forbidden))));
    }
    Ok(())
}

#[rstest]
#[case("rstest-xfail-core")]
#[case("rstest-xfail-macros")]
#[case("rstest-xfail")]
fn each_intended_member_is_present(
    #[case] expected: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let metadata = workspace_metadata()?;
    let names = member_names(&metadata)?;
    assert_that!(&names, contains(eq(expected)));
    Ok(())
}
