# Rust 2026 Modernization — arxiv-data-explorer

**Date:** 2026-07-14
**Target:** Rust 1.97.0 (latest stable), Edition 2024
**Scope:** Edition migration, language feature adoption, workspace unification, tooling, CI

## 1. Edition Migration: 2021 → 2024

**Mechanism:** `cargo fix --edition` on both crates, then `cargo fix --edition-idioms`.

### Changes
- `crates/arxwasm/Cargo.toml`: `edition = "2021"` → `edition = "2024"`
- `crates/arxcheck/Cargo.toml`: `edition = "2021"` → `edition = "2024"`

### Expected auto-fixes
- `unsafe` blocks in `unsafe fn` bodies — likely zero in this codebase
- `unsafe extern` blocks — none present
- Never type fallback — none present
- Keyword reservation (`gen`) — no identifiers named `gen`

**Expected manual fixes: 0.** Both crates are simple and use no affected patterns.

## 2. Language Feature Adoption

### 2a. Let-else for read + parse chains (all 4 check files)

Replace the `match Ok/Err + early return` pattern used for file I/O and JSON parsing in `edges.rs`, `graph.rs`, `xref.rs`, and `shard.rs`.

**Pattern in edges.rs:44-84** (4 repetitions):
```rust
// Before
let content = match fs::read_to_string(&path) {
    Ok(c) => c,
    Err(e) => {
        violations.push(CheckViolation::error(...));
        return violations;
    }
};
let data: T = match serde_json::from_str(&content) {
    Ok(d) => d,
    Err(e) => { violations.push(...); return violations; }
};

// After — extracted helper
fn read_json_file<T: DeserializeOwned>(
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

// Usage — let-else
let Some(edges_file) = read_json_file::<CausalEdgesFile>(&edges_path, &mut violations) else {
    return violations;
};
```

**Files affected:** `edges.rs`, `graph.rs`, `xref.rs`, `shard.rs`
**Lines removed:** ~40 total

### 2b. Let chain for filename filter (shard.rs)

```rust
// Before
if !fname.starts_with("shard-") || path.extension().and_then(|s| s.to_str()) != Some("json") {
    continue;
}

// After — let chain (Rust 1.88)
if !fname.starts_with("shard-")
    && let Some(ext) = path.extension().and_then(|s| s.to_str())
    && ext != "json"
{ continue; }
```

### 2c. Extract `require_field` helper (api_contract.rs)

Three identical `match obj.get("field") { Some(Value::String(s)) if !s.is_empty() => {} _ => return ... }` blocks refactored to a helper:

```rust
fn require_string_field(obj: &Value, field: &str) -> Result<(), String> {
    match obj.get(field) {
        Some(Value::String(s)) if !s.is_empty() => Ok(()),
        _ => Err(format!("field \"{field}\" missing or empty")),
    }
}
```

### 2d. `assert_matches!` in tests (Rust 1.96)

Replace pattern-checking assertions:
```rust
// Before
assert!(violations.iter().any(|v| v.message.contains("source")));

// After
use std::assert_matches::assert_matches;
assert_matches!(
    violations.iter().find(|v| v.message.contains("source")),
    Some(_)
);
```

**Files affected:** All test modules in `edges.rs`, `graph.rs`, `xref.rs`, `shard.rs`

### 2e. `is_some_and` / `bool::then_some` where natural

```rust
// trigram.rs:41
// Before
if let Some(entries) = self.posting.get(g) { ... }
// After — could use is_some_and if logic changes, but if let is still idiomatic

// No strong candidates — the existing code is already idiomatic.
```

## 3. Workspace Unification

### Root Cargo.toml (new file)

```toml
[workspace]
resolver = "3"
members = ["crates/arxwasm", "crates/arxcheck"]

[workspace.package]
edition = "2024"
rust-version = "1.97"
```

### Crate Cargo.toml updates

Both crates add `rust-version = "1.97"` and remove standalone `edition` (inherited from workspace).

## 4. Tooling Configuration

### rust-toolchain.toml (new)

```toml
[toolchain]
channel = "1.97.0"
components = ["rustc", "cargo", "clippy", "rustfmt"]
```

### .rustfmt.toml (new)

```toml
style_edition = "2024"
version = "Two"
imports_granularity = "Module"
group_imports = "StdExternalCrate"
```

### clippy.toml (new)

```toml
msrv = "1.97.0"
```

### .cargo/config.toml (new)

```toml
[build]
warnings = "deny"
```

## 5. Dependency Auditing

### deny.toml (new)

```toml
[advisories]
vulnerability = "deny"
unmaintained = "warn"
yanked = "warn"

[licenses]
allow = ["MIT", "Apache-2.0", "ISC", "BSD-2-Clause", "BSD-3-Clause"]
copyleft = "deny"

[bans]
multiple-versions = "deny"
```

## 6. CI

### .github/workflows/rust.yml (new)

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

(`cargo deny check` requires `cargo install cargo-deny` — noted but not enforced in initial CI)

## Files Changed Summary

| File | Action |
|------|--------|
| `Cargo.toml` (root) | **Create** — workspace root |
| `rust-toolchain.toml` | **Create** — pin 1.97.0 |
| `.rustfmt.toml` | **Create** — style edition 2024 |
| `clippy.toml` | **Create** — MSRV 1.97 |
| `.cargo/config.toml` | **Create** — deny warnings |
| `deny.toml` | **Create** — license/bans/advisories |
| `.github/workflows/rust.yml` | **Create** — CI |
| `crates/arxwasm/Cargo.toml` | **Edit** — edition 2024, rust-version |
| `crates/arxcheck/Cargo.toml` | **Edit** — edition 2024, rust-version |
| `crates/arxcheck/src/checks/mod.rs` | **Edit** — add `read_json_file` helper |
| `crates/arxcheck/src/checks/edges.rs` | **Edit** — helper usage, assert_matches! |
| `crates/arxcheck/src/checks/graph.rs` | **Edit** — helper usage, assert_matches! |
| `crates/arxcheck/src/checks/xref.rs` | **Edit** — helper usage, assert_matches! |
| `crates/arxcheck/src/checks/shard.rs` | **Edit** — helper usage, let chain, assert_matches! |
| `crates/arxcheck/src/checks/api_contract.rs` | **Edit** — require_field helper |
| `crates/arxwasm/src/lib.rs` | **Edit** — edition idioms only |
