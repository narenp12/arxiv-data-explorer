use crate::checks::api_contract;
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn validate_paper_result_json(json: &str) -> JsValue {
    let errors = api_contract::validate_paper_result(json.as_bytes());
    serde_wasm_bindgen::to_value(&errors).unwrap_or(JsValue::UNDEFINED)
}

#[wasm_bindgen]
pub fn validate_paper_detail_json(json: &str) -> JsValue {
    let errors = api_contract::validate_paper_detail(json.as_bytes());
    serde_wasm_bindgen::to_value(&errors).unwrap_or(JsValue::UNDEFINED)
}

#[wasm_bindgen]
pub fn validate_profile_json(json: &str) -> JsValue {
    let errors = api_contract::validate_author_profile(json.as_bytes());
    serde_wasm_bindgen::to_value(&errors).unwrap_or(JsValue::UNDEFINED)
}
