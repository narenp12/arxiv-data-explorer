# Navbar Search Improvements

## Problem

The global navbar search (`UnifiedSearch.svelte`) produces noticeably worse results than the dedicated papers page search. Three data sources are searched locally with `String.includes()` — no ranking, no fuzzy matching, no relevance scoring. Paper results are capped at 4 in a cramped dropdown.

## Approach

Quick wins using existing infrastructure. Three independent changes:

1. **Authors** — integrate existing `arxwasm` WASM module (trie + trigram fuzzy matching, already compiled and used on `/authors` page)
2. **Categories** — ranked scoring (prefix > word-start > substring), zero new data
3. **Papers** — increase limit, show citation count, widen dropdown

## Changes

### 1. Authors: WASM fuzzy search with progressive enhancement

Replace current `author_rankings.json` + `includes()` with `arxwasm` WASM module, but keep the JSON approach as a fallback.

**Loading strategy** (progressive enhancement):
1. On first focus, start loading WASM + 31 shards in background (same pattern as `wasm-search.ts`)
2. While WASM loads, continue filtering `author_rankings.json` with `includes()` for instant results
3. When WASM is ready, switch to `wasmSearch()` — results improve seamlessly on next keystroke

**Scoring**: WASM returns ranked results via trigram similarity. Top 5 shown. Tiebreaker: higher paper count first.

**Errors**: If WASM init fails, silently fall back to `includes()` filtering (current behavior). No error surface shown to user.

### 2. Categories: Ranked matching

Replace `includes()` with weighted scoring:

| Match type | Score |
|---|---|
| Exact match (label or id) | 100 |
| Starts with query | 80 |
| Word starts with query | 60 |
| Substring match | 40 |

Results sorted by score desc, then paper count desc. Cap at 5.

No new data loads — uses existing `category_hierarchy.json`.

### 3. Papers: More results, better display

- Increase `limit` from 4 to 8
- Show citation count badge on right side of result row (next to year)
- Same `searchPapers()` call, same caching

### 4. Layout: Widen dropdown

- Input: `max-w-[200px]` → `max-w-xs` (320px)
- Dropdown: `min-w-[360px]` → `min-w-[420px]`
- Add "View all X results →" link at bottom of each section:
  - Papers: `/papers?q={query}`
  - Authors: `/authors?q={query}`
  - Categories/Trends: `/trends?q={query}`

### Files changed

| File | Changes |
|---|---|
| `src/lib/components/UnifiedSearch.svelte` | Import arxwasm, replace author filtering, score categories, increase paper limit, widen dropdown, add view-all links |
| `src/lib/authors/wasm-search.ts` | Export `isReady()` getter so navbar can check WASM status without calling `searchAuthors()` and guessing from empty results |

### Non-goals

- No new data files or build steps
- No recomputation of WASM shards
- No restructuring of the dropdown into multi-column layout (deferred to future iteration)
- No keyboard shortcut changes

## Verification

1. Type partial author name in navbar — should return ranked fuzzy matches, not alphabetical
2. Type category prefix — exact match shows first
3. Paper results show 8 items with citation counts
4. Dropdown wider, sections have "View all" links
5. WASM init happens on first focus, not on page load
