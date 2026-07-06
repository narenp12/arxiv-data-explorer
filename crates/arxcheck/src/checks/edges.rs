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
