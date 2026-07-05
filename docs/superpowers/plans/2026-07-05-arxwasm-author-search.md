# arxwasm — WASM Author Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace server-side author lookup with client-side full-text search across 25K+ authors, powered by a Rust → WASM prefix trie with fuzzy fallback.

**Architecture:** A single `crates/arxwasm/` Rust crate compiled with `wasm-pack` to WebAssembly. The WASM module exposes three JS-callable functions: `init(data_json)`, `search(query, max_results)`, and `search_stats()`. The SvelteKit frontend loads the WASM binary and feeds it all author shards on mount.

**Tech Stack:** Rust, wasm-bindgen, serde_json, wasm-pack

## Global Constraints

- No `std` feature dependencies that don't compile to `wasm32-unknown-unknown`
- WASM binary must stay under 200KB gzipped
- All author shards are fed as a single JSON string (not individually)
- The crate must not depend on `regex` or heavy parser libraries

---

## File Structure

```
crates/arxwasm/
├── Cargo.toml
└── src/
    ├── lib.rs          — wasm-bindgen exports (init, search, search_stats)
    ├── normalize.rs    — name normalization (lowercase, strip punctuation, NFKC)
    ├── trie.rs         — prefix trie for exact-match lookup
    ├── trigram.rs      — trigram index for fuzzy/typo-tolerant search
    ├── ranker.rs       — score & rank candidates by weight × co-count × ranking
    └── data.rs         — in-memory author store (deserialized from JSON)

src/lib/authors/
└── wasm-search.ts     — SvelteKit glue: load WASM, call init, expose search
```

---

### Task 1: Cargo project scaffolding

**Files:**
- Create: `crates/arxwasm/Cargo.toml`
- Create: `crates/arxwasm/src/lib.rs` (minimal)
- Create: `crates/arxwasm/src/data.rs`

**Interfaces:**
- Consumes: nothing
- Produces: `data::Author { name: String, weight: u32, coauthors: Vec<String>, rank: Option<u32> }`, `data::AuthorStore { authors: Vec<Author> }`

- [ ] **Step 1: Write Cargo.toml**

```toml
[package]
name = "arxwasm"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]

[dependencies]
wasm-bindgen = "0.2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"

[profile.release]
opt-level = "s"
lto = true
```

- [ ] **Step 2: Write minimal data.rs**

```rust
use serde::Deserialize;

#[derive(Clone, Debug)]
pub struct Author {
    pub name: String,
    pub weight: u32,
    pub coauthors: Vec<String>,
    pub rank: Option<u32>,
}

#[derive(Clone, Debug, Default)]
pub struct AuthorStore {
    pub authors: Vec<Author>,
}

/// Raw shard entry as deserialized from JSON.
#[derive(Deserialize)]
struct RawShardEntry {
    w: u32,
    co: Vec<[String; 2]>,
}

type RawShard = std::collections::HashMap<String, RawShardEntry>;

impl AuthorStore {
    pub fn from_shards(shards_json: &[(&str, &str)], rankings: &[u8]) -> Self {
        // rankings_json: [{name, papers, relative}]
        // Build a map of name → rank
        let mut store = AuthorStore::default();

        for (_filename, json_bytes) in shards_json {
            let shard: RawShard = serde_json::from_slice(json_bytes.as_bytes()).expect("valid shard JSON");
            for (name, entry) in shard {
                store.authors.push(Author {
                    name: name.clone(),
                    weight: entry.w,
                    coauthors: entry.co.iter().map(|c| c[0].clone()).collect(),
                    rank: None, // filled below
                });
            }
        }

        // Fill ranks from rankings.json
        let rankings: Vec<serde_json::Value> = serde_json::from_slice(rankings).unwrap_or_default();
        let name_to_rank: std::collections::HashMap<&str, u32> = rankings
            .iter()
            .enumerate()
            .map(|(i, v)| (v["name"].as_str().unwrap_or(""), i as u32))
            .collect();
        for author in &mut store.authors {
            author.rank = name_to_rank.get(author.name.as_str()).copied();
        }

        store
    }
}
```

- [ ] **Step 3: Write minimal lib.rs**

```rust
mod data;
mod normalize;
mod trie;
mod trigram;
mod ranker;

use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn init(shards_json: &str, rankings_json: &str) -> Result<(), JsValue> {
    // Store globally for search
    Ok(())
}
```

- [ ] **Step 4: Verify it compiles**

Run:
```bash
cd crates/arxwasm
cargo build --target wasm32-unknown-unknown
```
Expected: builds without errors.

- [ ] **Step 5: Commit**

```bash
git add crates/arxwasm/
git commit -m "feat(arxwasm): scaffold crate layout with data types"
```

---

### Task 2: Name normalizer

**Files:**
- Create: `crates/arxwasm/src/normalize.rs`

**Interfaces:**
- Produces: `normalize::normalize(name: &str) -> String`, `normalize::normalize_for_search(query: &str) -> String`

- [ ] **Step 1: Write normalize.rs**

```rust
/// Strip punctuation, lowercase, normalize Unicode.
pub fn normalize(name: &str) -> String {
    name.chars()
        .map(|c| match c {
            c if c.is_ascii_alphanumeric() || c.is_whitespace() => c.to_ascii_lowercase(),
            '.' | ',' | '-' | '\'' | '(' | ')' => ' ',
            _ => c.to_ascii_lowercase(),
        })
        .collect::<String>()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

/// Normalize a search query — same as normalize but trims aggressively.
pub fn normalize_for_search(query: &str) -> String {
    normalize(query.trim())
}
```

- [ ] **Step 2: Add unit tests to normalize.rs**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strips_punctuation() {
        assert_eq!(normalize("C. Chen"), "c chen");
    }

    #[test]
    fn lowercases() {
        assert_eq!(normalize("Wei Wang"), "wei wang");
    }

    #[test]
    fn collapses_whitespace() {
        assert_eq!(normalize("  Zhang   Wei  "), "zhang wei");
    }
}
```

- [ ] **Step 3: Run tests**

```bash
cargo test
```
Expected: all 3 pass.

- [ ] **Step 4: Commit**

```bash
git add crates/arxwasm/src/normalize.rs
git commit -m "feat(arxwasm): add name normalizer"
```

---

### Task 3: Prefix trie

**Files:**
- Create: `crates/arxwasm/src/trie.rs`

**Interfaces:**
- Produces: `trie::AuthorTrie::new()`, `trie::AuthorTrie::insert(name, idx)`, `trie::AuthorTrie::search(prefix) -> Vec<usize>`

- [ ] **Step 1: Write trie.rs**

```rust
use std::collections::HashMap;

#[derive(Default)]
struct TrieNode {
    children: HashMap<char, TrieNode>,
    author_indices: Vec<usize>,
}

#[derive(Default)]
pub struct AuthorTrie {
    root: TrieNode,
}

impl AuthorTrie {
    pub fn new() -> Self {
        Self::default()
    }

    /// Insert a normalized author name linked to its index in AuthorStore.
    pub fn insert(&mut self, normalized: &str, author_idx: usize) {
        let mut node = &mut self.root;
        for ch in normalized.chars() {
            node = node.children.entry(ch).or_default();
        }
        node.author_indices.push(author_idx);
    }

    /// Find all author indices whose normalized name starts with `prefix`.
    pub fn search(&self, prefix: &str) -> Vec<usize> {
        let mut node = &self.root;
        for ch in prefix.chars() {
            match node.children.get(&ch) {
                Some(child) => node = child,
                None => return Vec::new(),
            }
        }
        let mut results = Vec::new();
        collect_all(&node, &mut results);
        results
    }
}

fn collect_all(node: &TrieNode, out: &mut Vec<usize>) {
    out.extend_from_slice(&node.author_indices);
    for child in node.children.values() {
        collect_all(child, out);
    }
}
```

- [ ] **Step 2: Add tests**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exact_prefix_match() {
        let mut trie = AuthorTrie::new();
        trie.insert("c chen", 0);
        trie.insert("wei wang", 1);
        let r = trie.search("c chen");
        assert_eq!(r, vec![0]);
    }

    #[test]
    fn prefix_returns_multiple() {
        let mut trie = AuthorTrie::new();
        trie.insert("wei", 0);
        trie.insert("wei wang", 1);
        trie.insert("wei zhang", 2);
        let r = trie.search("wei");
        assert_eq!(r.len(), 3);
    }

    #[test]
    fn no_match_returns_empty() {
        let trie = AuthorTrie::new();
        let r = trie.search("nonexistent");
        assert!(r.is_empty());
    }
}
```

- [ ] **Step 3: Run tests**

```bash
cargo test
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add crates/arxwasm/src/trie.rs
git commit -m "feat(arxwasm): add prefix trie for exact author name matches"
```

---

### Task 4: Trigram fuzzy index

**Files:**
- Create: `crates/arxwasm/src/trigram.rs`

**Interfaces:**
- Produces: `trigram::TrigramIndex::new()`, `trigram::TrigramIndex::insert(normalized, idx)`, `trigram::TrigramIndex::search(query, max_edit_dist) -> Vec<(usize, f64)>`

- [ ] **Step 1: Write trigram.rs**

```rust
use std::collections::HashMap;

fn trigrams(s: &str) -> Vec<String> {
    let padded = format!("  {s} ");
    padded
        .chars()
        .collect::<Vec<_>>()
        .windows(3)
        .map(|w| w.iter().collect())
        .collect()
}

#[derive(Default)]
pub struct TrigramIndex {
    // trigram → list of (author_index, trigram_count_for_that_name)
    posting: HashMap<String, Vec<(usize, u32)>>,
}

impl TrigramIndex {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn insert(&mut self, normalized: &str, author_idx: usize) {
        let grams = trigrams(normalized);
        let total = grams.len() as u32;
        for g in &grams {
            self.posting.entry(g.clone()).or_default().push((author_idx, total));
        }
    }

    /// Returns (author_idx, similarity) sorted by similarity descending.
    /// similarity = 2 * |intersection| / (|qgrams| + |docgrams|)
    pub fn search(&self, query: &str) -> Vec<(usize, f64)> {
        let qgrams = trigrams(query);
        if qgrams.is_empty() {
            return Vec::new();
        }
        let qtotal = qgrams.len() as f64;

        let mut scores: HashMap<usize, (u32, u32)> = HashMap::new(); // idx → (match_count, doctotal)
        for g in &qgrams {
            if let Some(entries) = self.posting.get(g) {
                for &(idx, doctotal) in entries {
                    let entry = scores.entry(idx).or_insert((0, doctotal));
                    entry.0 += 1;
                }
            }
        }

        let mut results: Vec<(usize, f64)> = scores
            .into_iter()
            .map(|(idx, (matches, doctotal))| {
                let sim = 2.0 * matches as f64 / (qtotal + doctotal as f64);
                (idx, sim)
            })
            .filter(|(_, sim)| *sim > 0.3)
            .collect();
        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        results.truncate(20);
        results
    }
}
```

- [ ] **Step 2: Add tests**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trigram_generation() {
        let grams = trigrams("chen");
        assert!(grams.contains(&" che".to_string()));
        assert!(grams.contains(&"hen ".to_string()));
    }

    #[test]
    fn fuzzy_match() {
        let mut idx = TrigramIndex::new();
        idx.insert("chen", 0);
        // Typo: "chn" should still match "chen"
        let r = idx.search("chn");
        assert!(!r.is_empty());
        assert_eq!(r[0].0, 0);
    }

    #[test]
    fn no_match() {
        let idx = TrigramIndex::new();
        let r = idx.search("xyzabc");
        assert!(r.is_empty());
    }
}
```

- [ ] **Step 3: Run tests**

```bash
cargo test
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add crates/arxwasm/src/trigram.rs
git commit -m "feat(arxwasm): add trigram fuzzy index for typo-tolerant search"
```

---

### Task 5: Ranker

**Files:**
- Create: `crates/arxwasm/src/ranker.rs`

**Interfaces:**
- Produces: `ranker::rank_candidates(authors: &[Author], indices: &[usize], query: &str) -> Vec<usize>`

- [ ] **Step 1: Write ranker.rs**

```rust
use crate::data::Author;

/// Score candidates: exact prefix > fuzzy; within tier, weight × co-count × rank.
pub fn rank_candidates(authors: &[Author], indices: &[usize], query: &str) -> Vec<usize> {
    let query_lower = query.to_ascii_lowercase();
    let mut scored: Vec<(usize, f64, u32, u32, Option<u32>)> = indices
        .iter()
        .map(|&idx| {
            let author = &authors[idx];
            let name_lower = author.name.to_ascii_lowercase();
            let exact_bonus = if name_lower.starts_with(&query_lower) { 1000.0 } else { 0.0 };
            let score = exact_bonus + author.weight as f64 * (1.0 + author.coauthors.len() as f64);
            (idx, score, author.weight, author.coauthors.len() as u32, author.rank)
        })
        .collect();

    scored.sort_by(|a, b| {
        b.1.partial_cmp(&a.1)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    scored.into_iter().map(|(idx, _, _, _, _)| idx).collect()
}
```

- [ ] **Step 2: Add tests**

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::Author;

    fn make_author(name: &str, weight: u32, co_count: u32) -> Author {
        Author {
            name: name.to_string(),
            weight,
            coauthors: (0..co_count).map(|i| format!("co{i}")).collect(),
            rank: None,
        }
    }

    #[test]
    fn exact_prefix_ranks_higher() {
        let authors = vec![
            make_author("Wei Wang", 100, 0),
            make_author("C. Chen", 200, 5),
        ];
        let r = rank_candidates(&authors, &[0, 1], "wei");
        assert_eq!(r[0], 0);
    }

    #[test]
    fn higher_weight_ranks_higher_within_tier() {
        let authors = vec![
            make_author("C. Chen", 50, 0),
            make_author("Chao Chen", 200, 0),
        ];
        let r = rank_candidates(&authors, &[0, 1], "chen");
        assert_eq!(r[0], 1); // Chao Chen has higher weight
    }
}
```

- [ ] **Step 3: Run tests**

```bash
cargo test
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add crates/arxwasm/src/ranker.rs
git commit -m "feat(arxwasm): add result ranker (exact prefix bonus + weight)"
```

---

### Task 6: Wire everything — full lib.rs with wasm-bindgen exports

**Files:**
- Modify: `crates/arxwasm/src/lib.rs`

**Interfaces:**
- Produces: `#[wasm_bindgen] pub fn init(shards_json: &str, rankings_json: &str)`, `#[wasm_bindgen] pub fn search(query: &str, max_results: u32) -> JsValue`, `#[wasm_bindgen] pub fn search_stats() -> JsValue`

- [ ] **Step 1: Write lib.rs**

```rust
mod data;
mod normalize;
mod trie;
mod trigram;
mod ranker;

use data::AuthorStore;
use normalize::{normalize, normalize_for_search};
use trie::AuthorTrie;
use trigram::TrigramIndex;
use wasm_bindgen::prelude::*;

static mut STORE: Option<AppState> = None;

struct AppState {
    store: AuthorStore,
    trie: AuthorTrie,
    trigram: TrigramIndex,
}

#[wasm_bindgen]
pub fn init(shards_json: &str, rankings_json: &str) -> Result<(), JsValue> {
    let store = AuthorStore::from_shards(shards_json, rankings_json.as_bytes());

    let mut trie = AuthorTrie::new();
    let mut trigram = TrigramIndex::new();

    for (i, author) in store.authors.iter().enumerate() {
        let n = normalize(&author.name);
        trie.insert(&n, i);
        trigram.insert(&n, i);
    }

    unsafe {
        STORE = Some(AppState { store, trie, trigram });
    }
    Ok(())
}

#[wasm_bindgen]
pub fn search(query: &str, max_results: u32) -> JsValue {
    let state = unsafe { STORE.as_ref() };
    let state = match state {
        Some(s) => s,
        None => return JsValue::UNDEFINED,
    };

    let q = normalize_for_search(query);
    if q.is_empty() {
        return serde_wasm_bindgen::to_value(&[] as &[serde_json::Value]).unwrap_or(JsValue::UNDEFINED);
    }

    // 1. Exact prefix search
    let mut candidates = state.trie.search(&q);
    let exact_empty = candidates.is_empty();

    // 2. If nothing, fall back to fuzzy
    if exact_empty {
        let fuzzy = state.trigram.search(&q);
        candidates = fuzzy.into_iter().map(|(idx, _)| idx).collect();
    }

    // 3. Rank
    let ranked = ranker::rank_candidates(&state.store.authors, &candidates, &q);

    // 4. Serialize top-N
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
    let state = unsafe { STORE.as_ref() };
    let state = match state {
        Some(s) => s,
        None => return JsValue::UNDEFINED,
    };
    let total = state.store.authors.len();
    let with_ranks = state.store.authors.iter().filter(|a| a.rank.is_some()).count();
    serde_wasm_bindgen::to_value(&serde_json::json!({
        "total_authors": total,
        "with_rankings": with_ranks,
    }))
    .unwrap_or(JsValue::UNDEFINED)
}
```

Add `serde-wasm-bindgen` to Cargo.toml:

```toml
serde-wasm-bindgen = "0.6"
```

- [ ] **Step 2: Build for wasm32 target**

```bash
cargo build --target wasm32-unknown-unknown
```
Expected: compiles without errors.

- [ ] **Step 3: Run native tests**

```bash
cargo test
```
Expected: all previous tests still pass.

- [ ] **Step 4: Commit**

```bash
git add crates/arxwasm/Cargo.toml crates/arxwasm/src/lib.rs
git commit -m "feat(arxwasm): wire init/search/search_stats wasm exports"
```

---

### Task 7: SvelteKit integration — WASM loader + search component

**Files:**
- Create: `src/lib/authors/wasm-search.ts`
- Create: `src/lib/authors/AuthorSearch.svelte`

**Interfaces:**
- Consumes: wasm-bindgen generated JS binder + WASM binary
- Produces: Svelte component with search input + results list

- [ ] **Step 1: Build WASM binary**

```bash
cd crates/arxwasm
wasm-pack build --target web --out-dir ../../static/wasm/arxwasm
```
Expected: produces `static/wasm/arxwasm/arxwasm_bg.wasm` + `static/wasm/arxwasm/arxwasm.js`.

- [ ] **Step 2: Write WASM loader**

```ts
// src/lib/authors/wasm-search.ts
import init, { init as wasmInit, search as wasmSearch, searchStats } from "$lib/../static/wasm/arxwasm/arxwasm.js";

let ready = false;

export async function loadAuthorSearch(): Promise<void> {
  if (ready) return;
  await init(); // instantiate WASM

  // Fetch all shards + rankings
  const shardUrls = Array.from({ length: 31 }, (_, i) => `/data/authors/shard-${i}.json`);
  const rankingsUrl = "/data/author_rankings.json";

  const shardTexts = await Promise.all(
    shardUrls.map((url) => fetch(url).then((r) => r.text()))
  );
  const rankingsText = await fetch(rankingsUrl).then((r) => r.text());

  const combined = shardTexts.join("\n");
  wasmInit(combined, rankingsText);
  ready = true;
}

export function searchAuthors(query: string, max = 20): { name: string; weight: number; coauthors: number; rank: number | null }[] {
  if (!ready) return [];
  return wasmSearch(query, max);
}

export function getStats(): { totalAuthors: number; withRankings: number } {
  if (!ready) return { totalAuthors: 0, withRankings: 0 };
  return searchStats();
}
```

- [ ] **Step 3: Write AuthorSearch Svelte component**

```svelte
<script lang="ts">
  import { onMount } from "svelte";
  import { loadAuthorSearch, searchAuthors, getStats } from "./wasm-search";

  let query = $state("");
  let results = $state<{ name: string; weight: number; coauthors: number; rank: number | null }[]>([]);
  let loading = $state(true);
  let stats = $state({ totalAuthors: 0, withRankings: 0 });
  let debounceTimer: ReturnType<typeof setTimeout>;

  onMount(async () => {
    await loadAuthorSearch();
    stats = getStats();
    loading = false;
  });

  function onInput(e: Event) {
    const target = e.target as HTMLInputElement;
    query = target.value;
    clearTimeout(debounceTimer);
    if (query.length < 2) {
      results = [];
      return;
    }
    debounceTimer = setTimeout(() => {
      results = searchAuthors(query);
    }, 150);
  }
</script>

<div class="author-search">
  {#if loading}
    <p class="loading">Loading author index…</p>
  {:else}
    <p class="stats">{stats.totalAuthors} authors indexed</p>
    <input
      type="search"
      placeholder="Search authors…"
      value={query}
      oninput={onInput}
      class="search-input"
    />
    {#if results.length > 0}
      <ul class="results">
        {#each results as r}
          <li>
            <a href="/authors/{encodeURIComponent(r.name)}">{r.name}</a>
            <span class="meta">{r.weight} papers, {r.coauthors} coauthors</span>
            {#if r.rank !== null}
              <span class="rank">#{r.rank + 1}</span>
            {/if}
          </li>
        {/each}
      </ul>
    {:else if query.length >= 2}
      <p class="no-results">No authors found</p>
    {/if}
  {/if}
</div>

<style>
  .author-search { font-family: var(--font-mono); }
  .search-input { width: 100%; padding: 0.5rem; }
  .results { list-style: none; padding: 0; }
  .results li { padding: 0.25rem 0; display: flex; gap: 1rem; }
  .meta { color: var(--color-muted); font-size: 0.875rem; }
  .rank { color: var(--color-accent); font-weight: bold; }
</style>
```

- [ ] **Step 4: Verify Svelte build**

```bash
npm run build
```
Expected: builds without errors. WASM binary is copied to the output.

- [ ] **Step 5: Commit**

```bash
git add src/lib/authors/ static/wasm/
git commit -m "feat(arxwasm): integrate WASM author search into SvelteKit"
```
