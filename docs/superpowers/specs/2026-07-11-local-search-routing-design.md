# Local Search Data as Routing Layer for arXiv API

**Status**: Proposed
**Date**: 2026-07-11
**Deciders**: @narenprax

## Problem

`static/data/search.db` (SQLite FTS5) stores 28K+ arXiv papers with title, abstract, authors, categories — but the frontend uses Semantic Scholar API for search. The local database is built but never consumed.

FTS5 contentless bug is fixed (`content=''` removed). Now the local data needs to connect to the frontend.

## Constraint

Free. No D1, R2, or external services. Must work at full 3M paper scale on Cloudflare Pages free tier.

## Solution overview

Three-tier architecture: **Suggest → Route → Enrich**

```
┌─────────────┐   keystroke    ┌──────────────────────┐
│  User types  │ ──────────→   │  Suggest Module       │
│  "quantum"   │               │                      │
└──────┬───────┘               │  Load shard 'q'       │
       │                       │  Build FlexSearch idx │
       │                       │  Show dropdown        │
       │                       └──────────┬───────────┘
       │                                  │
       │  click "Quantum Physics"         │ click "Quantum In-
       │  (category)                      │ verse Scattering..."
       │                                  │
       ▼                                  ▼
┌──────────────┐                 ┌──────────────────┐
│ /api/arxiv   │                 │ /api/arxiv        │
│ ?search      │                 │ ?search_query     │
│ _query=      │                 │ =id:cond-mat/9310 │
│ cat:quant-ph │                 │ 31                │
└──────┬───────┘                 └────────┬─────────┘
       │                                  │
       └──────────────┬───────────────────┘
                      ▼
             ┌──────────────────┐
             │  Result Display  │
             │  (enriched with  │
             │   local data)    │
             └──────────────────┘
```

### Search flow

1. User types in search input
2. Shard loads on first keystroke (no debounce for network)
3. Debounce 300ms → FlexSearch queries cached shard → dropdown with Papers / Authors / Categories
4. **Click suggestion** → route to arXiv API with appropriate query
5. **Hit Enter** (no suggestion) → route to arXiv API with `all:query`
6. Results displayed, enriched with local data (categories, co-author counts)
7. Toggle tab switches between arXiv API results and Semantic Scholar API results

## Tier 1: Auto-suggest

### Shard format

Build-time script exports compact suggestion shards from the paper DataFrame:

```
static/data/search/suggest/
  a.json.gz       → {"t":[[id,title],...], "a":[[name,idx],...]}
  b.json.gz
  ...
  categories.json.gz    → {"c":[[code,desc],...]}  (one file, ~2KB)
  meta.json             → version, updated, total_papers, per-shard stats
```

**Per shard:**
- `t` — paper titles: `[paperId, title]` for titles starting with that letter
- `a` — author names: `[authorName, rankingIndex]` (index into `author_rankings.json`, avoids duplication)

**Categories** stored as a single `categories.json.gz` loaded alongside whatever shard is active.

**meta.json schema:**
```json
{
  "version": 1,
  "updated": "2026-03-04",
  "total_papers": 28731,
  "shards": {
    "a": {"papers": 1100, "authors": 320, "size_bytes": 42000}
  }
}
```

### Edge case: non-ASCII titles

Normalize with `title.normalize("NFD").replace(/[\u0300-\u036f]/g, "")` before extracting first character. Anything outside `[a-zA-Z0-9]` → `other.json.gz`.

### Loading strategy

Each shard fetch uses its own `AbortController`. When user types a different first letter, the previous in-flight fetch is aborted before starting the new one.

```
keypress 'q' → abort previous fetch → fetch q.json.gz (starts immediately, no debounce)
keypress 'u' → abort q fetch → fetch u.json.gz (letter changed mid-flight)
keypress 'a' → shard loaded → 300ms debounce starts
keypress 'n' → debounce resets
(no input for 300ms) → FlexSearch.query("quant") → render dropdown
```

Overlaps download time with typing. Net latency at 3M: ~800ms instead of 1.3s.

**Prefetch on idle:** After page load, `requestIdleCallback(() => prefetch(['a','c','m','s','t']))` with `setTimeout` polyfill. Covers ~80% of common query starts. If user types a letter whose shard is still downloading via prefetch, the active fetch wins (AbortController from prior prefetch is cancelled).

### Cache strategy

| Tier | Where | Survives | Max at 3M | Eviction |
|------|-------|----------|-----------|----------|
| FlexSearch index | In-memory Map | SPA navigation | ~8MB | LRU, max 3 shard indexes |
| Shard data | sessionStorage | Page refresh | ~1.5MB/shard | LRU, keep 3 most recent |
| meta.json | localStorage | Indefinite | ~2KB | Version check on load |

**LRU eviction** for sessionStorage: on `QuotaExceededError`, clear least-recently-used shard key and retry. On repeated failure, fall back to no caching (fetch every time).

**SessionStorage** caches up to 3 most recently loaded shards so page refresh doesn't redownload. FlexSearch index rebuilt from cached data on reload (~50ms vs 800ms from raw text).

**Meta version check:** On page load, read `localStorage['suggest_meta_version']`. If it doesn't match the fetched `meta.json.version`, clear all cached shards from sessionStorage and reload. This catches stale suggests after a data rebuild.

### Shard failures

- Shard 404/network error → suggestions disabled for that letter. Search still works via Enter/button.
- FlexSearch OOM at 3M → fallback: disable suggestions entirely for that session, route directly to API. `String.includes()` O(n) on 3M items blocks main thread.
- sessionStorage `QuotaExceededError` → catch, call `.clear()`, retry once. LRU eviction keeps only the N most recently accessed shards (N=3 at 3M scale, ~4.5MB used out of ~5-10MB quota).

## Tier 2: Route to arXiv API

| Trigger | Action | API call |
|---------|--------|----------|
| Click paper title | Fetch paper by ID | `/api/arxiv?search_query=id:arXivID` |
| Click author name | Search author's papers | `/api/arxiv?search_query=au:"Name"` |
| Click category code | List category papers | `/api/arxiv?search_query=cat:category` |
| Hit Enter (no suggestion) | Full-text search | `/api/arxiv?search_query=all:query` |
| Click "Search" button | Full-text search | `/api/arxiv?search_query=all:query` |

All routed through existing `/api/arxiv` Cloudflare Pages Function proxy (free, no rate limits).

### API error handling

- arXiv API 429/500 → show existing error pattern: "arXiv is busy — Retry" with retry button (same as current Semantic Scholar handling)
- arXiv API returns empty results → show "No results" state
- Network offline → clear messaging, suggestions from cache only (if shards cached in sessionStorage)

## Tier 3: Enrich results with local data

After arXiv API returns results, cross-reference against local data:

- Attach arXiv category labels (from `categories.json.gz`)
- Add co-author counts (from `author_rankings.json`)
- Add local paper counts if available

This runs client-side using the local data files already loaded for suggest.

## Semantic Scholar toggle

Tab bar always visible above results area, even in empty state:
```
[ arXiv ] [ Semantic Scholar ]
```

- **arXiv tab** (default) — routes through `/api/arxiv`
- **Semantic Scholar tab** — routes through existing `/api/s2` (preserves `searchPapers()`)
- **Separate query per tab:** Each tab tracks its own query. Switching tabs preserves the other tab's last query in component state. No query format translation between tabs.
- Tab state reflected in URL (`?tab=arxiv` or `?tab=s2`)
- URL follows existing `syncUrl()` pattern: `?q=cat:quant-ph&tab=arxiv&page=1` on suggestion clicks
- **S2-only filters hidden when arXiv tab active:** `SearchFilters` component hidden entirely. Filters reappear on S2 tab.

## File changes

### `package.json`
- Add `"flexsearch": "^0.8"` to `dependencies`

### Build environment
- Requires Python `brotli` package (`pip install brotli` or `brotlipy`) for Brotli compression

### `scripts/build_data.py`
- New function `build_suggest_index(df)`:
  - Group papers by first character of normalized title (NFD-normalized before grouping)
  - For each group, write `{t, a}` as gzipped JSON and Brotli-compressed (`.br`) variant
  - `paperId` uses the full arXiv identifier string (e.g. `arXiv:cond-mat/931031`)
  - Write `categories.json.gz` and `categories.json.br`
  - Write `meta.json`
  - Supports `--no-incremental` (same as existing builders)

### `src/lib/utils/db/suggest.ts` (new)
- `SuggestShard` class:
  - `load(letter)`: fetch + decompress + cache in sessionStorage. Calls `checkVersion()` first — if version mismatched, purges sessionStorage before fetching. Uses `AbortController` — aborts previous in-flight fetch on new call. Handles `QuotaExceededError` with `.clear()` + retry.
  - `buildIndex()`: create FlexSearch index from shard data
  - `search(query, limit)`: query FlexSearch, return categorized results (Papers, Authors, Categories)
  - `prefetch()`: `requestIdleCallback(() => prefetch(['a','c','m','s','t']))` with `setTimeout(5000)` polyfill
  - `checkVersion()`: compare local `meta.version` against fetched meta. On mismatch, purge sessionStorage cache.
  - Handles non-ASCII normalization, FlexSearch OOM fallback (disable suggestions), network errors

### `src/lib/components/SearchSuggest.svelte` (new)
- Dropdown overlay on search input, positioned absolutely below input
- Three sections: Papers, Authors, Categories
- **Full keyboard navigation:** Arrow keys move selection (no wrap-around — stops at top/bottom), Enter selects highlighted item, Escape closes dropdown + refocuses input, Tab closes + focuses next element. `role="listbox"`, `aria-activedescendant`, `aria-selected` on items. Live region for screen reader announcements of result count.
- **Click-outside:** Click anywhere outside dropdown closes it. Search button click also closes dropdown.
- Loading state while FlexSearch builds
- Empty state when no matches
- Error state hidden (suggestions degrade silently, search still works)
- Suggestion text rendered via `.textContent` (never `.innerHTML`) — data is build-generated but defense-in-depth
- Last item: "Search arXiv for '{query}'" responds to click AND Enter → routes to API with `all:query`

### `src/lib/components/SearchView.svelte`
- Integrate SearchSuggest into search input
- Wire suggestion click → arXiv API via `doSearch()` + URL updated with `syncUrl()` pattern (`?q=cat:quant-ph&tab=arxiv&page=1`)
- Wire Enter → arXiv API via `doSearch()` + URL update
- Add tab bar (always visible): arXiv / Semantic Scholar. Tab state in URL (`?tab=arxiv` or `?tab=s2`).
- Separate query tracking per tab — switching tabs preserves each tab's last query in component state
- Hide `SearchFilters` component when arXiv tab active
- arXiv tab calls `searchArxiv()` function

### `src/lib/utils/db/search.ts`
- Add generic `searchArxiv(query, opts?)` function that wraps `/api/arxiv` calls (alongside existing `searchArxivCategory()`)
- Constructs `search_query=all:query`, `au:"name"`, `id:arXivID`, or `cat:category` depending on query format
- Parse arXiv API XML response (like existing `parseArxivResponse`)
- Keep `searchPapers()` for Semantic Scholar tab

### `functions/api/arxiv.js`
- Already exists — no changes needed

## Alternatives considered

| Approach | Cost | Search quality | Rejected because |
|----------|------|---------------|------------------|
| D1 FTS5 | ~$4-6/mo at 3M | Full FTS5 | Not free |
| sql.js in browser | Free | Full FTS5 | 41MB download, won't scale to 3M |
| R2 custom index | Free | No FTS5, must build | Complex, no FTS5 |
| This (sharded JSON + arXiv API) | Free | Basic suggest + API search | Best fit for constraints |

## Consequences

### Positive
- Free — no infra changes, no new services
- Fast after first load — cached shards + FlexSearch = instant
- arXiv API is comprehensive (full arXiv corpus, not just local 28K/3M sample)
- Local data reused for enrichment (categories, authors)
- Both arXiv and Semantic Scholar available as tabs

### Negative
- First keystroke latency at 3M: ~800ms (vs ~100ms at 28K)
- No abstract search locally — abstract-heavy queries go to API
- Suggestion quality depends on shard data freshness
- 3M → FlexSearch index ~8MB in browser memory
- Brotli + gzip shard files double storage in `static/data/search/suggest/` (~40MB extra at 3M)

### Neutral
- Need to rebuild suggest shards when papers are updated
- Two search APIs to maintain (arXiv + Semantic Scholar)
- sessionStorage caching means first visit to a letter is slow

## Testing

- **Unit:** Mock fetch for `SuggestShard.load()` — verify decompression, caching, AbortController dedup, QuotaExceededError recovery, version mismatch purge, LRU eviction behavior
- **Unit:** `SuggestShard.search()` with fixture shard — verify FlexSearch query returns correct paper/author/category results
- **Unit:** `searchArxiv()` with mock XML response — verify URL construction (`all:`, `cat:`, `au:`, `id:` query format detection) and XML parsing
- **Integration (Playwright/browser):**
  - Load page with fixture suggest shards, type into search input, verify dropdown appears with correct suggestions
  - Verify keyboard nav: arrow down/up moves selection, Enter selects, Escape closes, Tab closes+focusses next
  - Verify click-outside closes dropdown
  - Verify "Search arXiv for" item responds to both click and Enter
  - Verify suggestion click routes to arXiv API and updates URL
  - Verify tab toggle switches search source, preserves last query per tab
  - Verify S2 filters hidden when arXiv tab active, reappear on S2 tab
  - Verify URL reflects tab state (`?tab=arxiv` / `?tab=s2`)

## Key metrics

| Metric | Sample (28K) | Full (3M) |
|--------|-------------|-----------|
| Shard count | 27 + 1 | 27 + 1 |
| Shard size (avg gzip) | ~40KB | ~1.5MB |
| First keystroke latency | ~110ms | ~800ms |
| Subsequent searches | ~10ms | ~10ms |
| FlexSearch index memory | ~80KB | ~8MB |
| sessionStorage per shard | ~40KB | ~1.5MB |
| Brotli shard size (estimated) | ~32KB | ~1.2MB |

## Future considerations

- Service Worker cache for full offline support
- Trending/related-term suggestions from local data
- Local search as standalone mode (no arXiv API)
