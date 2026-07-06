pub mod checks;
#[cfg(target_arch = "wasm32")]
pub mod wasm;

#[derive(Debug, Clone, PartialEq)]
pub enum Severity {
    Error,
    Warning,
}

#[derive(Debug, Clone)]
pub struct CheckViolation {
    pub file: String,
    pub severity: Severity,
    pub message: String,
}

impl CheckViolation {
    pub fn error(file: impl Into<String>, message: impl Into<String>) -> Self {
        Self { file: file.into(), severity: Severity::Error, message: message.into() }
    }
    pub fn warning(file: impl Into<String>, message: impl Into<String>) -> Self {
        Self { file: file.into(), severity: Severity::Warning, message: message.into() }
    }
}

pub trait Check {
    fn name(&self) -> &'static str;
    fn run(&self, data_dir: &str) -> Vec<CheckViolation>;
}
