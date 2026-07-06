use std::collections::HashSet;
use std::fs;
use std::path::Path;
use crate::{Check, CheckViolation};
use serde::Deserialize;

#[derive(Deserialize)]
#[allow(dead_code)]
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
