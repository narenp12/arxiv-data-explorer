use crate::{Check, CheckViolation};
use serde::Deserialize;
use std::collections::HashSet;
use std::fs;
use std::path::Path;

#[derive(Deserialize)]
#[allow(dead_code)]
struct ShardEntry {
    w: u32,
    co: Vec<(String, serde_json::Value)>,
}

pub struct ShardCheck;

impl Check for ShardCheck {
    fn name(&self) -> &'static str {
        "shard"
    }

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
            if !fname.starts_with("shard-")
                || path.extension().and_then(|s| s.to_str()) != Some("json")
            {
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

#[cfg(test)]
mod tests {
    use super::*;

    use std::io::Write;

    fn write_json(dir: &std::path::Path, name: &str, data: &serde_json::Value) {
        let path = dir.join(name);
        let content = serde_json::to_string(data).unwrap();
        let mut f = std::fs::File::create(&path).unwrap();
        f.write_all(content.as_bytes()).unwrap();
    }

    #[test]
    fn test_valid_shard() {
        let dir =
            std::env::temp_dir().join(format!("arxcheck_test_shard_valid_{}", std::process::id()));
        let authors_dir = dir.join("authors");
        std::fs::create_dir_all(&authors_dir).unwrap();

        write_json(
            &authors_dir,
            "shard-0.json",
            &serde_json::json!({
                "Alice": {"w": 5, "co": [["Bob", {}]]},
                "Bob": {"w": 3, "co": [["Alice", {}]]}
            }),
        );

        let check = ShardCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(
            violations.is_empty(),
            "expected no violations, got: {:?}",
            violations
        );

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_shard_corrupt_json() {
        let dir = std::env::temp_dir().join(format!(
            "arxcheck_test_shard_corrupt_{}",
            std::process::id()
        ));
        let authors_dir = dir.join("authors");
        std::fs::create_dir_all(&authors_dir).unwrap();

        let path = authors_dir.join("shard-0.json");
        let mut f = std::fs::File::create(&path).unwrap();
        f.write_all(b"not valid json").unwrap();

        let check = ShardCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(
            violations
                .iter()
                .any(|v| v.message.contains("invalid JSON"))
        );

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_shard_duplicate_author() {
        let dir =
            std::env::temp_dir().join(format!("arxcheck_test_shard_dup_{}", std::process::id()));
        let authors_dir = dir.join("authors");
        std::fs::create_dir_all(&authors_dir).unwrap();

        write_json(
            &authors_dir,
            "shard-0.json",
            &serde_json::json!({
                "Alice": {"w": 5, "co": []}
            }),
        );
        write_json(
            &authors_dir,
            "shard-1.json",
            &serde_json::json!({
                "Alice": {"w": 3, "co": []}
            }),
        );

        let check = ShardCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(violations.iter().any(|v| v.message.contains("duplicate")));

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_shard_empty_coauthor() {
        let dir = std::env::temp_dir().join(format!(
            "arxcheck_test_shard_empty_co_{}",
            std::process::id()
        ));
        let authors_dir = dir.join("authors");
        std::fs::create_dir_all(&authors_dir).unwrap();

        write_json(
            &authors_dir,
            "shard-0.json",
            &serde_json::json!({
                "Alice": {"w": 5, "co": [["", {}]]}
            }),
        );

        let check = ShardCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(
            violations
                .iter()
                .any(|v| v.message.contains("empty co-author"))
        );

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_shard_missing_authors_dir() {
        let dir = std::env::temp_dir().join(format!(
            "arxcheck_test_shard_missing_dir_{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        let check = ShardCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(
            violations
                .iter()
                .any(|v| v.message.contains("cannot read directory"))
        );

        std::fs::remove_dir_all(&dir).unwrap();
    }
}
