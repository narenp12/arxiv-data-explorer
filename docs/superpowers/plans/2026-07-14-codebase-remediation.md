# Codebase Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all issues from code quality triage: dead code, empty catch blocks, circular deps, duplicate code, `any` types, console.warn in prod, Rust unwraps, missing tests.

**Architecture:** Five independent phases — each produces working code without blocking later phases. Phases 1-4 are source changes, Phase 5 adds tests. Order matters within phases but not between phases.

**Tech Stack:** TypeScript 5.x, Svelte 5, Rust with wasm-bindgen, Vitest

---
## Global Constraints

- No new npm/cargo dependencies
- All catch blocks must have at least a comment explaining why the error is safe to ignore
- New exports must have JSDoc if public
- All changes must pass `npx vitest run` and `cargo test`
- Keep existing code style (tabs for TS/Svelte, 4-space for Rust, single quotes for TS)

---

## File Structure

**New files:**
- `src/lib/utils/db/checker.ts` — WASM checker init (extracted from `index.ts`)
- `src/lib/utils/logger.ts` — dev-only warn/error helpers
- `src/lib/utils/db/rate-limit.test.ts` — rateLimitedFetch tests
- `src/lib/utils/categories.test.ts` — categoryLabel tests

**Modified files:**
- `src/lib/utils/db/index.ts` — remove inline ensureChecker, re-export from checker
- `src/lib/utils/db/search.ts` — update ensureChecker import, remove searchArxiv, drop re-export
- `src/lib/utils/db/detail.ts` — update ensureChecker import
- `src/lib/utils/db/rate-limit.ts` — inline rateLimitedFetchOnce, drop dead exports
- `src/lib/authors/wasm-search.ts` — unexport isReady
- `src/lib/utils/db/suggest.ts` — fill empty catches, use logger
- `src/lib/utils/openalex.ts` — extract fetch factory for references/citations/related
- `src/lib/components/AuthorGraph.svelte` — replace `any` with D3 types
- `src/routes/+page.svelte` — fill empty catches
- `src/lib/authors/AuthorSearch.svelte` — fill empty catch
- `src/routes/categories/+page.svelte` — fill empty catch
- `src/lib/stores/saved.svelte.ts` — fill empty catch
- `src/routes/authors/+page.svelte` — fill empty catch
- `src/lib/components/CommandPalette.svelte` — fill empty catch
- `src/lib/components/CitationGraph.svelte` — fill empty catch
- `crates/arxwasm/src/trigram.rs` — fix unwrap
- `crates/arxwasm/src/data.rs` — fix expect
- `src/lib/utils/db/index.ts` line 22 — remove searchArxiv from re-exports

### Task 1: Extract ensureChecker → checker.ts (break circular deps)

**Files:**
- Create: `src/lib/utils/db/checker.ts`
- Modify: `src/lib/utils/db/index.ts`
- Modify: `src/lib/utils/db/search.ts:4`
- Modify: `src/lib/utils/db/detail.ts:4`

**Interfaces:**
- Consumes: nothing
- Produces: `ensureChecker(): WasmAPI | null` from `checker.ts`

- [ ] **Create `src/lib/utils/db/checker.ts`:**

```ts
type WasmAPI = { default: () => Promise<void>; validate_paper_result_json: (json: string) => string[]; validate_paper_detail_json: (json: string) => string[]; validate_profile_json: (json: string) => string[] };

let _check: WasmAPI | null = null;
let _checkReady = false;

export function ensureChecker(): WasmAPI | null {
	if (!_checkReady) return null;
	return _check;
}

if (import.meta.env.DEV) {
	import("../../../../static/wasm/arxcheck/arxcheck.js")
		.then((m) => m.default().then(() => { _check = m as unknown as WasmAPI; _checkReady = true; }))
		.catch(() => {});
}

export type { WasmAPI };
```

- [ ] **Update `src/lib/utils/db/index.ts`:**

Replace the top block (lines 1-15) with a single re-export:

```ts
export { ensureChecker } from './checker';
export type { WasmAPI } from './checker';
```

Keep all other re-exports unchanged.

- [ ] **Update `src/lib/utils/db/search.ts:4`:**

```ts
import { ensureChecker } from './checker';
```

- [ ] **Update `src/lib/utils/db/detail.ts:4`:**

```ts
import { ensureChecker } from './checker';
```

- [ ] **Verify build:**

```bash
npx vite build 2>&1 | head -30
```

Expected: No errors.

### Task 2: Inline rateLimitedFetchOnce, drop dead exports

**Files:**
- Modify: `src/lib/utils/db/rate-limit.ts`

- [ ] **Rewrite `src/lib/utils/db/rate-limit.ts`:**

Inline `rateLimitedFetchOnce` into `rateLimitedFetch`. Drop exports from `inFlight`, `RATE_LIMIT_MS`, `resetRateLimitState` (make them module-private). The `RATE_LIMIT_MS` and `inFlight` will still work because barrel re-exports no longer reference them.

```ts
const RATE_LIMIT_MS = 1100;
let lastRequest = 0;
let requestQueue: Promise<void> = Promise.resolve();
const inFlight = new Map<string, Promise<Response>>();

function resetRateLimitState() {
	lastRequest = 0;
	requestQueue = Promise.resolve();
	inFlight.clear();
}

export async function rateLimitedFetch(url: string): Promise<Response> {
	const retryDelaysMs = [2000, 5000];

	const once = async (): Promise<Response> => {
		const prev = requestQueue;
		let resolveNext: () => void;
		requestQueue = new Promise((r) => { resolveNext = r; });
		await prev;

		const inflight = inFlight.get(url);
		if (inflight) { resolveNext!(); return inflight.then((r) => r.clone()); }

		const now = Date.now();
		const wait = Math.max(0, RATE_LIMIT_MS - (now - lastRequest));
		if (wait > 0) await new Promise((r) => setTimeout(r, wait));
		lastRequest = Date.now();
		const promise = fetch(url);
		inFlight.set(url, promise);
		promise.finally(() => {
			resolveNext!();
			queueMicrotask(() => inFlight.delete(url));
		});
		return promise.then((r) => r.clone());
	};

	let res = await once();
	for (const fallbackDelay of retryDelaysMs) {
		if (res.status !== 429) return res;
		const retryAfter = res.headers.get("Retry-After");
		const retrySeconds = retryAfter ? parseFloat(retryAfter) : NaN;
		const delayMs = Number.isFinite(retrySeconds) ? retrySeconds * 1000 : fallbackDelay;
		await new Promise((r) => setTimeout(r, delayMs));
		res = await once();
	}
	if (res.status === 429) throw new Error("SEARCH_BUSY");
	return res;
}
```

- [ ] **Remove stale re-exports from `index.ts`:**

In `src/lib/utils/db/index.ts`, change line 20 from:
```ts
export { rateLimitedFetch, RATE_LIMIT_MS } from './rate-limit';
```
to:
```ts
export { rateLimitedFetch } from './rate-limit';
```

- [ ] **Verify build:**

```bash
npx vite build 2>&1 | head -30
```

Expected: No errors.

### Task 3: Remove dead searchArxiv and isReady

**Files:**
- Modify: `src/lib/utils/db/search.ts:169-210`
- Modify: `src/lib/utils/db/index.ts:23`
- Modify: `src/lib/authors/wasm-search.ts:6`

- [ ] **Remove `searchArxiv` function from `search.ts`:**

Delete lines 169-210 (the `searchArxiv` function declaration). Keep `searchArxivCategory` — it's used.

- [ ] **Remove `searchArxiv` from barrel re-export in `index.ts`:**

Change line 23 from:
```ts
export { searchPapers, searchArxiv, searchArxivCategory, parseArxivTotal, sanitiseYearRange, sanitiseFieldOfStudy, sanitiseMinCites, SEARCH_FIELDS } from './search';
```
to:
```ts
export { searchPapers, searchArxivCategory, parseArxivTotal, sanitiseYearRange, sanitiseFieldOfStudy, sanitiseMinCites, SEARCH_FIELDS } from './search';
```

- [ ] **Unexport `isReady` in `wasm-search.ts`:**

Change line 6 from:
```ts
export function isReady(): boolean {
```
to:
```ts
function isReady(): boolean {
```

- [ ] **Verify build:**

```bash
npx vite build 2>&1 | head -30
```

Expected: No errors.

### Task 4: Create logger utility

**Files:**
- Create: `src/lib/utils/logger.ts`

- [ ] **Create `src/lib/utils/logger.ts`:**

```ts
export const warn = import.meta.env.DEV
	? console.warn.bind(console)
	: () => {};

export const error = import.meta.env.DEV
	? console.error.bind(console)
	: () => {};
```

### Task 5: Fill empty catch blocks

**Files:**
- Modify: `src/lib/utils/db/suggest.ts`
- Modify: `src/routes/+page.svelte`
- Modify: `src/lib/authors/AuthorSearch.svelte`
- Modify: `src/routes/categories/+page.svelte`
- Modify: `src/lib/stores/saved.svelte.ts`
- Modify: `src/routes/authors/+page.svelte`
- Modify: `src/lib/components/CommandPalette.svelte`
- Modify: `src/lib/components/CitationGraph.svelte`

- [ ] **Fix suggest.ts:50 (categories load):**

```ts
	} catch {
		// categories non-critical — search still works without them
	}
```

- [ ] **Fix suggest.ts:220 (version check):**

```ts
	} catch {
		return false; // version check failed, treat as no update
	}
```

- [ ] **Fix suggest.ts:240 (quota catch):**

```ts
		} catch {
			// sessionStorage quota exceeded — degrade gracefully, do not retry
		}
```

- [ ] **Fix suggest.ts:131 console.warn → use logger:**

```ts
import { warn } from '$lib/utils/logger';

// Inside catch block:
if (e?.name === "AbortError") return;
warn(`SuggestShard load error for ${letter}:`, e);
```

- [ ] **Fix suggest.ts:120 console.warn → use logger:**

```ts
warn("FlexSearch OOM, disabling suggestions", e);
```

- [ ] **Fix +page.svelte:22:**

```ts
} catch {
	// data load non-critical — page renders with empty state
}
```

- [ ] **Fix +page.svelte:44:**

```ts
} catch {
	// pulse strip simply doesn't render — non-critical
}
```

- [ ] **Fix AuthorSearch.svelte:16:**

```ts
} catch {
	// search load failure — fall back to empty results
}
```

- [ ] **Fix categories/+page.svelte:33:**

```ts
} catch {
	// categories load non-critical — show empty
}
```

- [ ] **Fix saved.svelte.ts:25:**

```ts
} catch {
	// readingList restore failed — start with empty list
}
```

- [ ] **Fix authors/+page.svelte:19:**

```ts
} catch {
	// author list load non-critical
}
```

- [ ] **Fix CommandPalette.svelte:54:**

```ts
} catch {
	// command palette data load non-critical
}
```

- [ ] **Fix CitationGraph.svelte:165:**

```ts
} catch {
	// citation data load non-critical — graph won't render
}
```

- [ ] **Fix index.ts:14 DEV catch:**

```ts
.catch(() => {
	// DEV-only WASM check — production never runs this path
});
```

- [ ] **Verify build:**

```bash
npx vite build 2>&1 | head -30
```

Expected: No errors.

### Task 6: Gate remaining console.warn calls with logger

**Files:**
- Modify: `src/lib/components/UnifiedSearch.svelte:57,70,146`
- Modify: `src/lib/utils/db/detail.ts:59`
- Modify: `src/lib/utils/db/search.ts:127`

- [ ] **Add logger import to UnifiedSearch.svelte:**

```ts
import { warn } from '$lib/utils/logger';
```

Replace:
```ts
console.warn("Failed to load search data:", err)
→ warn("Failed to load search data:", err)

console.warn("WASM load failed, falling back to includes():", err)
→ warn("WASM load failed, falling back to includes():", err)

console.warn("Paper search failed:", err)
→ warn("Paper search failed:", err)
```

- [ ] **Add logger import to detail.ts:**

```ts
import { warn } from '$lib/utils/logger';
```

Replace:
```ts
console.warn("[arxcheck] PaperDetail violations:", errs)
→ warn("[arxcheck] PaperDetail violations:", errs)
```

- [ ] **Add logger import to search.ts:**

```ts
import { warn } from '$lib/utils/logger';
```

Replace:
```ts
console.warn("[arxcheck] PaperResult violations:", errs)
→ warn("[arxcheck] PaperResult violations:", errs)
```

(The suggest.ts warn calls were already updated in Task 5.)

- [ ] **Verify build:**

```bash
npx vite build 2>&1 | head -30
```

Expected: No errors.

### Task 7: Extract OpenAlex fetch factory

**Files:**
- Modify: `src/lib/utils/openalex.ts:141-169`

- [ ] **Replace three duplicate fetch functions with factory:**

Delete lines 141-169 (`fetchReferences`, `fetchCitations`, `fetchRelatedWorks`). Add factory + re-exports:

```ts
async function fetchWorks(path: string, id: string, perPage = 25): Promise<WorkSummary[]> {
	const oaid = normalizeOpenAlexId(id);
	const res = await rateLimitedFetch(
		`${API_BASE}/works/${encodeURIComponent(oaid)}/${path}?per_page=${perPage}&select=id,title,authorships,publication_year,doi,cited_by_count`,
	);
	if (!res.ok) return [];
	const data = await res.json();
	return (data.results ?? []).map(parseWork);
}

export const fetchReferences = (id: string, perPage = 25) => fetchWorks("references", id, perPage);
export const fetchCitations = (id: string, perPage = 25) => fetchWorks("citations", id, perPage);
export const fetchRelatedWorks = (id: string, perPage = 25) => fetchWorks("related_works", id, perPage);
```

- [ ] **Verify build:**

```bash
npx vite build 2>&1 | head -30
```

Expected: No errors.

### Task 8: Replace any with D3 types in AuthorGraph.svelte

**Files:**
- Modify: `src/lib/components/AuthorGraph.svelte`

- [ ] **Add typed D3 aliases after existing interfaces (line 12):**

```ts
type D3SimNode = d3.SimulationNodeDatum & DispNode;
type D3SimEdge = d3.SimulationLinkDatum<D3SimNode> & AuthEdge;
```

- [ ] **Replace `any[]` state declarations (lines 24-25):**

```ts
let graphEdges: D3SimEdge[] = $state([]);
let graphNodes: D3SimNode[] = $state([]);
```

- [ ] **Replace `n: any` in matchCount derived (line 32):**

```ts
? graphNodes.filter((n: D3SimNode) => n.label.toLowerCase().includes(searchQuery.trim().toLowerCase())).length
```

- [ ] **Replace `any` in coauthorList derived (lines 39-43):**

```ts
for (const e of graphEdges) {
	const source = e.source as D3SimNode;
	const target = e.target as D3SimNode;
	if (source.id === selectedNode.id) degrees.set(target.label ?? target.id, (degrees.get(target.label ?? target.id) ?? 0) + (e.weight ?? 1));
	if (target.id === selectedNode.id) degrees.set(source.label ?? source.id, (degrees.get(source.label ?? source.id) ?? 0) + (e.weight ?? 1));
}
```

- [ ] **Replace forceLink any cast (line 151):**

```ts
.force("link", d3.forceLink<D3SimNode, D3SimEdge>(edges).id((d) => d.id).distance(50).strength(0.3))
```

- [ ] **Replace all `<any, any>` generic params in D3 selections:**

Replace all `selectAll<any, any>(...)` with `selectAll<SVGCircleElement, D3SimNode>(...)` for circles and `selectAll<SVGPathElement, D3SimEdge>(...)` for paths.

Replace all `(d: any) =>` callbacks with `(d: D3SimNode) =>` or `(d: D3SimEdge) =>` as appropriate.

Replace `edgePath(d: any)` → `edgePath(d: D3SimEdge)` (line 162).

Replace `radius = (d: any)` → `radius = (d: D3SimNode)` (line 179). 

Replace all `(e.source as any)` → `(e.source as D3SimNode)` and `(e.target as any)` → `(e.target as D3SimNode)`.

- [ ] **Verify build:**

```bash
npx vite build 2>&1 | head -30
```

Expected: No errors.

### Task 9: Fix Rust unwrap/expect panics

**Files:**
- Modify: `crates/arxwasm/src/trigram.rs:57`
- Modify: `crates/arxwasm/src/data.rs:26`

- [ ] **Fix trigram.rs:57 — unwrap → unwrap_or:**

```rust
// Before:
results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());

// After:
results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
```

- [ ] **Fix data.rs:26 — expect → Result return:**

```rust
// Before:
pub fn from_shards(shards_json: &str) -> Self {
    let shards: Vec<Vec<Author>> = serde_json::from_str(shards_json).expect("valid shard JSON");

// After:
pub fn from_shards(shards_json: &str) -> Result<Self, serde_json::Error> {
    let shards: Vec<Vec<Author>> = serde_json::from_str(shards_json)?;
```

Update all callers of `AuthorStore::from_shards` (should be just `lib.rs:init`):

```rust
// lib.rs before wasm wrapper:
pub fn init(shards_json: &str, rankings_json: &str) {
    let store = AuthorStore::from_shards(shards_json);
    // ...
}

// After — propagate or handle error:
pub fn init(shards_json: &str, rankings_json: &str) {
    let store = match AuthorStore::from_shards(shards_json) {
        Ok(s) => s,
        Err(e) => { wasm_bindgen::prelude::console_error!("from_shards failed: {}", e); return; }
    };
    // ...
}
```

- [ ] **Verify with cargo test:**

```bash
cargo test 2>&1 | tail -20
```

Expected: All tests passing.

### Task 10: Add rateLimitedFetch and categoryLabel tests

**Files:**
- Create: `src/lib/utils/db/rate-limit.test.ts`
- Create: `src/lib/utils/categories.test.ts`

- [ ] **Create `src/lib/utils/db/rate-limit.test.ts`:**

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

// We test the underlying logic by importing rateLimitedFetch.
// We mock global fetch.
beforeEach(() => {
	vi.restoreAllMocks();
});

describe("rateLimitedFetch", () => {
	it("returns response on success", async () => {
		const mockResponse = new Response(JSON.stringify({ ok: true }), { status: 200 });
		globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

		// Import dynamically to get fresh module state
		const { rateLimitedFetch } = await import("./rate-limit");
		const res = await rateLimitedFetch("https://example.com/test");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.ok).toBe(true);
	});

	it("retries on 429 then succeeds", async () => {
		let attempts = 0;
		globalThis.fetch = vi.fn().mockImplementation(async () => {
			attempts++;
			if (attempts === 1) {
				return new Response(null, { status: 429, headers: { "Retry-After": "0" } });
			}
			return new Response(JSON.stringify({ ok: true }), { status: 200 });
		});

		const { rateLimitedFetch } = await import("./rate-limit");
		const res = await rateLimitedFetch("https://example.com/retry-test");
		expect(res.status).toBe(200);
		expect(attempts).toBe(2);
	});

	it("throws SEARCH_BUSY after exhausting retries", async () => {
		globalThis.fetch = vi.fn().mockResolvedValue(
			new Response(null, { status: 429, headers: { "Retry-After": "0" } })
		);

		const { rateLimitedFetch } = await import("./rate-limit");
		await expect(rateLimitedFetch("https://example.com/busy")).rejects.toThrow("SEARCH_BUSY");
	});
});
```

- [ ] **Create `src/lib/utils/categories.test.ts`:**

```ts
import { describe, it, expect } from "vitest";
import { categoryLabel } from "./categories";

describe("categoryLabel", () => {
	it("returns label for known category", () => {
		expect(categoryLabel("cs.AI")).toBe("Artificial Intelligence");
	});

	it("returns id as fallback for unknown category", () => {
		expect(categoryLabel("zz.UNKNOWN")).toBe("zz.UNKNOWN");
	});

	it("handles empty string", () => {
		expect(categoryLabel("")).toBe("");
	});
});
```

- [ ] **Run tests:**

```bash
npx vitest run src/lib/utils/db/rate-limit.test.ts src/lib/utils/categories.test.ts 2>&1
```

Expected: All tests passing.

### Task 11: Add #[cfg(test)] blocks to arxcheck crate

**Files:**
- Modify: `crates/arxcheck/src/checks/edges.rs`
- Modify: `crates/arxcheck/src/checks/graph.rs`
- Modify: `crates/arxcheck/src/checks/shard.rs`
- Modify: `crates/arxcheck/src/checks/xref.rs`

- [ ] **Add test module to edges.rs:**

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use crate::CheckViolation;

    fn sample_edges() -> Vec<serde_json::Value> {
        vec![
            serde_json::json!({"source": "node_a", "target": "node_b", "weight": 5}),
            serde_json::json!({"source": "node_b", "target": "node_c", "weight": 3}),
        ]
    }

    #[test]
    fn test_valid_edges() {
        let check = EdgesCheck;
        let violations = check.run(&serde_json::json!({"edges": sample_edges()}));
        assert!(violations.is_empty());
    }

    #[test]
    fn test_missing_edges_field() {
        let check = EdgesCheck;
        let violations = check.run(&serde_json::json!({}));
        assert!(!violations.is_empty());
        assert!(violations.iter().any(|v| v.message.contains("edges")));
    }
}
```

- [ ] **Add test module to graph.rs** (similar pattern — test with valid node/edge data, test with missing data).

- [ ] **Add test module to shard.rs** (test with valid shard data, test with corrupt data).

- [ ] **Add test module to xref.rs** (test cross-reference validation with known-good and known-bad ID pairs).

- [ ] **Run tests:**

```bash
cargo test -p arxcheck 2>&1 | tail -30
```

Expected: All tests passing.

### Task 12: Extract magic number constants

**Files:**
- Modify: `src/lib/utils/db/search.ts`
- Modify: `src/lib/utils/db/suggest.ts`

- [ ] **Extract PAGE_LIMIT constant in search.ts:**

At the top of the file, add:
```ts
const PAGE_LIMIT = 30;
```

Replace all `?? 30` occurrences:
```ts
// search.ts:107
const limit = options?.limit ?? PAGE_LIMIT;

// search.ts:140
const limit = opts?.limit ?? PAGE_LIMIT;
```

- [ ] **Extract timeout constants in suggest.ts:**

At the top of the file, add:
```ts
const PREFETCH_TIMEOUT_MS = 5000;
```

Replace usage on lines 203/205 with `PREFETCH_TIMEOUT_MS`.

- [ ] **Verify build:**

```bash
npx vite build 2>&1 | head -30
```

Expected: No errors.
