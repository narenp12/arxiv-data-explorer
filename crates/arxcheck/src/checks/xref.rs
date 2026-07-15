use super::read_json_file;
use crate::{Check, CheckViolation};
use serde::Deserialize;
use std::collections::HashSet;
use std::fs;
use std::path::Path;

#[derive(Deserialize)]
#[allow(dead_code)]
struct RankingEntry {
    name: String,
    papers: u32,
    relative: u32,
}

pub struct CrossRefCheck;

impl Check for CrossRefCheck {
    fn name(&self) -> &'static str {
        "cross_ref"
    }

    fn run(&self, data_dir: &str) -> Vec<CheckViolation> {
        let mut violations = Vec::new();
        let path = Path::new(data_dir).join("author_rankings.json");

        let rankings: Vec<RankingEntry> = match read_json_file(&path, &mut violations) {
            Some(r) => r,
            None => return violations,
        };

        let shards_dir = Path::new(data_dir).join("authors");
        let mut shard_names: HashSet<String> = HashSet::new();
        if let Ok(entries) = fs::read_dir(&shards_dir) {
            for entry in entries.flatten() {
                let p = entry.path();
                if p.extension().and_then(|s| s.to_str()) != Some("json") {
                    continue;
                }
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
                    format!(
                        "author \"{}\" has relative {} > 100",
                        entry.name, entry.relative
                    ),
                ));
            }
        }

        violations
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    use std::assert_matches;
    use std::io::Write;

    fn write_json(dir: &std::path::Path, name: &str, data: &serde_json::Value) {
        let path = dir.join(name);
        let content = serde_json::to_string(data).unwrap();
        let mut f = std::fs::File::create(&path).unwrap();
        f.write_all(content.as_bytes()).unwrap();
    }

    #[test]
    fn test_valid_cross_ref() {
        let dir =
            std::env::temp_dir().join(format!("arxcheck_test_xref_valid_{}", std::process::id()));
        let authors_dir = dir.join("authors");
        std::fs::create_dir_all(&authors_dir).unwrap();

        write_json(
            &dir,
            "author_rankings.json",
            &serde_json::json!([
                {"name": "Alice", "papers": 10, "relative": 50}
            ]),
        );
        write_json(
            &authors_dir,
            "shard-0.json",
            &serde_json::json!({
                "Alice": {"w": 5, "co": []}
            }),
        );

        let check = CrossRefCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(
            violations.is_empty(),
            "expected no violations, got: {:?}",
            violations
        );

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_xref_missing_author_in_shard() {
        let dir = std::env::temp_dir().join(format!(
            "arxcheck_test_xref_missing_auth_{}",
            std::process::id()
        ));
        let authors_dir = dir.join("authors");
        std::fs::create_dir_all(&authors_dir).unwrap();

        write_json(
            &dir,
            "author_rankings.json",
            &serde_json::json!([
                {"name": "Alice", "papers": 10, "relative": 50},
                {"name": "Unknown", "papers": 5, "relative": 20}
            ]),
        );
        write_json(
            &authors_dir,
            "shard-0.json",
            &serde_json::json!({
                "Alice": {"w": 5, "co": []}
            }),
        );

        let check = CrossRefCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert_matches!(
            violations.iter().find(|v| v.message.contains("not found in any shard")),
            Some(_)
        );

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_xref_relative_gt_100() {
        let dir =
            std::env::temp_dir().join(format!("arxcheck_test_xref_rel_{}", std::process::id()));
        let authors_dir = dir.join("authors");
        std::fs::create_dir_all(&authors_dir).unwrap();

        write_json(
            &dir,
            "author_rankings.json",
            &serde_json::json!([
                {"name": "Alice", "papers": 10, "relative": 150}
            ]),
        );
        write_json(
            &authors_dir,
            "shard-0.json",
            &serde_json::json!({
                "Alice": {"w": 5, "co": []}
            }),
        );

        let check = CrossRefCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert_matches!(
            violations.iter().find(|v| v.message.contains("relative") && v.message.contains("> 100")),
            Some(_)
        );

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_xref_missing_author_rankings() {
        let dir = std::env::temp_dir().join(format!(
            "arxcheck_test_xref_missing_file_{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        let check = CrossRefCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert_eq!(violations.len(), 1, "expected 1 violation for missing file");

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_xref_both_warnings() {
        let dir =
            std::env::temp_dir().join(format!("arxcheck_test_xref_both_{}", std::process::id()));
        let authors_dir = dir.join("authors");
        std::fs::create_dir_all(&authors_dir).unwrap();

        write_json(
            &dir,
            "author_rankings.json",
            &serde_json::json!([
                {"name": "Unknown", "papers": 5, "relative": 200}
            ]),
        );
        write_json(
            &authors_dir,
            "shard-0.json",
            &serde_json::json!({
                "Alice": {"w": 5, "co": []}
            }),
        );

        let check = CrossRefCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert_eq!(violations.len(), 2, "expected 2 violations");

        std::fs::remove_dir_all(&dir).unwrap();
    }
}
