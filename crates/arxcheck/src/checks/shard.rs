use crate::{Check, CheckViolation};

pub struct ShardCheck;

impl Check for ShardCheck {
    fn name(&self) -> &'static str {
        "shard"
    }
    fn run(&self, _data_dir: &str) -> Vec<CheckViolation> {
        Vec::new()
    }
}
