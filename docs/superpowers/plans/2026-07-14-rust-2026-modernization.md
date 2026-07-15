# Rust 2026 Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade arxiv-data-explorer's two Rust crates to Rust 1.97 / Edition 2024 with full modern tooling, CI, and code patterns.

**Architecture:** Two standalone crates (`arxwasm` WASM lib, `arxcheck` WASM+CLI lib/bin) get unified under a root workspace, edition-migrated, refactored with 2026-idiomatic patterns, and guarded by lint/format/CI tooling.

**Tech Stack:** Rust 1.97.0, Edition 2024, clap 4, wasm-bindgen, serde, cargo-deny

## Global Constraints

- `edition = "2024"` required (for let chains, assert_matches!, RPIT capture rules)
- `rust-version = "1.97"` in all Cargo.toml
- `channel = "1.97.0"` in rust-toolchain.toml
- Clippy must pass with `-D warnings`
- All existing tests must pass unchanged
- No dependency version bumps beyond `cargo update`

---

### Task 1: Root workspace + rust-toolchain.toml

**Files:**
- Create: `Cargo.toml` (root workspace)
- Create: `rust-toolchain.toml`
- Modify: `crates/arxwasm/Cargo.toml`
- Modify: `crates/arxcheck/Cargo.toml`

**Interfaces:**
- Consumes: existing crate Cargo.toml files
- Produces: workspace root, pinned toolchain

- [ ] **Step 1: Create root Cargo.toml workspace**

```toml
[workspace]
resolver = "3"
members = ["crates/arxwasm", "crates/arxcheck"]
```

- [ ] **Step 2: Create rust-toolchain.toml**

```toml
[toolchain]
channel = "1.97.0"
components = ["rustc", "cargo", "clippy", "rustfmt"]
```

- [ ] **Step 3: Update arxwasm/Cargo.toml — add rust-version**

Insert `rust-version = "1.97"` after the `edition` line.

- [ ] **Step 4: Update arxcheck/Cargo.toml — add rust-version**

Insert `rust-version = "1.97"` after the `edition` line.

- [ ] **Step 5: Verify workspace resolves**

Run: `cargo check --workspace`
Expected: clean build, no errors

- [ ] **Step 6: Commit**

```bash
git add Cargo.toml rust-toolchain.toml crates/arxwasm/Cargo.toml crates/arxcheck/Cargo.toml
git commit -m "feat: add root workspace, pin rust 1.97.0"
```

---

### Task 2: Edition migration 2021 → 2024

**Files:**
- Modify: `crates/arxwasm/Cargo.toml` (edition field)
- Modify: `crates/arxcheck/Cargo.toml` (edition field)
- Various `.rs` files (auto-fixed by cargo fix)

- [ ] **Step 1: Run `cargo update`**

```bash
cargo update
```

- [ ] **Step 2: Run `cargo fix --edition --workspace --all-features`**

```bash
cargo fix --edition --workspace --all-features
```
Expected: applies compatibility lints. Likely zero changes for this codebase.

- [ ] **Step 3: Set edition = "2024" in both Cargo.toml files**

In both `crates/arxwasm/Cargo.toml` and `crates/arxcheck/Cargo.toml`:
```toml
edition = "2024"
```

- [ ] **Step 4: Verify build**

```bash
cargo check --workspace
```
Expected: clean build on edition 2024.

- [ ] **Step 5: Run `cargo fix --edition-idioms`**

```bash
cargo fix --edition-idioms --workspace --all-features
```

- [ ] **Step 6: Run tests**

```bash
cargo test --workspace
```
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: migrate to rust edition 2024"
```

---

### Task 3: Tooling config — rustfmt, clippy, cargo

**Files:**
- Create: `.rustfmt.toml`
- Create: `clippy.toml`
- Create: `.cargo/config.toml`

- [ ] **Step 1: Create .rustfmt.toml**

```toml
style_edition = "2024"
version = "Two"
imports_granularity = "Module"
group_imports = "StdExternalCrate"
```

- [ ] **Step 2: Create clippy.toml**

```toml
msrv = "1.97.0"
```

- [ ] **Step 3: Create .cargo/config.toml**

```toml
[build]
warnings = "deny"
```

- [ ] **Step 4: Run rustfmt + clippy to verify**

```bash
cargo fmt --all
cargo clippy --workspace -- -D warnings
```
Expected: clean format, clean clippy.

- [ ] **Step 5: Commit**

```bash
git add .rustfmt.toml clippy.toml .cargo/config.toml
git commit -m "feat: add rustfmt, clippy, deny-warnings config"
```

---

### Task 4: Add `read_json_file` helper to checks/mod.rs

**Files:**
- Modify: `crates/arxcheck/src/checks/mod.rs`
- Modify: `crates/arxcheck/src/lib.rs` (re-export)

- [ ] **Step 1: Add `serde::de::DeserializeOwned` import and helper fn**

At top of `checks/mod.rs`:
```rust
use std::path::Path;
use std::fs;
use serde::de::DeserializeOwned;
use crate::CheckViolation;

pub(crate) fn read_json_file<T: DeserializeOwned>(
    path: &Path,
    violations: &mut Vec<CheckViolation>,
) -> Option<T> {
    let content = match fs::read_to_string(path) {
        Ok(c) => c,
        Err(e) => {
            violations.push(CheckViolation::error(
                path.display().to_string(),
                format!("cannot read: {e}"),
            ));
            return None;
        }
    };
    match serde_json::from_str(&content) {
        Ok(v) => Some(v),
        Err(e) => {
            violations.push(CheckViolation::error(
                path.display().to_string(),
                format!("invalid JSON: {e}"),
            ));
            None
        }
    }
}
```

- [ ] **Step 2: Verify build**

```bash
cargo check --workspace
```
Expected: clean build.

- [ ] **Step 3: Commit**

```bash
git add crates/arxcheck/src/checks/mod.rs
git commit -m "feat: add read_json_file helper for check crates"
```

---

### Task 5: Modernize edges.rs

**Files:**
- Modify: `crates/arxcheck/src/checks/edges.rs`

- [ ] **Step 1: Replace match chains with read_json_file helper**

Replace lines 44-84 (4 `match Ok/Err + early return` blocks) with:

```rust
let edges_file: CausalEdgesFile = match read_json_file(&edges_path, &mut violations) {
    Some(f) => f,
    None => return violations,
};
let dynamics_file: DynamicsFile = match read_json_file(&dynamics_path, &mut violations) {
    Some(f) => f,
    None => return violations,
};
```

Add `use super::read_json_file;` at top of the file.

- [ ] **Step 2: Add `use std::assert_matches::assert_matches;` at top of test module**

At top of `mod tests { }` block.

- [ ] **Step 3: Replace assertions in test for `test_edges_missing_source`**

Replace `assert!(violations.iter().any(|v| v.message.contains("source")));` with:
```rust
assert_matches!(
    violations.iter().find(|v| v.message.contains("source")),
    Some(_)
);
```

- [ ] **Step 4: Replace assertions in `test_edges_bad_ci_range`**

Replace `assert!(violations.iter().any(|v| v.message.contains("ci_lower")));` with:
```rust
assert_matches!(
    violations.iter().find(|v| v.message.contains("ci_lower")),
    Some(_)
);
```

- [ ] **Step 5: Replace assertions in `test_edges_bad_prob`**

Replace `assert!(violations.iter().any(|v| v.message.contains("prob")));` with:
```rust
assert_matches!(
    violations.iter().find(|v| v.message.contains("prob")),
    Some(_)
);
```

- [ ] **Step 6: Verify build + tests**

```bash
cargo check --workspace
cargo test --workspace
```
Expected: clean build, all tests pass.

- [ ] **Step 7: Commit**

```bash
git add crates/arxcheck/src/checks/edges.rs
git commit -m "feat: modernize edges.rs — read_json_file helper, assert_matches!"
```

---

### Task 6: Modernize graph.rs

**Files:**
- Modify: `crates/arxcheck/src/checks/graph.rs`

- [ ] **Step 1: Replace match chains with read_json_file helper**

Add `use super::read_json_file;` at top.

Replace lines 33-53 (2 match blocks):

```rust
let graph: CategoryGraph = match read_json_file(&path, &mut violations) {
    Some(g) => g,
    None => return violations,
};
```

- [ ] **Step 2: Update tests — add assert_matches! import and replace pattern assertions**

Replace `assert!(violations.iter().any(|v| v.message.contains("empty id")));` with:
```rust
assert_matches!(
    violations.iter().find(|v| v.message.contains("empty id")),
    Some(_)
);
```

Replace `assert!(violations.iter().any(|v| v.message.contains("duplicate")));` with:
```rust
assert_matches!(
    violations.iter().find(|v| v.message.contains("duplicate")),
    Some(_)
);
```

Replace `assert!(violations.iter().any(|v| v.message.contains("not found")));` with:
```rust
assert_matches!(
    violations.iter().find(|v| v.message.contains("not found")),
    Some(_)
);
```

- [ ] **Step 3: Verify build + tests**

```bash
cargo check --workspace
cargo test --workspace
```

- [ ] **Step 4: Commit**

```bash
git add crates/arxcheck/src/checks/graph.rs
git commit -m "feat: modernize graph.rs — read_json_file helper, assert_matches!"
```

---

### Task 7: Modernize xref.rs

**Files:**
- Modify: `crates/arxcheck/src/checks/xref.rs`

- [ ] **Step 1: Replace match chains with read_json_file helper**

Add `use super::read_json_file;` at top.

Replace lines 24-44:

```rust
let rankings: Vec<RankingEntry> = match read_json_file(&path, &mut violations) {
    Some(r) => r,
    None => return violations,
};
```

- [ ] **Step 2: Update tests with assert_matches!**

Replace pattern-based assertions (`fn test_xref_relative_gt_100`, `fn test_xref_missing_author_in_shard`) with `assert_matches!`.

- [ ] **Step 3: Verify build + tests**

```bash
cargo check --workspace
cargo test --workspace
```

- [ ] **Step 4: Commit**

```bash
git add crates/arxcheck/src/checks/xref.rs
git commit -m "feat: modernize xref.rs — read_json_file helper, assert_matches!"
```

---

### Task 8: Modernize shard.rs (helper + let chain + assert_matches!)

**Files:**
- Modify: `crates/arxcheck/src/checks/shard.rs`

- [ ] **Step 1: Replace file read match with read_json_file helper + let-else**

Add `use super::read_json_file;` at top of file.

Replace lines 41-78:

```rust
let shard: std::collections::HashMap<String, ShardEntry> =
    match read_json_file(&path, &mut violations) {
        Some(m) => m,
        None => continue,
    };
```

- [ ] **Step 2: Apply let chain for filename filter**

Replace line 38:
```rust
if !fname.starts_with("shard-")
    && let Some(ext) = path.extension().and_then(|s| s.to_str())
    && ext != "json"
{ continue; }
```

- [ ] **Step 3: Update tests with assert_matches!**

Replace pattern assertions with `assert_matches!` where appropriate.

- [ ] **Step 4: Verify build + tests**

```bash
cargo check --workspace
cargo test --workspace
```

- [ ] **Step 5: Commit**

```bash
git add crates/arxcheck/src/checks/shard.rs
git commit -m "feat: modernize shard.rs — let chain, helper, assert_matches!"
```

---

### Task 9: Modernize api_contract.rs (require_field helper)

**Files:**
- Modify: `crates/arxcheck/src/checks/api_contract.rs`

- [ ] **Step 1: Add require_string_field and require_number_field helpers**

Add before `pub fn validate_paper_result`:

```rust
fn require_string_field(obj: &Value, field: &str) -> Result<(), String> {
    match obj.get(field) {
        Some(Value::String(s)) if !s.is_empty() => Ok(()),
        _ => Err(format!("field \"{field}\" missing or empty")),
    }
}

fn require_number_field(obj: &Value, field: &str) -> Result<(), String> {
    match obj.get(field) {
        Some(Value::Number(_)) => Ok(()),
        _ => Err(format!("field \"{field}\" missing or not a number")),
    }
}
```

- [ ] **Step 2: Refactor validate_paper_detail using helper**

Replace lines 43-54:

```rust
for field in ["title", "abstract", "venue"] {
    require_string_field(&v, field)?;
}
```

Return `Vec::new()` if no errors at end.

- [ ] **Step 3: Refactor validate_author_profile using helpers**

Replace lines 67-78:

```rust
require_string_field(&v, "name")?;
require_number_field(&v, "worksCount")?;
require_number_field(&v, "citedByCount")?;
Vec::new()
```

- [ ] **Step 4: Verify build + tests**

```bash
cargo check --workspace
cargo test --workspace
```

- [ ] **Step 5: Commit**

```bash
git add crates/arxcheck/src/checks/api_contract.rs
git commit -m "feat: modernize api_contract.rs — require_field helpers"
```

---

### Task 10: run cargo fmt + final verification

- [ ] **Step 1: Format all code**

```bash
cargo fmt --all
```

- [ ] **Step 2: Clippy check**

```bash
cargo clippy --workspace -- -D warnings
```
Expected: clean. If warnings, fix them.

- [ ] **Step 3: Full test suite**

```bash
cargo test --workspace
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: cargo fmt, final clippy cleanup"
```

---

### Task 11: deny.toml

**Files:**
- Create: `deny.toml`

- [ ] **Step 1: Create deny.toml**

```toml
[advisories]
vulnerability = "deny"
unmaintained = "warn"
yanked = "warn"
notice = "warn"

[licenses]
allow = ["MIT", "Apache-2.0", "ISC", "BSD-2-Clause", "BSD-3-Clause"]
copyleft = "deny"

[bans]
multiple-versions = "deny"
```

- [ ] **Step 2: Commit**

```bash
git add deny.toml
git commit -m "feat: add deny.toml for dependency auditing"
```

---

### Task 12: CI workflow

**Files:**
- Create: `.github/workflows/rust.yml`

- [ ] **Step 1: Create CI workflow**

```yaml
name: Rust CI
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: rustup show
      - run: cargo check --workspace
      - run: cargo clippy --workspace -- -D warnings
      - run: cargo test --workspace
```

- [ ] **Step 2: Commit**

```bash
mkdir -p .github/workflows
git add .github/workflows/rust.yml
git commit -m "feat: add rust CI workflow"
```
