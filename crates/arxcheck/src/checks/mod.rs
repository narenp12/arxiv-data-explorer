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
