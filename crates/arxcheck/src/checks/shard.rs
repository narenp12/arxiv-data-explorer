use std::fs;
use std::collections::HashSet;
use std::path::Path;
use crate::{Check, CheckViolation};
use serde::Deserialize;

#[derive(Deserialize)]
#[allow(dead_code)]
struct ShardEntry {
    w: u32,
    co: Vec<(String, serde_json::Value)>,
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
            let fname = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
            if !fname.starts_with("shard-") || path.extension().and_then(|s| s.to_str()) != Some("json") {
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
                        if entry.co.iter().any(|c| c.0.is_empty()) {
                            violations.push(CheckViolation::error(
                                path.display().to_string(),
                                format!("author \"{name}\" has empty co-author name"),
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
