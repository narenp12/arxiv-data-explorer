use crate::{Check, CheckViolation};
use serde::Deserialize;
use std::collections::HashSet;
use std::fs;
use std::path::Path;

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
    fn name(&self) -> &'static str {
        "graph"
    }

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
    fn test_valid_graph() {
        let dir =
            std::env::temp_dir().join(format!("arxcheck_test_graph_valid_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();

        write_json(
            &dir,
            "category_graph.json",
            &serde_json::json!({
                "nodes": [{"id": "cs.AI"}, {"id": "cs.LG"}],
                "edges": [{"source": "cs.AI", "target": "cs.LG"}]
            }),
        );

        let check = GraphCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(
            violations.is_empty(),
            "expected no violations, got: {:?}",
            violations
        );

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_graph_empty_node_id() {
        let dir = std::env::temp_dir().join(format!(
            "arxcheck_test_graph_empty_node_{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        write_json(
            &dir,
            "category_graph.json",
            &serde_json::json!({
                "nodes": [{"id": ""}, {"id": "cs.LG"}],
                "edges": [{"source": "", "target": "cs.LG"}]
            }),
        );

        let check = GraphCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(violations.iter().any(|v| v.message.contains("empty id")));

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_graph_duplicate_edges() {
        let dir = std::env::temp_dir().join(format!(
            "arxcheck_test_graph_dup_edge_{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        write_json(
            &dir,
            "category_graph.json",
            &serde_json::json!({
                "nodes": [{"id": "cs.AI"}, {"id": "cs.LG"}],
                "edges": [
                    {"source": "cs.AI", "target": "cs.LG"},
                    {"source": "cs.AI", "target": "cs.LG"}
                ]
            }),
        );

        let check = GraphCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(violations.iter().any(|v| v.message.contains("duplicate")));

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_graph_missing_edge_target() {
        let dir = std::env::temp_dir().join(format!(
            "arxcheck_test_graph_missing_target_{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        write_json(
            &dir,
            "category_graph.json",
            &serde_json::json!({
                "nodes": [{"id": "cs.AI"}],
                "edges": [{"source": "cs.AI", "target": "MISSING"}]
            }),
        );

        let check = GraphCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert!(violations.iter().any(|v| v.message.contains("not found")));

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn test_graph_missing_file() {
        let dir = std::env::temp_dir().join(format!(
            "arxcheck_test_graph_missing_file_{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        let check = GraphCheck;
        let violations = check.run(dir.to_str().unwrap());
        assert_eq!(violations.len(), 1, "expected 1 violation for missing file");
        assert!(violations[0].message.contains("cannot read"));

        std::fs::remove_dir_all(&dir).unwrap();
    }
}
