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
    let obj = match &v {
        Value::Object(o) => o,
        _ => return vec!["expected JSON object".to_string()],
    };
    match obj.get("title") {
        Some(Value::String(s)) if !s.is_empty() => {}
        _ => return vec!["field \"title\" missing or empty".to_string()],
    }
    match obj.get("abstract") {
        Some(Value::String(s)) if !s.is_empty() => {}
        _ => return vec!["field \"abstract\" missing or empty".to_string()],
    }
    match obj.get("venue") {
        Some(Value::String(s)) if !s.is_empty() => {}
        _ => return vec!["field \"venue\" missing or empty".to_string()],
    }
    Vec::new()
}

pub fn validate_author_profile(json: &[u8]) -> Vec<String> {
    let v: Value = match serde_json::from_slice(json) {
        Ok(v) => v,
        Err(e) => return vec![format!("invalid JSON: {e}")],
    };
    let obj = match &v {
        Value::Object(o) => o,
        _ => return vec!["expected JSON object".to_string()],
    };
    match obj.get("name") {
        Some(Value::String(s)) if !s.is_empty() => {}
        _ => return vec!["field \"name\" missing or empty".to_string()],
    }
    match obj.get("worksCount") {
        Some(Value::Number(_)) => {}
        _ => return vec!["field \"worksCount\" missing or not a number".to_string()],
    }
    match obj.get("citedByCount") {
        Some(Value::Number(_)) => {}
        _ => return vec!["field \"citedByCount\" missing or not a number".to_string()],
    }
    Vec::new()
}
