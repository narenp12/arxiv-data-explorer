use crate::{Check, CheckViolation};
use serde::de::DeserializeOwned;
use std::fs;
use std::path::Path;

#[allow(dead_code)]
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

pub mod api_contract;
pub mod edges;
pub mod graph;
pub mod shard;
pub mod xref;

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
