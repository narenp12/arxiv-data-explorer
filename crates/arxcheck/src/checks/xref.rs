use crate::{Check, CheckViolation};

pub struct CrossRefCheck;

impl Check for CrossRefCheck {
    fn name(&self) -> &'static str {
        "xref"
    }
    fn run(&self, _data_dir: &str) -> Vec<CheckViolation> {
        Vec::new()
    }
}
