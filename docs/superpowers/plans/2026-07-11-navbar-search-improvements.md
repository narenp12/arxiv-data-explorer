# Navbar Search Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement.

**Goal:** Improve navbar search quality with WASM author fuzzy matching, ranked categories, more paper results, and wider dropdown.

**Architecture:** Two files changed. `wasm-search.ts` gets an `isReady()` export. `UnifiedSearch.svelte` integrates WASM with progressive JSON fallback, replaces `includes()` with scoring for categories, increases paper limit, and widens layout.

**Tech Stack:** Svelte 5 (runes), TypeScript, Rust WASM (arxwasm), Semantic Scholar API

---

### Task 1: Add `isReady()` to wasm-search.ts

**Files:**
- Modify: `src/lib/authors/wasm-search.ts:3` (add `isReady()`)

**Interfaces:**
- Produces: `export function isReady(): boolean` — returns current WASM init state

- [ ] **Step 1: Add isReady() function**

```typescript
// Add after `ready` variable declaration (line 3)

export function isReady(): boolean {
  return ready;
}
```

- [ ] **Step 2: Run existing tests to confirm nothing broken**

Run: `npx vitest run src/lib/authors/ -v`
Expected: Tests pass

- [ ] **Step 3: Commit**

```bash
git add src/lib/authors/wasm-search.ts
git commit -m "feat: export isReady() from wasm-search"
```

---

### Task 2: Improve UnifiedSearch.svelte

**Files:**
- Modify: `src/lib/components/UnifiedSearch.svelte`

**Interfaces:**
- Consumes: `isReady()` from Task 1, `loadAuthorSearch()`, `searchAuthors()` from `wasm-search.ts`
- Consumes: `searchPapers(q, { limit: 8 })` from `$lib/utils/db/search`

- [ ] **Step 1: Add WASM imports and state**

After existing imports (line 4), add:

```typescript
import { loadAuthorSearch, searchAuthors, isReady } from "$lib/authors/wasm-search";
```

Add state variables after existing state declarations (after line 27):

```typescript
  let wasmLoaded = $state(false);
  let wasmLoading = $state(false);
  let paperTotal = $state(0);
  let catTotal = $state(0);
  let concTotal = $state(0);
```

- [ ] **Step 2: Update onFocus to trigger WASM load**

Replace `onFocus` function (lines 53-56):

```typescript
  async function onFocus() {
    focused = true;
    ensureData();
    if (!wasmLoading && !wasmLoaded) {
      wasmLoading = true;
      try {
        await loadAuthorSearch();
        wasmLoaded = true;
        if (query.trim().length >= 2) doSearch();
      } catch {
        // fall back to includes() filtering
      }
      wasmLoading = false;
    }
  }
```

- [ ] **Step 3: Replace doSearch with improved logic**

Replace `doSearch` function (lines 87-113):

```typescript
  async function doSearch() {
    const seq = ++requestSeq;
    const q = query.trim().toLowerCase();

    // Authors: WASM if ready, else includes() fallback
    if (isReady()) {
      const wResults = searchAuthors(q, 5);
      authorResults = wResults.map(r => ({ name: r.name, papers: r.weight }));
    } else {
      authorResults = authors
        .filter(a => a.name.toLowerCase().includes(q))
        .slice(0, 5);
    }

    // Categories: ranked scoring
    const scoredCats = categories
      .map(c => ({ item: c, score: scoreCategory(c, q) }))
      .filter(x => x.score > 0)
      .sort((a, b) => b.score - a.score || b.item.papers - a.item.papers);
    catTotal = scoredCats.length;
    categoryResults = scoredCats.slice(0, 5).map(x => x.item);

    // Concepts: same as categories
    const scoredConcs = concepts
      .map(c => ({ item: c, score: scoreCategory(c, q) }))
      .filter(x => x.score > 0)
      .sort((a, b) => b.score - a.score);
    concTotal = scoredConcs.length;
    conceptResults = scoredConcs.slice(0, 5).map(x => x.item);

    if (seq !== requestSeq) return;

    // Papers: increased limit
    try {
      const res = await searchPapers(q, { limit: 8 });
      if (seq !== requestSeq) return;
      paperResults = res.results;
      paperTotal = res.total;
    } catch { /* paper search unavailable */ }

    searching = false;
  }

  function scoreCategory(item: { label: string; id: string }, q: string): number {
    const l = item.label.toLowerCase();
    const i = item.id.toLowerCase();
    const query = q.toLowerCase();
    if (l === query || i === query) return 100;
    if (l.startsWith(query) || i.startsWith(query)) return 80;
    if (l.split(/\s+/).some(w => w.startsWith(query))) return 60;
    if (l.includes(query) || i.includes(query)) return 40;
    return 0;
  }
```

- [ ] **Step 4: Update clearResults to reset new totals**

Update `clearResults` function:

```typescript
  function clearResults() {
    paperResults = [];
    paperTotal = 0;
    authorResults = [];
    categoryResults = [];
    catTotal = 0;
    conceptResults = [];
    concTotal = 0;
    selectedIndex = 0;
  }
```

- [ ] **Step 5: Widen search input**

In template (line 168), change:

```svelte
<div class="relative flex-1 max-w-[200px] focus-within:max-w-xs transition-all">
```

to:

```svelte
<div class="relative flex-1 max-w-xs focus-within:max-w-sm transition-all">
```

- [ ] **Step 6: Widen dropdown**

In template (line 185), change:

```svelte
<div class="absolute left-1/2 top-full z-50 mt-2 min-w-[360px] -translate-x-1/2 ...">
```

to:

```svelte
<div class="absolute left-1/2 top-full z-50 mt-2 min-w-[420px] -translate-x-1/2 ...">
```

- [ ] **Step 7: Add citation badge and view-all links to paper results**

Replace the paper results button block (lines 194-208) with:

```svelte
{#each paperResults as paper, i}
  <button
    role="option"
    aria-selected={selectedIndex === selOffset.papers + i}
    onclick={() => go(`/papers/${encodeURIComponent(paper.id)}`)}
    onmouseenter={() => (selectedIndex = selOffset.papers + i)}
    class="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors {selectedIndex === selOffset.papers + i ? 'bg-surface-container-high' : 'hover:bg-surface-container-high'}"
  >
    <div class="min-w-0 flex-1">
      <p class="truncate font-mono text-xs font-bold text-on-surface">{paper.title}</p>
      <p class="truncate font-mono text-[10px] text-outline">{paper.authors}</p>
    </div>
    <div class="shrink-0 text-right">
      <span class="font-mono text-[10px] text-outline">{paper.year ?? "—"}</span>
      {#if paper.citationCount > 0}
        <p class="font-mono text-[10px] text-outline/60">{paper.citationCount} cites</p>
      {/if}
    </div>
  </button>
{/each}
```

Add view-all link after the paper results each block (after line 209):

```svelte
{#if paperTotal > paperResults.length}
  <button
    onclick={() => go(`/papers?q=${encodeURIComponent(query)}`)}
    class="flex w-full items-center justify-center gap-1 rounded-md px-2 py-1.5 text-[10px] font-mono text-primary transition-colors hover:bg-surface-container-high"
  >
    View all {paperTotal} results →
  </button>
{/if}
```

- [ ] **Step 8: Add view-all links to authors section**

After the authors each block (after line 227), add:

```svelte
<button
  onclick={() => go(`/authors?q=${encodeURIComponent(query)}`)}
  class="flex w-full items-center justify-center gap-1 rounded-md px-2 py-1.5 text-[10px] font-mono text-primary transition-colors hover:bg-surface-container-high"
>
  View all results →
</button>
```

- [ ] **Step 9: Add view-all links to categories section**

After the categories each block (after line 248), add:

```svelte
{#if catTotal > categoryResults.length}
  <button
    onclick={() => go(`/trends?q=${encodeURIComponent(query)}`)}
    class="flex w-full items-center justify-center gap-1 rounded-md px-2 py-1.5 text-[10px] font-mono text-primary transition-colors hover:bg-surface-container-high"
  >
    View all {catTotal} results →
  </button>
{/if}
```

- [ ] **Step 10: Run tests**

Run: `npx vitest run src/lib/components/ -v`
Expected: All tests pass

- [ ] **Step 11: Commit**

```bash
git add src/lib/components/UnifiedSearch.svelte
git commit -m "feat: improve navbar search with WASM, scoring, wider layout"
```
