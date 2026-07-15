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
#[allow(dead_code)]
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
    fn test_valid_edges() {
        let dir = std::env::temp_dir().join(format!("arxcheck_test_edges_valid_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();

        write_json(&dir, "causal_edges.json", &serde_json::json!({
            "edges": [{"source": "cs.AI", "target": "cs.LG", "weight": 0.5, "ci_lower": 0.1, "ci_upper": 0.9, "prob": 0.8}],
            "categories": [{"id": "cs.AI"}]
        }));
        write_json(&dir, "category_dynamics.json", &serde_json::json!({
            "series": { "cs.AI": [10, 20], "cs.LG": [5, 15] }
        }));

        let check = EdgesCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(violations.is_empty(), "expected no violations, got: {:?}", violations);

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_edges_missing_source() {
        let dir = std::env::temp_dir().join(format!("arxcheck_test_edges_missing_source_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();

        write_json(&dir, "causal_edges.json", &serde_json::json!({
            "edges": [{"source": "MISSING", "target": "cs.LG", "weight": 0.5, "ci_lower": 0.1, "ci_upper": 0.9, "prob": 0.8}],
            "categories": []
        }));
        write_json(&dir, "category_dynamics.json", &serde_json::json!({
            "series": { "cs.LG": [5, 15] }
        }));

        let check = EdgesCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(!violations.is_empty(), "expected violations but got none");
        assert!(violations.iter().any(|v| v.message.contains("source")));

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_edges_missing_both_files() {
        let dir = std::env::temp_dir().join(format!("arxcheck_test_edges_missing_files_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();

        let check = EdgesCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert_eq!(violations.len(), 1, "expected 1 violation for missing file (early return)");

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_edges_bad_ci_range() {
        let dir = std::env::temp_dir().join(format!("arxcheck_test_edges_bad_ci_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();

        write_json(&dir, "causal_edges.json", &serde_json::json!({
            "edges": [{"source": "cs.AI", "target": "cs.LG", "weight": 0.5, "ci_lower": 0.9, "ci_upper": 0.1, "prob": 0.8}],
            "categories": [{"id": "cs.AI"}]
        }));
        write_json(&dir, "category_dynamics.json", &serde_json::json!({
            "series": { "cs.AI": [10, 20], "cs.LG": [5, 15] }
        }));

        let check = EdgesCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(violations.iter().any(|v| v.message.contains("ci_lower")), "expected ci range warning");

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_edges_bad_prob() {
        let dir = std::env::temp_dir().join(format!("arxcheck_test_edges_bad_prob_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();

        write_json(&dir, "causal_edges.json", &serde_json::json!({
            "edges": [{"source": "cs.AI", "target": "cs.LG", "weight": 0.5, "ci_lower": 0.1, "ci_upper": 0.9, "prob": 0.3}],
            "categories": []
        }));
        write_json(&dir, "category_dynamics.json", &serde_json::json!({
            "series": { "cs.AI": [10, 20], "cs.LG": [5, 15] }
        }));

        let check = EdgesCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(violations.iter().any(|v| v.message.contains("prob")), "expected prob warning");

        std::fs::remove_dir_all(&dir).unwrap();
    }
}
