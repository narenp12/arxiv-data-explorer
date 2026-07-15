# Codebase Remediation: arXiv Explorer Quality Fixes

## Scope

Fix all issues from 2026-07-14 code quality triage across 9 categories. Single pass, no decomposition needed — all changes are local refactors within existing files, no new features.

## Phase 1: Dead Code & Circular Deps (P0)

### 1.1 Extract `ensureChecker` → `checker.ts`

**Problem:** `src/lib/utils/db/index.ts` (barrel) defines `ensureChecker` which both `search.ts` and `detail.ts` import from `./index`. Creates 2 circular deps: `index.ts ⇄ search.ts` and `index.ts ⇄ detail.ts`.

**Fix:** Create `src/lib/utils/db/checker.ts` containing:
- `WasmAPI` type ← moved from `index.ts`
- `ensureChecker()` function ← moved from `index.ts`
- `import.meta.env.DEV` WASM init block ← moved from `index.ts`

Update `index.ts` to re-export from `./checker` instead of defining inline.
Update `search.ts:4` and `detail.ts:4` to import `ensureChecker` from `./checker`.

### 1.2 Remove dead `rateLimitedFetchOnce` from rate-limit.ts

**Problem:** Private function never referenced anywhere (confirmed zero importers). Also `inFlight`, `RATE_LIMIT_MS`, and `resetRateLimitState` are exported but never imported externally.

**Fix:** Inline `rateLimitedFetchOnce` body directly into `rateLimitedFetch`. Remove export from `inFlight`, `RATE_LIMIT_MS`, `resetRateLimitState` — keep as module-private. Barrel re-exports in `index.ts` will fail to resolve if any still exist — update accordingly.

### 1.3 Remove/keep dead `searchArxiv`

**Problem:** `searchArxiv()` in `search.ts` has zero consumers. Only `searchArxivCategory` is used.

**Fix:** Remove `searchArxiv` function + its barrel re-export from `index.ts`. The route is dead — arXiv category search uses `searchArxivCategory`.

### 1.4 Remove dead `isReady` export

**Problem:** `isReady()` in `wasm-search.ts` exported but never imported by any consumer.

**Fix:** Remove `export` keyword, keep as module-private helper. Update any internal references if needed (none exist — checked).

## Phase 2: Anti-Patterns (P0/P1)

### 2.1 Fill all empty catch blocks

12 bare catch blocks across 8 files. Each needs at minimum a comment explaining why the error is safe to ignore. Where the error may indicate a real issue, add `console.warn`.

Files:
- `src/lib/utils/db/suggest.ts` — 3 locations (categories load, version check, quota catch)
- `src/routes/+page.svelte` — 2 locations (data load, pulse strip)
- `src/lib/authors/AuthorSearch.svelte` — 1 location
- `src/routes/categories/+page.svelte` — 1 location
- `src/lib/stores/saved.svelte.ts` — 1 location
- `src/routes/authors/+page.svelte` — 1 location
- `src/lib/components/CommandPalette.svelte` — 1 location
- `src/lib/components/CitationGraph.svelte` — 1 location
- `src/lib/utils/db/index.ts` — `.catch(() => {})` on DEV WASM init

### 2.2 Gate/remove console.warn in prod

7 console.warn calls across 3 files. 3 are already gated by `import.meta.env.DEV`. Create `src/lib/utils/logger.ts` with `warn()` / `error()` helpers that no-op in production. Replace all console.warn with `warn()`.

### 2.3 Extract magic numbers as named constants

Key extraction targets:
- search.ts: `30` default page limit → `DEFAULT_PAGE_LIMIT`
- suggest.ts: `3` LRU_MAX → already named but inline
- suggest.ts: `5000` prefetch timeout → named constant
- openalex.ts: `110` rate limit → already named
- openalex.ts: `50` per_page → constant

## Phase 3: Duplicate Code (P1)

### Extract OpenAlex fetch factory in openalex.ts

`fetchReferences`, `fetchCitations`, `fetchRelatedWorks` are identical except URL path segment (`references`, `citations`, `related_works`). Replace with private `fetchWorks(path, id, perPage)` factory + three one-liner exports.

## Phase 4: Type Safety & Rust (P1/P2)

### 4.1 Replace `any` in AuthorGraph.svelte

~20 `as any` casts in D3 force simulation code. Replace with:
- `D3SimNode = d3.SimulationNodeDatum & DispNode`
- `D3SimEdge = d3.SimulationLinkDatum<D3SimNode> & AuthEdge`
- Properly typed `d3.forceLink<D3SimNode, D3SimEdge>()`
- Typed `selectAll<SVGCircleElement, D3SimNode>`

### 4.2 Fix Rust unwrap/expect

- `trigram.rs:57`: `.unwrap()` on `partial_cmp` → `.unwrap_or(Ordering::Equal)`
- `data.rs:26`: `.expect("valid shard JSON")` → return `Result` instead of panicking

## Phase 5: Testing (P2)

### 5.1 Add tests for key untested symbols

- `rateLimitedFetch` — mock fetch, test 429 retry, test dedup via inFlight
- `categoryLabel` — simple lookup table test
- `searchArxivCategory` — mock fetch + XML parse
- `ensureChecker` — test null return when not in DEV

### 5.2 Add `#[cfg(test)]` to arxcheck crate

Add test modules for EdgesCheck, GraphCheck, ShardCheck, CrossRefCheck with known-valid and known-invalid JSON inputs.

## Files Changed

| File | Phase | Change |
|------|-------|--------|
| `src/lib/utils/db/checker.ts` | 1 | NEW — extracted ensureChecker + WasmAPI |
| `src/lib/utils/db/index.ts` | 1 | Remove inline ensureChecker, re-export from checker |
| `src/lib/utils/db/search.ts` | 1, 3 | Update import, remove searchArxiv, extract helper |
| `src/lib/utils/db/detail.ts` | 1 | Update import |
| `src/lib/utils/db/rate-limit.ts` | 1 | Inline rateLimitedFetchOnce, drop exports |
| `src/lib/authors/wasm-search.ts` | 1 | Unexport isReady |
| `src/lib/utils/logger.ts` | 2 | NEW — dev-only warn/error helpers |
| `src/lib/utils/db/suggest.ts` | 2 | Fill empty catches, use logger |
| `src/routes/+page.svelte` | 2 | Fill empty catches |
| `src/lib/authors/AuthorSearch.svelte` | 2 | Fill empty catch |
| `src/routes/categories/+page.svelte` | 2 | Fill empty catch |
| `src/lib/stores/saved.svelte.ts` | 2 | Fill empty catch |
| `src/routes/authors/+page.svelte` | 2 | Fill empty catch |
| `src/lib/components/CommandPalette.svelte` | 2 | Fill empty catch |
| `src/lib/components/CitationGraph.svelte` | 2 | Fill empty catch |
| `src/lib/utils/openalex.ts` | 3 | Extract fetch factory |
| `src/lib/components/AuthorGraph.svelte` | 4 | Replace any with D3 types |
| `crates/arxwasm/src/trigram.rs` | 4 | Fix unwrap |
| `crates/arxwasm/src/data.rs` | 4 | Fix expect |
| `src/lib/utils/db/rate-limit.test.ts` | 5 | NEW |
| `src/lib/utils/categories.test.ts` | 5 | NEW |
| `crates/arxcheck/src/checks/*.rs` | 5 | Add #[cfg(test)] blocks |

## Non-Goals

- NOT refactoring `scripts/build_data.py` (separate effort — speculative design needed)
- NOT adding Rust integration tests (requires WASM test harness setup)
- NOT adding full test suites for every function (only highest-risk untested symbols)
- NOT rewriting D3 force simulation

## Verification

After each phase:
1. `npm run build` (or `rtk npm run build`) to confirm no TypeScript/Svelte errors
2. `npm run test` (or `npx vitest run`) to confirm existing tests still pass
3. For Rust: `cargo build` + `cargo test`
