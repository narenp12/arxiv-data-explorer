# Rust Integrations for arxiv-data-explorer

## Overview

Two Rust crates supplementing the existing SvelteKit + Python data pipeline:
1. **`arxwasm`** — WASM author search index (frontend)
2. **`arxcheck`** — Dual-target checker (CI CLI + browser WASM)

---

## 1. `arxwasm` — WASM Author Search

### Purpose

Replace any server-side author lookup with purely client-side full-text search across ~25K authors, powered by a Rust → WASM prefix trie with fuzzy fallback.

### Data model

Current `static/data/authors/shard-*.json` (30 shards, ~800 authors each):

```
"Author Name": { w: <weight>, co: [["Coauthor", <weight>], ...] }
```

Plus `static/data/author_rankings.json`: `[{name, papers, relative}, ...]`.

### Architecture

```
┌──────────────────────────────────────────────┐
│  SvelteKit page                              │
│  ┌─────────────────────────────────────────┐ │
│  │  JS glue (wasm-bindgen)                 │ │
│  │  - load wasm module on mount            │ │
│  │  - feed all shards as JSON string       │ │
│  │  - call search(query, max_results)     │ │
│  └────────────┬────────────────────────────┘ │
│               │                               │
│               ▼                               │
│  ┌─────────────────────────────────────────┐ │
│  │  WASM module (arxwasm)                  │ │
│  │                                         │ │
│  │  ┌─────────┐  ┌──────────┐  ┌────────┐ │ │
│  │  │Prefix   │  │Trigram   │  │Ranker  │ │ │
│  │  │trie     │  │index     │  │(w, co, │ │ │
│  │  │         │  │(fuzzy)   │  │ rank)  │ │ │
│  │  └─────────┘  └──────────┘  └────────┘ │ │
│  └─────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

### Components

| Component | Responsibility |
|---|---|
| **Normalizer** | lowercase, strip punctuation, normalize Unicode (NFKC) |
| **Prefix trie** | O(k) exact-match prefix lookup on normalized names |
| **Trigram index** | 3-gram overlap + Levenshtein distance for typo tolerance |
| **Ranker** | Sort candidates by: author weight > co-author count > ranking position |
| **JS glue** | `load(data: string)`, `search(query: string, max: u32) -> JsValue` |

### Integration

- Build with `wasm-pack build --target web`
- SvelteKit imports generated JS binder (`import init, { load, search } from "arxwasm"`)
- WASM binary hosted alongside other static assets in the SvelteKit build
- Author shards already loaded as static JSON — no additional network cost

### Output

`search("chen", 10)` returns a `JsValue` deserialized to:
```ts
{ name: string, weight: number, coauthors: number, rank: number | null }[]
```

### Bundle size

WASM binary: ~80-150KB gzipped. Author JSON: already ~2MB in the static bundle.

---

## 2. `arxcheck` — Validation Checker

### Purpose

Dual-target Rust crate that validates data integrity: CLI binary for CI, WASM module for runtime API response validation.

### Architecture

```
┌─────────────────────┐     ┌─────────────────────────┐
│  CLI (arxcheck)     │     │  WASM (wasm-checker)     │
│                     │     │                          │
│  cargo build --bin  │     │  wasm-pack build --target web
│                     │     │                          │
│  ┌───────────────┐  │     │  ┌────────────────────┐  │
│  │ checks::shard │  │     │  │ checks::api_contract│  │
│  │ checks::edges │  │     │  │ validate_paper...() │  │
│  │ checks::graph │  │     │  │ validate_detail()  │  │
│  │ checks::xref  │  │     │  │ validate_profile() │  │
│  └───────────────┘  │     │  └────────────────────┘  │
└─────────────────────┘     └──────────────────────────┘
       │                             │
       ▼                             ▼
  prebuild script              wrapped fetch calls
  (CI gating)                  in db.ts
```

### Validation modules

#### `checks::shard` (CLI only)
- Every `shard-*.json` parses as valid JSON with expected schema
- No duplicate author names across shards
- All weights (`w`) are non-negative integers
- Co-author lists reference names that exist in some shard

#### `checks::edges` (CLI only)
- Every `source` and `target` in `causal_edges.json` exists as a key in `category_dynamics.json`
- Edge weights are finite, CI bounds are well-ordered (lower < upper)
- `prob` is 0.5–1.0

#### `checks::graph` (CLI only)
- Every edge in `category_graph.json` references valid nodes
- No duplicate edges (same source + target pair)
- Node IDs are non-empty

#### `checks::cross_ref` (CLI only)
- All names in `author_rankings.json` appear in at least one shard
- `relative` field is 0–100 inclusive
- Paper counts are non-negative

#### `checks::api_contract` (WASM only)
Exposes validation functions for each API response type:
- `validate_paper_result(json: &[u8])` — checks all fields of `PaperResult` exist with correct types
- `validate_paper_detail(json: &[u8])` — checks `PaperDetail` shape, non-null where required
- `validate_author_profile(json: &[u8])` — checks `AuthorProfile` shape

Each returns either Ok or an error listing all field mismatches found.

### Dual-target build

Both targets share `src/checks/` modules. Target selection:

```
cargo build --bin arxcheck                    # native CLI
cargo build --target wasm32-unknown-unknown    # WASM (wasm-bindgen stubs)
```

CLI adds `#[cfg(not(target_arch = "wasm32"))]` for file I/O (`std::fs`, `clap`). WASM adds `#[cfg(target_arch = "wasm32")]` for `wasm-bindgen` exports. Validation logic itself is target-agnostic — operates on `&[u8]` / `&str`.

### CI integration

```jsonc
// package.json
{
  "scripts": {
    "prebuild": "arxcheck static/data",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json && arxcheck static/data"
  }
}
```

Fails the build with a non-zero exit code and a list of violations.

### Runtime integration

API contract validation fires only in dev mode (`import.meta.env.DEV`) to avoid runtime overhead in production:

```ts
// src/lib/utils/db.ts — wrapped fetch
import { validatePaperResult } from "wasm-checker";

async function searchPapers(...) {
  const res = await rateLimitedFetch(url);
  const data = await res.json();
  if (import.meta.env.DEV) {
    const errors = validatePaperResult(JSON.stringify(data));
    if (errors) console.warn("API contract violation:", errors);
  }
  // ... continue
}
```

---

## 3. Build & project structure

```
arxiv-data-explorer/
├── crates/
│   ├── arxwasm/                # wasm-pack project
│   │   ├── Cargo.toml
│   │   ├── src/lib.rs
│   │   └── src/search/         # trie, trigram, ranker
│   └── arxcheck/               # shared validation logic
│       ├── Cargo.toml
│       ├── build.rs             # conditional WASM/CLI build
│       └── src/
│           ├── lib.rs           # checks module shared by both targets
│           ├── checks/
│           │   ├── mod.rs
│           │   ├── shard.rs
│           │   ├── edges.rs
│           │   ├── graph.rs
│           │   ├── xref.rs
│           │   └── api_contract.rs
│           ├── bin/arxcheck.rs  # CLI entrypoint (native)
│           └── wasm.rs          # wasm-bindgen exports (WASM target)
├── scripts/                     # unchanged Python pipeline
├── src/                         # unchanged SvelteKit frontend
└── static/data/                 # unchanged JSON data
```

### Dependencies

**`arxwasm`**: `wasm-bindgen`, `serde_json`, `unicode-normalization` (optional, for NFKC)

**`arxcheck`**: `serde`, `serde_json`, `clap` (CLI), `wasm-bindgen` (WASM), `js-sys` (WASM)

No heavy dependencies — no `ndarray`, no `tokio`, no `regex`. Both crates are intentionally minimal.
