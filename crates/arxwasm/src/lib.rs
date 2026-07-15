mod data;
mod normalize;
mod ranker;
mod trie;
mod trigram;

use data::AuthorStore;
use normalize::{normalize, normalize_for_search};
use std::sync::OnceLock;
use trie::AuthorTrie;
use trigram::TrigramIndex;
use wasm_bindgen::prelude::*;

static STORE: OnceLock<AppState> = OnceLock::new();

struct AppState {
    store: AuthorStore,
    trie: AuthorTrie,
    trigram: TrigramIndex,
}

#[wasm_bindgen]
pub fn init(shards_json: &str, rankings_json: &str) -> Result<(), JsValue> {
    let store = match AuthorStore::from_shards(shards_json, rankings_json) {
        Ok(s) => s,
        Err(e) => {
            return Err(JsValue::from_str(&format!("from_shards failed: {}", e)));
        }
    };

    let mut trie = AuthorTrie::new();
    let mut trigram = TrigramIndex::new();

    for (i, author) in store.authors.iter().enumerate() {
        let n = normalize(&author.name);
        trie.insert(&n, i);
        trigram.insert(&n, i);
    }

    STORE
        .set(AppState {
            store,
            trie,
            trigram,
        })
        .map_err(|_| JsValue::from_str("init already called"))
}

#[wasm_bindgen]
pub fn search(query: &str, max_results: u32) -> JsValue {
    let Some(state) = STORE.get() else {
        return JsValue::UNDEFINED;
    };

    let q = normalize_for_search(query);
    if q.is_empty() {
        return serde_wasm_bindgen::to_value(&[] as &[serde_json::Value])
            .unwrap_or(JsValue::UNDEFINED);
    }

    let mut candidates = state.trie.search(&q);
    let exact_empty = candidates.is_empty();

    if exact_empty {
        let fuzzy = state.trigram.search(&q);
        candidates = fuzzy.into_iter().map(|(idx, _)| idx).collect();
    }

    let ranked = ranker::rank_candidates(&state.store.authors, &candidates, &q);

    let max = max_results as usize;
    let results: Vec<serde_json::Value> = ranked
        .into_iter()
        .take(max)
        .map(|idx| {
            let a = &state.store.authors[idx];
            serde_json::json!({
                "name": a.name,
                "weight": a.weight,
                "coauthors": a.coauthors.len(),
                "rank": a.rank,
            })
        })
        .collect();

    serde_wasm_bindgen::to_value(&results).unwrap_or(JsValue::UNDEFINED)
}

#[wasm_bindgen]
pub fn search_stats() -> JsValue {
    let Some(state) = STORE.get() else {
        return JsValue::UNDEFINED;
    };
    let total = state.store.authors.len();
    let with_ranks = state
        .store
        .authors
        .iter()
        .filter(|a| a.rank.is_some())
        .count();
    serde_wasm_bindgen::to_value(&serde_json::json!({
        "total_authors": total,
        "with_rankings": with_ranks,
    }))
    .unwrap_or(JsValue::UNDEFINED)
}
