mod data;
mod normalize;
mod trie;
mod trigram;
mod ranker;

use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn init(shards_json: &str, rankings_json: &str) -> Result<(), JsValue> {
    let _store = data::AuthorStore::from_shards(shards_json, rankings_json);
    Ok(())
}
