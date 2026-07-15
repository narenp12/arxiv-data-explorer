// Target-agnostic: operates on &[u8], no wasm-bindgen here.
use serde_json::Value;

fn string_fields_present(obj: &Value, fields: &[&str]) -> Vec<String> {
    let mut errors = Vec::new();
    for f in fields {
        match obj.get(f) {
            Some(Value::String(s)) if !s.is_empty() => {}
            _ => errors.push(format!("field \"{f}\" missing or not a non-empty string")),
        }
    }
    errors
}

fn require_string_field(obj: &Value, field: &str) -> Result<(), String> {
    match obj.get(field) {
        Some(Value::String(s)) if !s.is_empty() => Ok(()),
        _ => Err(format!("field \"{field}\" missing or empty")),
    }
}

fn require_number_field(obj: &Value, field: &str) -> Result<(), String> {
    match obj.get(field) {
        Some(Value::Number(_)) => Ok(()),
        _ => Err(format!("field \"{field}\" missing or not a number")),
    }
}

pub fn validate_paper_result(json: &[u8]) -> Vec<String> {
    let v: Value = match serde_json::from_slice(json) {
        Ok(v) => v,
        Err(e) => return vec![format!("invalid JSON: {e}")],
    };
    let items = match &v {
        Value::Array(arr) => arr.iter().collect::<Vec<&Value>>(),
        Value::Object(_) => vec![&v],
        _ => return vec!["expected JSON object or array".to_string()],
    };
    for item in &items {
        let errs = string_fields_present(item, &["id", "title"]);
        if !errs.is_empty() {
            return errs;
        }
    }
    Vec::new()
}

pub fn validate_paper_detail(json: &[u8]) -> Vec<String> {
    let v: Value = match serde_json::from_slice(json) {
        Ok(v) => v,
        Err(e) => return vec![format!("invalid JSON: {e}")],
    };
    if !v.is_object() {
        return vec!["expected JSON object".to_string()];
    }
    for field in ["title", "abstract", "venue"] {
        if let Err(e) = require_string_field(&v, field) {
            return vec![e];
        }
    }
    Vec::new()
}

pub fn validate_author_profile(json: &[u8]) -> Vec<String> {
    let v: Value = match serde_json::from_slice(json) {
        Ok(v) => v,
        Err(e) => return vec![format!("invalid JSON: {e}")],
    };
    if !v.is_object() {
        return vec!["expected JSON object".to_string()];
    }
    if let Err(e) = require_string_field(&v, "name") {
        return vec![e];
    }
    if let Err(e) = require_number_field(&v, "worksCount") {
        return vec![e];
    }
    if let Err(e) = require_number_field(&v, "citedByCount") {
        return vec![e];
    }
    Vec::new()
}
