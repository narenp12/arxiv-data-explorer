# arxcheck — Validation Checker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dual-target Rust crate that validates JSON shard integrity (CI CLI) and API response contracts (browser WASM), catching schema drift and data corruption before deploy or during runtime.

**Architecture:** A single `crates/arxcheck/` crate with conditional compilation: `#[cfg(not(target_arch = "wasm32"))]` for CLI binary (file I/O, clap), `#[cfg(target_arch = "wasm32")]` for WASM (wasm-bindgen exports). Validation logic in `src/checks/` is target-agnostic.

**Tech Stack:** Rust, serde, serde_json, clap (CLI), wasm-bindgen (WASM)

## Global Constraints

- No `regex` or `ndarray` dependencies
- CLI binary must have zero runtime dependencies beyond `clap` + `serde_json`
- WASM binary must stay under 100KB gzipped
- All validation functions take `&[u8]` or `&str` (no file I/O in shared code)
- Each check returns a `Vec<CheckViolation>` — never panics

---

## File Structure

```
crates/arxcheck/
├── Cargo.toml
└── src/
    ├── lib.rs              — module tree, Violation type, Check trait
    ├── checks/
    │   ├── mod.rs          — re-exports + run_all()
    │   ├── shard.rs        — author shard integrity
    │   ├── edges.rs        — causal_edges.json × category_dynamics.json
    │   ├── graph.rs        — category_graph.json validity
    │   ├── xref.rs         — author_rankings.json cross-reference
    │   └── api_contract.rs — API response shape validation
    ├── bin/arxcheck.rs     — CLI entrypoint (native only)
    └── wasm.rs             — wasm-bindgen exports (WASM only)
```

---

### Task 1: Cargo project + shared types

**Files:**
- Create: `crates/arxcheck/Cargo.toml`
- Create: `crates/arxcheck/src/lib.rs`
- Create: `crates/arxcheck/src/checks/mod.rs`

**Interfaces:**
- Consumes: nothing
- Produces: `CheckViolation { file: String, severity: Severity, message: String }`, `Severity { Error | Warning }`, `Check trait`

- [ ] **Step 1: Write Cargo.toml**

```toml
[package]
name = "arxcheck"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib", "rlib"]

[[bin]]
name = "arxcheck"
path = "src/bin/arxcheck.rs"
required-features = ["cli"]

[features]
default = ["cli"]
cli = ["dep:clap"]

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
clap = { version = "4", optional = true, features = ["derive"] }
wasm-bindgen = { version = "0.2", optional = true }
serde-wasm-bindgen = { version = "0.6", optional = true }

[target.'cfg(target_arch = "wasm32")'.dependencies]
wasm-bindgen = "0.2"
serde-wasm-bindgen = "0.6"

[profile.release]
opt-level = "z"
lto = true
codegen-units = 1
panic = "abort"
strip = true
```

- [ ] **Step 2: Write lib.rs**

```rust
pub mod checks;

#[derive(Debug, Clone, PartialEq)]
pub enum Severity {
    Error,
    Warning,
}

#[derive(Debug, Clone)]
pub struct CheckViolation {
    pub file: String,
    pub severity: Severity,
    pub message: String,
}

impl CheckViolation {
    pub fn error(file: impl Into<String>, message: impl Into<String>) -> Self {
        Self { file: file.into(), severity: Severity::Error, message: message.into() }
    }
    pub fn warning(file: impl Into<String>, message: impl Into<String>) -> Self {
        Self { file: file.into(), severity: Severity::Warning, message: message.into() }
    }
}

pub trait Check {
    fn name(&self) -> &'static str;
    fn run(&self, data_dir: &str) -> Vec<CheckViolation>;
}
```

- [ ] **Step 3: Write checks/mod.rs**

```rust
use crate::{Check, CheckViolation};

pub mod shard;
pub mod edges;
pub mod graph;
pub mod xref;
pub mod api_contract;

pub fn run_all(data_dir: &str) -> Vec<CheckViolation> {
    let checks: Vec<Box<dyn Check>> = vec![
        Box::new(shard::ShardCheck),
        Box::new(edges::EdgesCheck),
        Box::new(graph::GraphCheck),
        Box::new(xref::CrossRefCheck),
    ];
    let mut all = Vec::new();
    for c in &checks {
        let violations = c.run(data_dir);
        if violations.is_empty() {
            println!("  ✓ {}", c.name());
        } else {
            println!("  ✗ {} — {} violations", c.name(), violations.len());
        }
        all.extend(violations);
    }
    all
}
```

- [ ] **Step 4: Verify it compiles**

```bash
cd crates/arxcheck
cargo build
```
Expected: builds without errors.

- [ ] **Step 5: Commit**

```bash
git add crates/arxcheck/
git commit -m "feat(arxcheck): scaffold crate with shared types"
```

---

### Task 2: Shard integrity check

**Files:**
- Create: `crates/arxcheck/src/checks/shard.rs`

**Interfaces:**
- Produces: `ShardCheck` implementing `Check`

- [ ] **Step 1: Write shard.rs**

```rust
use std::fs;
use std::collections::HashSet;
use std::path::Path;
use crate::{Check, CheckViolation, Severity};
use serde::Deserialize;

#[derive(Deserialize)]
struct ShardEntry {
    w: u32,
    co: Vec<[String; 2]>,
}

pub struct ShardCheck;

impl Check for ShardCheck {
    fn name(&self) -> &'static str { "shard" }

    fn run(&self, data_dir: &str) -> Vec<CheckViolation> {
        let mut violations = Vec::new();
        let shards_dir = Path::new(data_dir).join("authors");
        let mut all_names: HashSet<String> = HashSet::new();

        let entries = match fs::read_dir(&shards_dir) {
            Ok(e) => e,
            Err(e) => {
                violations.push(CheckViolation::error(
                    shards_dir.display().to_string(),
                    format!("cannot read directory: {e}"),
                ));
                return violations;
            }
        };

        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) != Some("json") {
                continue;
            }
            let content = match fs::read_to_string(&path) {
                Ok(c) => c,
                Err(e) => {
                    violations.push(CheckViolation::error(
                        path.display().to_string(),
                        format!("cannot read: {e}"),
                    ));
                    continue;
                }
            };
            let shard: Result<std::collections::HashMap<String, ShardEntry>, _> =
                serde_json::from_str(&content);
            match shard {
                Ok(map) => {
                    for name in map.keys() {
                        if !all_names.insert(name.clone()) {
                            violations.push(CheckViolation::warning(
                                path.display().to_string(),
                                format!("duplicate author name across shards: \"{name}\""),
                            ));
                        }
                    }
                    for (name, entry) in &map {
                        if entry.co.iter().any(|c| c.len() != 2) {
                            violations.push(CheckViolation::error(
                                path.display().to_string(),
                                format!("author \"{name}\" has malformed co-author entry"),
                            ));
                        }
                    }
                }
                Err(e) => {
                    violations.push(CheckViolation::error(
                        path.display().to_string(),
                        format!("invalid JSON: {e}"),
                    ));
                }
            }
        }
        violations
    }
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cargo build
```
Expected: builds.

- [ ] **Step 3: Commit**

```bash
git add crates/arxcheck/src/checks/shard.rs
git commit -m "feat(arxcheck): shard integrity check"
```

---

### Task 3: Edges × dynamics cross-reference check

**Files:**
- Create: `crates/arxcheck/src/checks/edges.rs`

**Interfaces:**
- Produces: `EdgesCheck` implementing `Check`

- [ ] **Step 1: Write edges.rs**

```rust
use std::fs;
use std::collections::HashSet;
use std::path::Path;
use crate::{Check, CheckViolation};
use serde::Deserialize;

#[derive(Deserialize)]
struct CausalEdgesFile {
    edges: Vec<CausalEdge>,
    categories: Vec<CategoryInfo>,
}

#[derive(Deserialize)]
struct CausalEdge {
    source: String,
    target: String,
    weight: f64,
    ci_lower: f64,
    ci_upper: f64,
    prob: f64,
}

#[derive(Deserialize)]
struct CategoryInfo {
    id: String,
}

#[derive(Deserialize)]
struct DynamicsFile {
    series: std::collections::HashMap<String, Vec<i64>>,
}

pub struct EdgesCheck;

impl Check for EdgesCheck {
    fn name(&self) -> &'static str { "edges" }

    fn run(&self, data_dir: &str) -> Vec<CheckViolation> {
        let mut violations = Vec::new();
        let edges_path = Path::new(data_dir).join("causal_edges.json");
        let dynamics_path = Path::new(data_dir).join("category_dynamics.json");

        let edges_content = match fs::read_to_string(&edges_path) {
            Ok(c) => c,
            Err(e) => {
                violations.push(CheckViolation::error(
                    edges_path.display().to_string(),
                    format!("cannot read: {e}"),
                ));
                return violations;
            }
        };
        let dynamics_content = match fs::read_to_string(&dynamics_path) {
            Ok(c) => c,
            Err(e) => {
                violations.push(CheckViolation::error(
                    dynamics_path.display().to_string(),
                    format!("cannot read: {e}"),
                ));
                return violations;
            }
        };

        let edges_file: CausalEdgesFile = match serde_json::from_str(&edges_content) {
            Ok(f) => f,
            Err(e) => {
                violations.push(CheckViolation::error(
                    edges_path.display().to_string(),
                    format!("invalid JSON: {e}"),
                ));
                return violations;
            }
        };
        let dynamics_file: DynamicsFile = match serde_json::from_str(&dynamics_content) {
            Ok(f) => f,
            Err(e) => {
                violations.push(CheckViolation::error(
                    dynamics_path.display().to_string(),
                    format!("invalid JSON: {e}"),
                ));
                return violations;
            }
        };

        let category_ids: HashSet<&str> = dynamics_file.series.keys().map(|s| s.as_str()).collect();

        for edge in &edges_file.edges {
            if !category_ids.contains(edge.source.as_str()) {
                violations.push(CheckViolation::error(
                    edges_path.display().to_string(),
                    format!("edge source \"{}\" not found in category_dynamics.json", edge.source),
                ));
            }
            if !category_ids.contains(edge.target.as_str()) {
                violations.push(CheckViolation::error(
                    edges_path.display().to_string(),
                    format!("edge target \"{}\" not found in category_dynamics.json", edge.target),
                ));
            }
            if edge.ci_lower >= edge.ci_upper {
                violations.push(CheckViolation::warning(
                    edges_path.display().to_string(),
                    format!("edge {}→{} has ci_lower >= ci_upper", edge.source, edge.target),
                ));
            }
            if !(0.5..=1.0).contains(&edge.prob) {
                violations.push(CheckViolation::warning(
                    edges_path.display().to_string(),
                    format!("edge {}→{} has prob {} outside [0.5, 1.0]", edge.source, edge.target, edge.prob),
                ));
            }
        }

        for cat in &edges_file.categories {
            if !category_ids.contains(cat.id.as_str()) {
                violations.push(CheckViolation::warning(
                    edges_path.display().to_string(),
                    format!("category \"{}\" has trend but no dynamics series", cat.id),
                ));
            }
        }

        violations
    }
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cargo build
```
Expected: builds.

- [ ] **Step 3: Commit**

```bash
git add crates/arxcheck/src/checks/edges.rs
git commit -m "feat(arxcheck): edges × dynamics cross-reference check"
```

---

### Task 4: Category graph integrity check

**Files:**
- Create: `crates/arxcheck/src/checks/graph.rs`

**Interfaces:**
- Produces: `GraphCheck` implementing `Check`

- [ ] **Step 1: Write graph.rs**

```rust
use std::collections::HashSet;
use std::fs;
use std::path::Path;
use crate::{Check, CheckViolation};
use serde::Deserialize;

#[derive(Deserialize)]
struct CategoryGraph {
    nodes: Vec<GraphNode>,
    edges: Vec<GraphEdge>,
}

#[derive(Deserialize)]
struct GraphNode {
    id: String,
}

#[derive(Deserialize)]
struct GraphEdge {
    source: String,
    target: String,
}

pub struct GraphCheck;

impl Check for GraphCheck {
    fn name(&self) -> &'static str { "graph" }

    fn run(&self, data_dir: &str) -> Vec<CheckViolation> {
        let mut violations = Vec::new();
        let path = Path::new(data_dir).join("category_graph.json");

        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(e) => {
                violations.push(CheckViolation::error(
                    path.display().to_string(),
                    format!("cannot read: {e}"),
                ));
                return violations;
            }
        };

        let graph: CategoryGraph = match serde_json::from_str(&content) {
            Ok(g) => g,
            Err(e) => {
                violations.push(CheckViolation::error(
                    path.display().to_string(),
                    format!("invalid JSON: {e}"),
                ));
                return violations;
            }
        };

        let node_ids: HashSet<&str> = graph.nodes.iter().map(|n| n.id.as_str()).collect();
        let mut edge_pairs = HashSet::new();

        for node in &graph.nodes {
            if node.id.is_empty() {
                violations.push(CheckViolation::error(
                    path.display().to_string(),
                    "node has empty id".to_string(),
                ));
            }
        }

        for edge in &graph.edges {
            if !node_ids.contains(edge.source.as_str()) {
                violations.push(CheckViolation::error(
                    path.display().to_string(),
                    format!("edge source \"{}\" not found in nodes", edge.source),
                ));
            }
            if !node_ids.contains(edge.target.as_str()) {
                violations.push(CheckViolation::error(
                    path.display().to_string(),
                    format!("edge target \"{}\" not found in nodes", edge.target),
                ));
            }
            let pair = (edge.source.as_str(), edge.target.as_str());
            if !edge_pairs.insert(pair) {
                violations.push(CheckViolation::warning(
                    path.display().to_string(),
                    format!("duplicate edge: {} → {}", edge.source, edge.target),
                ));
            }
        }

        violations
    }
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cargo build
```
Expected: builds.

- [ ] **Step 3: Commit**

```bash
git add crates/arxcheck/src/checks/graph.rs
git commit -m "feat(arxcheck): category graph integrity check"
```

---

### Task 5: Author rankings cross-reference check

**Files:**
- Create: `crates/arxcheck/src/checks/xref.rs`

**Interfaces:**
- Produces: `CrossRefCheck` implementing `Check`

- [ ] **Step 1: Write xref.rs**

```rust
use std::collections::HashSet;
use std::fs;
use std::path::Path;
use crate::{Check, CheckViolation, Severity};
use serde::Deserialize;

#[derive(Deserialize)]
struct RankingEntry {
    name: String,
    papers: u32,
    relative: u32,
}

pub struct CrossRefCheck;

impl Check for CrossRefCheck {
    fn name(&self) -> &'static str { "cross_ref" }

    fn run(&self, data_dir: &str) -> Vec<CheckViolation> {
        let mut violations = Vec::new();
        let path = Path::new(data_dir).join("author_rankings.json");

        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(e) => {
                violations.push(CheckViolation::error(
                    path.display().to_string(),
                    format!("cannot read: {e}"),
                ));
                return violations;
            }
        };

        let rankings: Vec<RankingEntry> = match serde_json::from_str(&content) {
            Ok(r) => r,
            Err(e) => {
                violations.push(CheckViolation::error(
                    path.display().to_string(),
                    format!("invalid JSON: {e}"),
                ));
                return violations;
            }
        };

        // Collect all names from shards
        let shards_dir = Path::new(data_dir).join("authors");
        let mut shard_names: HashSet<String> = HashSet::new();
        if let Ok(entries) = fs::read_dir(&shards_dir) {
            for entry in entries.flatten() {
                let p = entry.path();
                if p.extension().and_then(|s| s.to_str()) != Some("json") { continue; }
                let content = fs::read_to_string(&p).unwrap_or_default();
                let map: std::collections::HashMap<String, serde_json::Value> =
                    serde_json::from_str(&content).unwrap_or_default();
                shard_names.extend(map.into_keys());
            }
        }

        for entry in &rankings {
            if !shard_names.contains(&entry.name) {
                violations.push(CheckViolation::warning(
                    path.display().to_string(),
                    format!("ranked author \"{}\" not found in any shard", entry.name),
                ));
            }
            if entry.relative > 100 {
                violations.push(CheckViolation::warning(
                    path.display().to_string(),
                    format!("author \"{}\" has relative {} > 100", entry.name, entry.relative),
                ));
            }
        }

        violations
    }
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cargo build
```
Expected: builds.

- [ ] **Step 3: Commit**

```bash
git add crates/arxcheck/src/checks/xref.rs
git commit -m "feat(arxcheck): author rankings cross-reference check"
```

---

### Task 6: API contract validation (WASM target)

**Files:**
- Create: `crates/arxcheck/src/checks/api_contract.rs`

**Interfaces:**
- Produces: `validate_paper_result(json: &[u8]) -> Vec<String>`, `validate_paper_detail(json: &[u8]) -> Vec<String>`, `validate_author_profile(json: &[u8]) -> Vec<String>`

- [ ] **Step 1: Write api_contract.rs**

```rust
// Target-agnostic: operates on &[u8], no wasm-bindgen here.
use serde_json::Value;

macro_rules! required_str {
    ($obj:expr, $field:expr) => {
        match $obj.get($field) {
            Some(Value::String(s)) if !s.is_empty() => {}
            _ => return vec![format!("field \"{}\" missing or empty", $field)],
        }
    };
}

macro_rules! required_num {
    ($obj:expr, $field:expr) => {
        match $obj.get($field) {
            Some(Value::Number(_)) => {}
            _ => return vec![format!("field \"{}\" missing or not a number", $field)],
        }
    };
}

fn string_fields_present(obj: &Value, fields: &[&str]) -> Vec<String> {
    let mut errors = Vec::new();
    for f in fields {
        match obj.get(f) {
            Some(Value::String(s)) if !s.is_empty() => {}
            _ => errors.push(format!("field \"{f}\" missing or not a non-empty string")),
        }
    }
    errors
}

pub fn validate_paper_result(json: &[u8]) -> Vec<String> {
    let v: Value = match serde_json::from_slice(json) {
        Ok(v) => v,
        Err(e) => return vec![format!("invalid JSON: {e}")],
    };
    let items = match &v {
        Value::Array(arr) => arr.iter().collect::<Vec<&Value>>(),
        Value::Object(_) => vec![&v],
        _ => return vec!["expected JSON object or array".to_string()],
    };
    for item in &items {
        let errs = string_fields_present(item, &["id", "title"]);
        if !errs.is_empty() {
            return errs;
        }
    }
    Vec::new()
}

pub fn validate_paper_detail(json: &[u8]) -> Vec<String> {
    let v: Value = match serde_json::from_slice(json) {
        Ok(v) => v,
        Err(e) => return vec![format!("invalid JSON: {e}")],
    };
    let obj = match &v {
        Value::Object(o) => o,
        _ => return vec!["expected JSON object".to_string()],
    };
    required_str!(obj, "title");
    required_str!(obj, "abstract");
    required_str!(obj, "venue");
    Vec::new()
}

pub fn validate_author_profile(json: &[u8]) -> Vec<String> {
    let v: Value = match serde_json::from_slice(json) {
        Ok(v) => v,
        Err(e) => return vec![format!("invalid JSON: {e}")],
    };
    let obj = match &v {
        Value::Object(o) => o,
        _ => return vec!["expected JSON object".to_string()],
    };
    required_str!(obj, "name");
    required_num!(obj, "worksCount");
    required_num!(obj, "citedByCount");
    Vec::new()
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cargo build --features cli
```
Expected: builds.

- [ ] **Step 3: Commit**

```bash
git add crates/arxcheck/src/checks/api_contract.rs
git commit -m "feat(arxcheck): API contract validation (WASM target)"
```

---

### Task 7: CLI binary

**Files:**
- Create: `crates/arxcheck/src/bin/arxcheck.rs`

**Interfaces:**
- Produces: CLI binary with exit code 0 (all clear), 1 (errors), 2 (warnings only)

- [ ] **Step 1: Write bin/arxcheck.rs**

```rust
use std::process;
use clap::Parser;
use arxcheck::{checks, Severity};

#[derive(Parser)]
#[command(name = "arxcheck", about = "Validate arxiv-data-explorer JSON data files")]
struct Args {
    /// Path to static/data directory
    #[arg(default_value = "static/data")]
    data_dir: String,

    /// Only run specific check (shard, edges, graph, xref)
    #[arg(long)]
    check: Option<String>,
}

fn main() {
    let args = Args::parse();

    let violations = if let Some(name) = &args.check {
        match name.as_str() {
            "shard" => checks::shard::ShardCheck.run(&args.data_dir),
            "edges" => checks::edges::EdgesCheck.run(&args.data_dir),
            "graph" => checks::graph::GraphCheck.run(&args.data_dir),
            "xref" => checks::xref::CrossRefCheck.run(&args.data_dir),
            _ => {
                eprintln!("Unknown check: {name}. Available: shard, edges, graph, xref");
                process::exit(2);
            }
        }
    } else {
        checks::run_all(&args.data_dir)
    };

    if violations.is_empty() {
        println!("✓ All checks passed");
        process::exit(0);
    }

    let errors: Vec<_> = violations.iter().filter(|v| v.severity == Severity::Error).collect();
    let warnings: Vec<_> = violations.iter().filter(|v| v.severity == Severity::Warning).collect();

    if !errors.is_empty() {
        eprintln!("\nErrors ({}):", errors.len());
        for v in &errors {
            eprintln!("  [{}] {}", v.file, v.message);
        }
    }
    if !warnings.is_empty() {
        eprintln!("\nWarnings ({}):", warnings.len());
        for v in &warnings {
            eprintln!("  [{}] {}", v.file, v.message);
        }
    }

    if !errors.is_empty() {
        process::exit(1);
    }
    process::exit(0);
}
```

- [ ] **Step 2: Verify it compiles and runs**

```bash
cargo build --bin arxcheck
./target/debug/arxcheck --help
```
Expected: help output.

- [ ] **Step 3: Run against actual data**

```bash
./target/debug/arxcheck ../../static/data
```
Expected: runs without crashing.

- [ ] **Step 4: Commit**

```bash
git add crates/arxcheck/src/bin/arxcheck.rs
git commit -m "feat(arxcheck): CLI binary with clap"
```

---

### Task 8: WASM exports

**Files:**
- Create: `crates/arxcheck/src/wasm.rs`

**Interfaces:**
- Produces: `#[wasm_bindgen] pub fn validate_paper_result_json(json: &str) -> JsValue`, `validate_paper_detail_json`, `validate_profile_json`

- [ ] **Step 1: Write wasm.rs**

```rust
use wasm_bindgen::prelude::*;
use crate::checks::api_contract;

#[wasm_bindgen]
pub fn validate_paper_result_json(json: &str) -> JsValue {
    let errors = api_contract::validate_paper_result(json.as_bytes());
    serde_wasm_bindgen::to_value(&errors).unwrap_or(JsValue::UNDEFINED)
}

#[wasm_bindgen]
pub fn validate_paper_detail_json(json: &str) -> JsValue {
    let errors = api_contract::validate_paper_detail(json.as_bytes());
    serde_wasm_bindgen::to_value(&errors).unwrap_or(JsValue::UNDEFINED)
}

#[wasm_bindgen]
pub fn validate_profile_json(json: &str) -> JsValue {
    let errors = api_contract::validate_author_profile(json.as_bytes());
    serde_wasm_bindgen::to_value(&errors).unwrap_or(JsValue::UNDEFINED)
}
```

- [ ] **Step 2: Build WASM binary with wasm-pack**

```bash
wasm-pack build --target web --out-dir ../../static/wasm/arxcheck --release --no-default-features
wasm-opt -Oz ../../static/wasm/arxcheck/arxcheck_bg.wasm -o ../../static/wasm/arxcheck/arxcheck_bg.wasm
```
Expected: builds, WASM binary under 100KB gzipped.

- [ ] **Step 3: Commit**

```bash
git add crates/arxcheck/src/wasm.rs
git commit -m "feat(arxcheck): WASM exports for API contract validation"
```

---

### Task 9: CI integration + SvelteKit runtime wiring

**Files:**
- Modify: `package.json` (prebuild script)
- Modify: `.github/workflows/` (if CI exists) or create CI workflow

- [ ] **Step 1: Add prebuild script to package.json**

```jsonc
// package.json — add to "scripts"
"prebuild": "cargo run --manifest-path crates/arxcheck/Cargo.toml -- static/data"
```

- [ ] **Step 2: Verify prebuild fails on bad data**

```bash
# Temporarily corrupt a shard
echo "not json" > static/data/authors/shard-0.json
npm run prebuild
# Expected: exit code 1 with "invalid JSON"
# Then restore
git checkout static/data/authors/shard-0.json
```

- [ ] **Step 3: Wire runtime validation in db.ts**

```ts
// src/lib/utils/db.ts — add dev-mode validation
import { validatePaperResultJson, validatePaperDetailJson } from "$lib/../static/wasm/arxcheck/arxcheck.js";

let checkerReady = false;
async function initChecker() {
  if (checkerReady) return;
  try {
    const init = (await import("$lib/../static/wasm/arxcheck/arxcheck.js")).default;
    await init();
    checkerReady = true;
  } catch { /* WASM not available in all environments */ }
}

// In searchPapers(), after response parsing:
if (import.meta.env.DEV && checkerReady) {
  const errors = validatePaperResultJson(JSON.stringify(data));
  if (errors.length > 0) console.warn("[arxcheck] PaperResult violations:", errors);
}

// In getPaperDetail(), after response parsing:
if (import.meta.env.DEV && checkerReady) {
  const errors = validatePaperDetailJson(JSON.stringify(data));
  if (errors.length > 0) console.warn("[arxcheck] PaperDetail violations:", errors);
}
```

- [ ] **Step 4: Commit**

```bash
git add package.json src/lib/utils/db.ts
git commit -m "feat(arxcheck): CI prebuild hook + dev-mode runtime API validation"
```
