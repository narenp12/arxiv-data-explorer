use crate::{Check, CheckViolation};

pub struct GraphCheck;

impl Check for GraphCheck {
    fn name(&self) -> &'static str {
        "graph"
    }
    fn run(&self, _data_dir: &str) -> Vec<CheckViolation> {
        Vec::new()
    }
}
