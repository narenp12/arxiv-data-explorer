# Codebase Audit Remediation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute all 7 remediation items from the codebase audit across 3 parallel-capable workstreams

**Architecture:** Three workstreams running in parallel where possible. WS1 (housekeeping) and WS2 (Rust analysis) run simultaneously. WS3 (quality — tests + refactor) waits on WS2's Rust decision. Within WS3, tests precede refactoring.

**Tech Stack:** TypeScript (Vitest), Python (Daft), Rust (arxcheck/arxwasm), SvelteKit, jCodemunch

## Global Constraints

- All 51 existing tests must continue to pass
- `npm run check` must report 0 errors, 0 warnings
- No behavioural changes during `db.ts` refactor — extract only, no logic changes
- `~/.claude/CLAUDE.md` is the global agent config; edits affect all projects

---

### Task 1: Delete Confirmed Dead Scripts

**Files:**
- Delete: `scripts/build_trends.py`
- Delete: `scripts/utils.py`
- Delete: `scripts/postbuild.mjs`
- Delete: `scripts/requirements.txt`

**Interfaces:**
- Consumes: (none)
- Produces: (none — cleanup only)

- [ ] **Step 1: Delete the four dead files**

```bash
rm scripts/build_trends.py scripts/utils.py scripts/postbuild.mjs scripts/requirements.txt
```

- [ ] **Step 2: Run tests to confirm nothing broke**

```bash
npm test
```
Expected: all 51 tests pass

- [ ] **Step 3: Run typecheck to confirm nothing broke**

```bash
npm run check
```
Expected: 0 errors, 0 warnings

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete dead scripts (build_trends, utils, postbuild, requirements)"
```

---

### Task 2: Right-size ~/.claude/CLAUDE.md

**Files:**
- Modify: `~/.claude/CLAUDE.md`

**Interfaces:**
- Consumes: (none)
- Produces: (none — config only)

- [ ] **Step 1: Read current ~/.claude/CLAUDE.md**

```bash
cat ~/.claude/CLAUDE.md
```

- [ ] **Step 2: Replace content with minimal one-liner + user preferences**

Replace the entire file with:
```markdown
Call jcodemunch_guide and strictly follow its instructions.

Always use jCodemunch-MCP tools for code navigation. Never fall back to Read, Grep, Glob, or Bash for code exploration — use the Read tool only when you need to edit a file.

Session start: resolve_repo, then suggest_queries. Before edits: get_file_outline, get_symbol_source.
After edits: register_edit to re-index.

Keep responses under 4 lines unless detail is requested.
```

- [ ] **Step 3: Verify file size**

```bash
wc -c ~/.claude/CLAUDE.md
```
Expected: under 500 bytes (saves ~2000 tokens vs previous 965-line file)

---

### Task 3: Add Layer Rules to .jcodemunch.jsonc

**Files:**
- Modify: `.jcodemunch.jsonc`

**Interfaces:**
- Consumes: (none)
- Produces: `jcodemunch_get_layer_violations` returns active rules

- [ ] **Step 1: Read current .jcodemunch.jsonc**

```bash
cat .jcodemunch.jsonc
```

- [ ] **Step 2: Add `architecture.layers` block**

If `.jcodemunch.jsonc` exists, add at the top level:
```jsonc
{
  "architecture": {
    "layers": [
      {
        "name": "utils",
        "paths": ["src/lib/utils", "src/lib/stores", "src/lib/authors"],
        "may_not_import": ["src/routes"]
      },
      {
        "name": "scripts",
        "paths": ["scripts"],
        "may_not_import": ["src", "crates"]
      },
      {
        "name": "crates",
        "paths": ["crates"],
        "may_not_import": ["src", "scripts"]
      }
    ]
  }
}
```

Merge with existing content — do not overwrite other settings.

- [ ] **Step 3: Verify layer rules are detected**

```bash
# Use jcodemunch_get_layer_violations to confirm rules are loaded
```
Expected: returns `layer_count: 3` with 0 violations

- [ ] **Step 4: Commit**

```bash
git add .jcodemunch.jsonc
git commit -m "chore: add architecture layer rules to jcodemunch config"
```

---

### Task 4: Re-index Repository

**Files:**
- (none — index only)

**Interfaces:**
- Consumes: (none)
- Produces: Index matches HEAD at `c917e9c`

- [ ] **Step 1: Re-index the local folder**

Use `index_folder` on the repo root to catch up from the stale SHA.

- [ ] **Step 2: Verify index matches HEAD**

Use `get_repo_health` or `resolve_repo` to confirm staleness warning is gone.

---

### Task 5: Rust Crate Audit — Analysis Dump

**Files:**
- Read-only: `crates/arxcheck/` (all files)
- Read-only: `crates/arxwasm/` (all files)
- Read-only: `src/lib/authors/wasm-search.ts`
- Read-only: `Cargo.toml` files, `package.json` scripts

**Interfaces:**
- Consumes: (none)
- Produces: Markdown summary for user decision

- [ ] **Step 1: Read all Rust source files in crates/arxcheck**

```bash
ls -la crates/arxcheck/src/
cat crates/arxcheck/src/bin/arxcheck.rs
cat crates/arxcheck/src/lib.rs
cat crates/arxcheck/src/wasm.rs
cat crates/arxcheck/src/checks/mod.rs
cat crates/arxcheck/src/checks/api_contract.rs
cat crates/arxcheck/src/checks/edges.rs
cat crates/arxcheck/src/checks/graph.rs
cat crates/arxcheck/src/checks/shard.rs
cat crates/arxcheck/src/checks/xref.rs
```

- [ ] **Step 2: Read all Rust source files in crates/arxwasm**

```bash
ls -la crates/arxwasm/src/
cat crates/arxwasm/src/lib.rs
cat crates/arxwasm/src/data.rs
cat crates/arxwasm/src/normalize.rs
cat crates/arxwasm/src/ranker.rs
cat crates/arxwasm/src/trie.rs
cat crates/arxwasm/src/trigram.rs
```

- [ ] **Step 3: Read the WASM bridge**

```bash
cat src/lib/authors/wasm-search.ts
```

- [ ] **Step 4: Check what depends on each crate**

```bash
# Check Cargo.toml for workspace membership
cat Cargo.toml 2>/dev/null || echo "No workspace Cargo.toml"
cat crates/arxcheck/Cargo.toml
cat crates/arxwasm/Cargo.toml

# Check if prebuild script references it
grep -r "arxcheck\|arxwasm" package.json
```

- [ ] **Step 5: Present findings to user as:**

```markdown
## Rust Crate Audit

### crates/arxcheck/
- **Purpose:** Validates data-file integrity — checks API contract compliance,
  causal edge structures, category graph references, author shard formats,
  cross-reference correctness.
- **Build:** Referenced in `package.json` prebuild script
- **WASM bindings:** Exists in `wasm.rs` but NO TypeScript code imports them.
- **Dependents:** None at runtime. Only called by build step.
- **Verdict options:** Keep (build-time validation) / Delete (validation is
  unused / redundant with Python pipeline)

### crates/arxwasm/
- **Purpose:** Author search engine — trie-based prefix search + trigram-based
  fuzzy matching with ranking.
- **WASM bindings:** `src/lib/authors/wasm-search.ts` wraps the crate, but
  NO Svelte route imports it.
- **Dependents:** `wasm-search.ts` exists but is dead code (unreached from
  any route or component).
- **Verdict options:** Keep (planned feature, search is incomplete) / Delete
  (not wired up, wasm-build complexity not worth it)
```

- [ ] **Step 6: Present findings and await user decision**

The user chooses one of:
1. Keep both crates → skip to Task 6
2. Delete both → continue to Task 5b
3. Keep arxwasm, delete arxcheck → continue to Task 5b

---

### Task 5b: Execute Rust Decision

**Only if Rust audit decides to delete crates. If keeping both, skip this task.**

**Files:**
- Delete: `crates/arxcheck/` (if deleting)
- Delete: `crates/arxwasm/` (if deleting)
- Delete: `src/lib/authors/wasm-search.ts` (if deleting arxwasm)
- Modify: `package.json` (remove prebuild script if arxcheck deleted)
- Modify: `.gitignore` (if needed)
- Delete: `src/lib/authors/wasm-search.test.ts` (if deleting arxwasm)

**Interfaces:**
- Consumes: user decision from Task 5
- Produces: cleaned-up crate structure

- [ ] **Step 1: Delete selected crate directories**

```bash
# If deleting arxcheck:
rm -rf crates/arxcheck

# If deleting arxwasm + bridge:
rm -rf crates/arxwasm
rm src/lib/authors/wasm-search.ts
```

- [ ] **Step 2: Update package.json prebuild if arxcheck deleted**

Remove or update the prebuild script that runs `cargo run --manifest-path crates/arxcheck/...`.

- [ ] **Step 3: Run tests to confirm nothing broke**

```bash
npm test && npm run check
```
Expected: all tests pass, 0 errors/warnings

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove unused Rust crates per audit decision"
```

---

### Task 6: Write Tests for openalex.ts

**Files:**
- Create: `src/lib/utils/openalex.test.ts`
- Modify: (none — tests only, production code stays unchanged)

**Interfaces:**
- Consumes: `openalex.ts` exports — `rateLimitedFetch`, `openalexIdFromUrl`,
  `fetchConcepts`, `normalizeOpenAlexId`, `arxivIdFromDoi`, `parseWork`,
  `fetchAuthorProfile`, `fetchReferences`, `fetchCitations`, `fetchRelatedWorks`
- Produces: 90%+ statement coverage on `openalex.ts`

- [ ] **Step 1: Write the test file**

```typescript
// src/lib/utils/openalex.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';

// We test the pure functions directly and mock fetch for the network functions.

describe('openalexIdFromUrl', () => {
  it('extracts ID from a full OpenAlex URL', () => {
    // Implementation to be determined based on actual function
  });

  it('returns null for invalid URLs', () => {
    // Implementation to be determined based on actual function
  });
});

describe('normalizeOpenAlexId', () => {
  // Tests for ID normalization
});

describe('arxivIdFromDoi', () => {
  // Tests for DOI → arxiv ID extraction
});

describe('parseWork', () => {
  // Tests for OpenAlex API response → internal format mapping
});

describe('rateLimitedFetch', () => {
  // Tests for rate limiting, queueing, in-flight dedup
});

describe('fetchConcepts', () => {
  // Integration test with mocked fetch
});

describe('fetchAuthorProfile', () => {
  // Integration test with mocked fetch
});

describe('fetchReferences', () => {
  // Integration test with mocked fetch
});

describe('fetchCitations', () => {
  // Integration test with mocked fetch
});

describe('fetchRelatedWorks', () => {
  // Integration test with mocked fetch
});
```

- [ ] **Step 2: Run test to confirm it fails (no existing tests)**

```bash
npm test -- src/lib/utils/openalex.test.ts
```
Expected: tests exist but some fail (placeholder tests need real assertions)

- [ ] **Step 3-~10: Fill in each describe block with real tests**

For each function, write tests covering:
- Happy path (typical input)
- Edge cases (null, undefined, malformed input)
- Error handling (network failure, malformed response)
- Rate limiting (timing, queue ordering, dedup)

- [ ] **Step 11: Run all tests**

```bash
npm test
```
Expected: all 51 + new openalex tests pass

- [ ] **Step 12: Commit**

```bash
git add src/lib/utils/openalex.test.ts
git commit -m "test: add coverage for openalex.ts"
```

---

### Task 7: Write Tests for db.ts Internals

**Files:**
- Modify: `src/lib/utils/db.test.ts` (extend existing test file)

**Interfaces:**
- Consumes: `db.ts` — `sanitiseYearRange`, `sanitiseMinCites`, `getCached`,
  `setCached`, `clearSearchCache`, `rateLimitedFetchOnce`, `rateLimitedFetch`,
  `arxivId`, `authorList`, `getProp`, `buildSearchUrl`, `parseSearchResponse`,
  `parseArxivTotal`, `rateLimitedFetch`
- Produces: 90%+ statement coverage on `db.ts`

- [ ] **Step 1: Add test blocks to db.test.ts**

Append to `src/lib/utils/db.test.ts`:

```typescript
describe('sanitiseYearRange', () => {
  it('handles typical range', () => { /* ... */ });
  it('handles undefined values', () => { /* ... */ });
  it('handles reversed years', () => { /* ... */ });
});

describe('sanitiseMinCites', () => {
  it('handles valid numbers', () => { /* ... */ });
  it('handles undefined', () => { /* ... */ });
});

describe('getCached / setCached / clearSearchCache', () => {
  it('stores and retrieves values', () => { /* ... */ });
  it('respects cache limit', () => { /* ... */ });
  it('clears all entries', () => { /* ... */ });
});

describe('rateLimitedFetchOnce', () => {
  it('fetches with rate limiting', () => { /* ... */ });
  it('deduplicates in-flight requests', () => { /* ... */ });
});

describe('arxivId', () => {
  it('extracts ID from various arXiv URL formats', () => { /* ... */ });
});

describe('authorList', () => {
  it('parses author names from XML', () => { /* ... */ });
});

describe('buildSearchUrl', () => {
  it('constructs correct URL with parameters', () => { /* ... */ });
  it('handles all parameter combinations', () => { /* ... */ });
});

describe('parseSearchResponse', () => {
  it('parses valid XML response', () => { /* ... */ });
  it('handles empty result set', () => { /* ... */ });
});

describe('parseArxivTotal', () => {
  it('extracts total results count', () => { /* ... */ });
});
```

- [ ] **Step 2: Run all tests**

```bash
npm test
```
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add src/lib/utils/db.test.ts
git commit -m "test: add coverage for db.ts internals"
```

---

### Task 8: (Conditional) Write Tests for wasm-search.ts

**Only if Rust audit decides to keep crates/arxwasm.**

**Files:**
- Create: `src/lib/authors/wasm-search.test.ts`

**Interfaces:**
- Consumes: `wasm-search.ts` — `loadAuthorSearch`, `getInitError`,
  `searchAuthors`, `getStats`
- Produces: test coverage for WASM bridge

- [ ] **Step 1: Create test file**

```typescript
// src/lib/authors/wasm-search.test.ts
import { describe, it, expect } from 'vitest';

describe('loadAuthorSearch', () => {
  // Mock WASM init
});

describe('searchAuthors', () => {
  // Test with mocked WASM search function
});

describe('getStats', () => {
  // Test stats retrieval
});
```

- [ ] **Step 2: Run tests**

```bash
npm test
```
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add src/lib/authors/wasm-search.test.ts
git commit -m "test: add coverage for wasm-search.ts"
```

---

### Task 9: Refactor db.ts into Focused Modules

**Files:**
- Create: `src/lib/utils/db/cache.ts`
- Create: `src/lib/utils/db/rate-limit.ts`
- Create: `src/lib/utils/db/search.ts`
- Create: `src/lib/utils/db/detail.ts`
- Create: `src/lib/utils/db/index.ts`
- Modify: `src/lib/utils/db.ts` → deleted (replaced by new modules)
- Modify: `src/lib/utils/db.test.ts` → update imports to new modules
- Modify: (any file importing `./db` → `./db/index` where needed)

**Interfaces:**
- Consumes: existing `db.ts` internals (extract, don't change)
- Produces: `src/lib/utils/db/index.ts` re-exports the same public API

- [ ] **Step 1: Create `db/cache.ts`**

Extract:
- `CACHE_LIMIT`, `searchCache`, `detailCache`
- `getCached()`, `setCached()`, `clearSearchCache()`

```typescript
export const CACHE_LIMIT = 50;

interface CacheEntry<T> { data: T; timestamp: number }

export function getCached<T>(cache: Map<string, CacheEntry<T>>, key: string): T | null { /* ... */ }
export function setCached<T>(cache: Map<string, CacheEntry<T>>, key: string, data: T): void { /* ... */ }
export function clearSearchCache(): void { /* ... */ }
```

- [ ] **Step 2: Create `db/rate-limit.ts`**

Extract:
- `RATE_LIMIT_MS`, `lastRequest`, `requestQueue`, `inFlight`
- `rateLimitedFetchOnce()`, `rateLimitedFetch()`

```typescript
export const RATE_LIMIT_MS = 1000;

export async function rateLimitedFetch(url: string): Promise<Response> { /* ... */ }
```

- [ ] **Step 3: Create `db/search.ts`**

Extract:
- `SEARCH_FIELDS`, `API_BASE`, `ARXIV_API_BASE`
- `sanitiseYearRange()`, `sanitiseFieldOfStudy()`, `sanitiseMinCites()`
- `buildSearchUrl()`, `parseSearchResponse()`, `parseArxivResponse()`, `parseArxivTotal()`
- `searchPapers()`, `searchArxivCategory()`

- [ ] **Step 4: Create `db/detail.ts`**

Extract:
- `DETAIL_FIELDS`
- `arxivId()`, `authorList()`, `getProp()`
- `getPaperDetail()`

- [ ] **Step 5: Create `db/index.ts`**

Re-export all public API so existing imports of `./db` still work:

```typescript
export { searchPapers, searchArxivCategory, PaperResult, ... } from './search';
export { getPaperDetail, ... } from './detail';
export { rateLimitedFetch, ... } from './rate-limit';
export { getCached, setCached, clearSearchCache, ... } from './cache';
export { WasmAPI, ensureChecker, ... } from './checker';
export { categoryLabel } from '../categories';
```

- [ ] **Step 6: Delete `db.ts`**

```bash
rm src/lib/utils/db.ts
```

- [ ] **Step 7: Update test imports**

In `src/lib/utils/db.test.ts`, change:
```typescript
import { ... } from './db';
```
to:
```typescript
import { ... } from './db/index';
```

- [ ] **Step 8: Check for other files importing `./db` or `./db.ts`**

```bash
grep -r "from ['\"]\.\/db['\"]" src/ --include='*.ts' --include='*.svelte'
grep -r "from ['\"]\.\/db\.ts['\"]" src/ --include='*.ts' --include='*.svelte'
```

Update any imports to point to `./db/index`.

- [ ] **Step 9: Run all tests**

```bash
npm test
```
Expected: all tests pass

- [ ] **Step 10: Run typecheck**

```bash
npm run check
```
Expected: 0 errors, 0 warnings

- [ ] **Step 11: Commit**

```bash
git add src/lib/utils/
git commit -m "refactor: split db.ts into cache, rate-limit, search, and detail modules"
```
