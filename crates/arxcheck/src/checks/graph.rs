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
