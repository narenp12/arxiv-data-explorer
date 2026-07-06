use crate::{Check, CheckViolation};

pub struct EdgesCheck;

impl Check for EdgesCheck {
    fn name(&self) -> &'static str {
        "edges"
    }
    fn run(&self, _data_dir: &str) -> Vec<CheckViolation> {
        Vec::new()
    }
}
