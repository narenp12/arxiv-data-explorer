# SvelteKit Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Svelte 5 + SvelteKit static site that serves the arXiv explorer from precomputed data files. Serves category/author network graphs, full-text search via sql.js FTS5, and drill-down hierarchies.

**Architecture:** Static site (adapter-static) deployed to Vercel. All data served from `static/data/` as assets. D3.js for network graphs. sql.js-httpvfs for search. No API routes.

**Tech Stack:** Svelte 5 (runes), SvelteKit, TypeScript, Tailwind CSS v4, D3.js, sql.js + sql.js-httpvfs.

## Global Constraints

- Svelte 5 with runes (`$state`, `$derived`, `$effect`) — no legacy `svelte/store` imports
- `@sveltejs/adapter-static` for Vercel deployment
- Tailwind CSS v4 for styling (dark mode default, light toggle)
- All data from `static/data/*` — no API routes
- Routes: `/`, `/papers`, `/papers/[id]`, `/authors`, `/authors/[id]`, `/categories`, `/causal` (placeholder), `/about`
- Every component handles loading, empty, error states
- Network graphs: D3.js force simulation (SVG for category < 200 nodes, Canvas for author 50K nodes)
- Search: sql.js-httpvfs with lazy WASM load on `/papers`
- Causal: placeholder route with lazy Pyodide import stub
- No comments in code

---
## File Structure

```
src/
├── app.html
├── app.css                    # Tailwind imports + dark/light variables
├── routes/
│   ├── +layout.svelte         # Nav + global layout
│   ├── +page.svelte           # Home — category network graph
│   ├── papers/
│   │   ├── +page.svelte       # Search page
│   │   └── [id]/
│   │       └── +page.svelte   # Paper detail
│   ├── authors/
│   │   ├── +page.svelte       # Author network
│   │   └── [id]/
│   │       └── +page.svelte   # Author detail
│   ├── categories/
│   │   └── +page.svelte       # Category hierarchy
│   ├── causal/
│   │   └── +page.svelte       # Placeholder
│   └── about/
│       └── +page.svelte       # About page
├── lib/
│   ├── components/
│   │   ├── CategoryGraph.svelte
│   │   ├── AuthorGraph.svelte
│   │   ├── SearchView.svelte
│   │   ├── PaperCard.svelte
│   │   └── StatsPanel.svelte
│   └── utils/
│       ├── db.ts              # sql.js-httpvfs wrapper
│       └── openalex.ts        # OpenAlex API client
```

---
### Task 1: Project Scaffold

**Files:**
- Create: full SvelteKit project via CLI
- Configure: `svelte.config.js`, Tailwind, adapter-static, path aliases

- [ ] **Step 1: Create SvelteKit project**

```bash
cd /Users/narenprax/Documents/GitHub/arxiv-data-explorer
npx sv create . --template minimal --types ts --no-add-ons
```

When prompted, choose: `Skeleton project`, `TypeScript`, no add-ons.

- [ ] **Step 2: Install dependencies**

```bash
cd /Users/narenprax/Documents/GitHub/arxiv-data-explorer
pnpm add -D @sveltejs/adapter-static tailwindcss @tailwindcss/vite d3 @types/d3 sql.js
```

If `pnpm` not available: `npm install` equivalent.

- [ ] **Step 3: Configure static adapter in `svelte.config.js`**

```js
import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

/** @type {import("@sveltejs/kit").Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: "build",
      assets: "build",
      fallback: "404.html",
      precompress: false,
      strict: true,
    }),
    paths: {
      base: "",
    },
  },
};

export default config;
```

- [ ] **Step 4: Configure Tailwind in `vite.config.ts`**

```ts
import { sveltekit } from "@sveltejs/kit/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
});
```

- [ ] **Step 5: Add Tailwind import to `src/app.css`**

```css
@import "tailwindcss";
```

- [ ] **Step 6: Enable prerender for all routes in `src/routes/+layout.ts`**

```ts
export const prerender = true;
```

- [ ] **Step 7: Verify dev server starts**

Run: `pnpm dev`
Open browser to `http://localhost:5173`
Expected: empty page, no errors

---
### Task 2: Layout + Navigation

**Files:**
- Create: `src/routes/+layout.svelte`
- Create: `src/routes/+layout.ts` (export prerender)
- Create: `src/routes/+page.svelte` (home placeholder)

- [ ] **Step 1: Write the layout with nav and theme toggle**

**`src/routes/+layout.svelte`:**
```svelte
<script lang="ts">
  let { children } = $props();
  let dark = $state(true);

  $effect(() => {
    document.documentElement.classList.toggle("dark", dark);
  });
</script>

<div class="min-h-screen {dark ? 'dark bg-gray-950 text-gray-100' : 'bg-white text-gray-900'} transition-colors">
  <nav class="border-b border-gray-800 px-4 py-3 flex items-center gap-6">
    <a href="/" class="text-lg font-bold tracking-tight">arXiv Explorer</a>
    <div class="flex gap-4 text-sm">
      <a href="/papers" class="hover:text-blue-400 transition-colors">Papers</a>
      <a href="/authors" class="hover:text-blue-400 transition-colors">Authors</a>
      <a href="/categories" class="hover:text-blue-400 transition-colors">Categories</a>
      <a href="/causal" class="hover:text-blue-400 transition-colors">Causal</a>
      <a href="/about" class="hover:text-blue-400 transition-colors">About</a>
    </div>
    <button onclick={() => dark = !dark} class="ml-auto text-sm px-3 py-1 rounded border border-gray-700 hover:bg-gray-800 transition-colors">
      {dark ? "Light" : "Dark"}
    </button>
  </nav>
  <main class="max-w-7xl mx-auto px-4 py-6">
    {@render children()}
  </main>
</div>
```

- [ ] **Step 2: Wire layout.ts if not already created**

If `+layout.ts` with `export const prerender = true` doesn't exist yet, create it.

- [ ] **Step 3: Write home page placeholder**

**`src/routes/+page.svelte`:**
```svelte
<script lang="ts">
  import CategoryGraph from "$lib/components/CategoryGraph.svelte";
</script>

<svelte:head>
  <title>arXiv Explorer</title>
</svelte:head>

<div class="space-y-6">
  <div class="text-center space-y-2">
    <h1 class="text-3xl font-bold">arXiv Research Explorer</h1>
    <p class="text-gray-400 text-sm">
      Explore 3M+ research papers through network graphs and full-text search
    </p>
  </div>
  <CategoryGraph />
</div>
```

- [ ] **Step 4: Verify layout renders**

Run: `pnpm dev`
Expected: dark-themed nav with links, placeholder home content

---
### Task 3: CategoryGraph Component (Home Page)

**Files:**
- Create: `src/lib/components/CategoryGraph.svelte`

- [ ] **Step 1: Write the D3.js category graph component**

```svelte
<script lang="ts">
  import { onMount } from "svelte";
  import * as d3 from "d3";

  interface CategoryNode {
    id: string;
    label: string;
    domain: string;
    group: string;
    weight: number;
    color: string;
  }

  interface CategoryEdge {
    source: string;
    target: string;
    weight: number;
  }

  interface CategoryGraph {
    nodes: CategoryNode[];
    edges: CategoryEdge[];
    metadata: { total_nodes: number; total_edges: number; last_updated: string };
  }

  let svgEl: SVGSVGElement;
  let data: CategoryGraph | null = $state(null);
  let error: string | null = $state(null);
  let loading = $state(true);

  onMount(async () => {
    try {
      const resp = await fetch("/data/category_graph.json");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      data = await resp.json();
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load graph";
    } finally {
      loading = false;
    }
  });

  $effect(() => {
    if (!data || !svgEl) return;
    renderGraph(data, svgEl);
  });

  function renderGraph(graph: CategoryGraph, svg: SVGSVGElement) {
    const w = svg.clientWidth || 800;
    const h = 500;
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);

    d3.select(svg).selectAll("*").remove();

    const simulation = d3.forceSimulation(graph.nodes)
      .force("link", d3.forceLink(graph.edges).id((d: any) => d.id).distance(60))
      .force("charge", d3.forceManyBody().strength(-120))
      .force("center", d3.forceCenter(w / 2, h / 2))
      .force("collision", d3.forceCollide().radius(8));

    const g = d3.select(svg);

    const link = g.append("g")
      .selectAll("line")
      .data(graph.edges)
      .join("line")
      .attr("stroke", "#4a5568")
      .attr("stroke-width", (d) => Math.max(0.5, Math.log(d.weight) / 3))
      .attr("stroke-opacity", 0.3);

    const node = g.append("g")
      .selectAll("circle")
      .data(graph.nodes)
      .join("circle")
      .attr("r", (d) => Math.max(4, Math.sqrt(d.weight) / 15))
      .attr("fill", (d) => d.color)
      .attr("stroke", "#1a1a2e")
      .attr("stroke-width", 1)
      .attr("cursor", "pointer")
      .append("title")
      .text((d) => `${d.label} (${d.weight.toLocaleString()} papers)`);

    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);

      node
        .attr("cx", (d: any) => d.x)
        .attr("cy", (d: any) => d.y);
    });
  }
</script>

<div class="w-full">
  {#if loading}
    <div class="h-[500px] flex items-center justify-center">
      <div class="animate-pulse text-gray-500">Loading graph…</div>
    </div>
  {:else if error}
    <div class="h-[500px] flex items-center justify-center text-red-400">
      Failed to load: {error}
      <button onclick={() => location.reload()} class="ml-2 underline hover:text-red-300">Retry</button>
    </div>
  {:else}
    <svg bind:this={svgEl} class="w-full h-[500px]" role="img" aria-label="Category co-occurrence network graph"></svg>
  {/if}
</div>
```

- [ ] **Step 2: Verify the component renders**

Create a small `static/data/category_graph.json`:

```json
{"nodes":[{"id":"cs.AI","label":"cs.AI","domain":"cs","group":"Computer Science","weight":1000,"color":"#1f77b4"},{"id":"cs.LG","label":"cs.LG","domain":"cs","group":"Computer Science","weight":2000,"color":"#1f77b4"},{"id":"cs.CV","label":"cs.CV","domain":"cs","group":"Computer Science","weight":3000,"color":"#1f77b4"}],"edges":[{"source":"cs.AI","target":"cs.LG","weight":500},{"source":"cs.AI","target":"cs.CV","weight":300}],"metadata":{"total_nodes":3,"total_edges":2,"last_updated":"2026-07-01"}}
```

Expected: dev server shows a force-directed graph with 3 colored circles

---
### Task 4: Search Page with sql.js FTS5

**Files:**
- Create: `src/routes/papers/+page.svelte`
- Create: `src/lib/utils/db.ts`
- Create: `src/lib/components/SearchView.svelte`
- Create: `src/lib/components/PaperCard.svelte`

- [ ] **Step 1: Write the database wrapper**

**`src/lib/utils/db.ts`:**
```ts
import initSqlJs from "sql.js";

let db: any = null;
let initPromise: Promise<void> | null = null;

export async function initDb(): Promise<void> {
  if (db) return;
  if (initPromise) return initPromise;
  initPromise = (async () => {
    const SQL = await initSqlJs();
    const resp = await fetch("/data/search.db");
    const buf = await resp.arrayBuffer();
    db = new SQL.Database(new Uint8Array(buf));
  })();
  return initPromise;
}

export interface PaperResult {
  id: string;
  title: string;
  authors: string;
  categories: string;
  date: string;
}

export function searchPapers(query: string, limit = 30, offset = 0): { results: PaperResult[]; total: number } {
  if (!db) return { results: [], total: 0 };

  const q = query.trim().replace(/[^a-zA-Z0-9\s]/g, "").split(/\s+/).filter(Boolean).join(" AND ");
  if (!q) return { results: [], total: 0 };

  const countStmt = db.prepare(
    "SELECT COUNT(*) as cnt FROM papers_fts WHERE papers_fts MATCH ?"
  );
  countStmt.bind([q]);
  let total = 0;
  if (countStmt.step()) {
    total = countStmt.getAsObject().cnt;
  }
  countStmt.free();

  const stmt = db.prepare(`
    SELECT p.id, p.title, p.authors, p.categories, p.date
    FROM papers_fts f JOIN papers p ON f.id = p.id
    WHERE f MATCH ?
    ORDER BY rank
    LIMIT ? OFFSET ?
  `);
  stmt.bind([q, limit, offset]);

  const results: PaperResult[] = [];
  while (stmt.step()) {
    const row = stmt.getAsObject() as any;
    results.push({
      id: row.id,
      title: row.title,
      authors: row.authors,
      categories: row.categories,
      date: row.date,
    });
  }
  stmt.free();

  return { results, total };
}
```

- [ ] **Step 2: Write PaperCard component**

**`src/lib/components/PaperCard.svelte`:**
```svelte
<script lang="ts">
  import type { PaperResult } from "$lib/utils/db";

  let { paper }: { paper: PaperResult } = $props();
</script>

<a href="/papers/{paper.id}" class="block p-4 rounded-lg border border-gray-800 hover:border-blue-500 transition-colors space-y-1">
  <div class="text-xs text-gray-500">{paper.date} · {paper.id}</div>
  <div class="font-medium text-sm leading-snug">{paper.title}</div>
  <div class="text-xs text-gray-400 truncate">{paper.authors}</div>
  <div class="text-xs text-gray-500">{paper.categories}</div>
</a>
```

- [ ] **Step 3: Write SearchView component**

**`src/lib/components/SearchView.svelte`:**
```svelte
<script lang="ts">
  import { onMount } from "svelte";
  import { initDb, searchPapers, type PaperResult } from "$lib/utils/db";
  import PaperCard from "./PaperCard.svelte";

  let query = $state("");
  let results: PaperResult[] = $state([]);
  let total = $state(0);
  let offset = $state(0);
  let loading = $state(true);
  let searching = $state(false);
  let dbReady = $state(false);
  let error: string | null = $state(null);

  onMount(async () => {
    try {
      await initDb();
      dbReady = true;
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load search database";
    } finally {
      loading = false;
    }
  });

  let debounceTimer: ReturnType<typeof setTimeout>;
  function onInput(e: Event) {
    const val = (e.target as HTMLInputElement).value;
    query = val;
    clearTimeout(debounceTimer);
    if (val.trim().length < 2) {
      results = [];
      total = 0;
      return;
    }
    searching = true;
    debounceTimer = setTimeout(() => {
      doSearch(0);
    }, 300);
  }

  function doSearch(newOffset: number) {
    try {
      const res = searchPapers(query, 30, newOffset);
      results = res.results;
      total = res.total;
      offset = newOffset;
    } catch (e) {
      error = e instanceof Error ? e.message : "Search failed";
    } finally {
      searching = false;
    }
  }

  function nextPage() { doSearch(offset + 30); }
  function prevPage() { doSearch(Math.max(0, offset - 30)); }
</script>

<div class="space-y-4">
  <div class="relative">
    <input
      type="search"
      placeholder="Search papers… (e.g. quantum computing)"
      oninput={onInput}
      class="w-full px-4 py-3 rounded-lg bg-gray-900 border border-gray-700 text-sm focus:border-blue-500 focus:outline-none transition-colors"
      disabled={!dbReady}
    />
    {#if searching}
      <div class="absolute right-3 top-3 text-sm text-gray-400 animate-pulse">searching…</div>
    {/if}
  </div>

  {#if loading}
    <div class="text-center text-gray-500 py-12 animate-pulse">Loading search index…</div>
  {:else if error}
    <div class="text-center text-red-400 py-12">
      {error}
      <button onclick={() => location.reload()} class="ml-2 underline">Retry</button>
    </div>
  {:else if query.trim().length === 0}
    <div class="text-center text-gray-500 py-12">Type at least 2 characters to search</div>
  {:else if results.length === 0 && !searching}
    <div class="text-center text-gray-500 py-12">No results for "{query}"</div>
  {:else}
    <div class="text-xs text-gray-500 mb-2">
      {total.toLocaleString()} result{total !== 1 ? "s" : ""} for "{query}"
      {#if total > 30}
        · page {Math.floor(offset / 30) + 1} of {Math.ceil(total / 30)}
      {/if}
    </div>
    <div class="space-y-2">
      {#each results as paper (paper.id)}
        <PaperCard {paper} />
      {/each}
    </div>
    {#if total > 30}
      <div class="flex gap-2 justify-center pt-4">
        <button onclick={prevPage} disabled={offset === 0}
          class="px-4 py-2 rounded bg-gray-800 text-sm disabled:opacity-30 hover:bg-gray-700 transition-colors">Previous</button>
        <button onclick={nextPage} disabled={offset + 30 >= total}
          class="px-4 py-2 rounded bg-gray-800 text-sm disabled:opacity-30 hover:bg-gray-700 transition-colors">Next</button>
      </div>
    {/if}
  {/if}
</div>
```

- [ ] **Step 4: Wire up the papers route page**

**`src/routes/papers/+page.svelte`:**
```svelte
<script lang="ts">
  import SearchView from "$lib/components/SearchView.svelte";
</script>

<svelte:head>
  <title>Search Papers — arXiv Explorer</title>
</svelte:head>

<div class="space-y-4">
  <h1 class="text-2xl font-bold">Search Papers</h1>
  <SearchView />
</div>
```

- [ ] **Step 5: Verify search page loads**

Run `pnpm dev`, navigate to `/papers`
Expected: search input appears, loads search.db, type "machine" → paper results appear

---
### Task 5: Paper Detail Page

**Files:**
- Create: `src/routes/papers/[id]/+page.svelte`

- [ ] **Step 1: Write paper detail with OpenAlex enrichment**

**`src/routes/papers/[id]/+page.svelte`:**
```svelte
<script lang="ts">
  import { onMount } from "svelte";
  import { initDb } from "$lib/utils/db";

  let { params } = $props();
  let paper: any = $state(null);
  let loading = $state(true);
  let error: string | null = $state(null);
  let openalexData: any = $state(null);
  let openalexLoading = $state(false);

  const arxivId = params.id;

  onMount(async () => {
    try {
      await initDb();
      const { default: initSqlJs } = await import("sql.js");
      const SQL = await initSqlJs();
      const resp = await fetch("/data/search.db");
      const buf = await resp.arrayBuffer();
      const d = new SQL.Database(new Uint8Array(buf));
      const stmt = d.prepare(
        "SELECT id, title, abstract, authors, categories, date FROM papers WHERE id = ?"
      );
      stmt.bind([arxivId]);
      if (stmt.step()) {
        paper = stmt.getAsObject();
      }
      stmt.free();
      d.close();

      if (paper) {
        openalexLoading = true;
        fetch(`https://api.openalex.org/works/doi:https://doi.org/10.48550/arXiv.${arxivId}`)
          .then(r => r.ok ? r.json() : null)
          .then(d => { openalexData = d; })
          .catch(() => {})
          .finally(() => { openalexLoading = false; });
      } else {
        error = "Paper not found";
      }
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load paper";
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>{paper?.title ?? "Paper Detail"} — arXiv Explorer</title>
</svelte:head>

{#if loading}
  <div class="text-center py-12 animate-pulse text-gray-500">Loading paper…</div>
{:else if error}
  <div class="text-center py-12 text-red-400">
    {error}
    <a href="/papers" class="ml-2 underline text-blue-400">Back to search</a>
  </div>
{:else if paper}
  <article class="max-w-3xl mx-auto space-y-6">
    <div>
      <h1 class="text-2xl font-bold leading-snug">{paper.title}</h1>
      <div class="text-sm text-gray-400 mt-2">
        <a href={`https://arxiv.org/abs/${arxivId}`} target="_blank" class="text-blue-400 hover:underline">arXiv:{arxivId}</a>
        {#if paper.date} · {paper.date}{/if}
      </div>
      <div class="text-sm text-gray-300 mt-2">{paper.authors}</div>
      <div class="text-xs text-gray-500 mt-1">{paper.categories}</div>
    </div>

    {#if openalexLoading}
      <div class="animate-pulse text-sm text-gray-500">Loading citation data…</div>
    {:else if openalexData}
      <div class="flex gap-4 text-sm">
        <div class="bg-gray-900 px-3 py-2 rounded-lg">
          <div class="text-gray-400 text-xs">Citations</div>
          <div class="font-bold">{openalexData.cited_by_count ?? "?"}</div>
        </div>
      </div>
    {/if}

    <div>
      <h2 class="text-lg font-semibold mb-2">Abstract</h2>
      <p class="text-sm text-gray-300 leading-relaxed">{paper.abstract || "No abstract available"}</p>
    </div>

    <a href="/papers" class="inline-block text-sm text-blue-400 hover:underline">← Back to search</a>
  </article>
{/if}
```

- [ ] **Step 2: Test with a known arXiv ID**

Run `pnpm dev`, navigate to `/papers/2401.00001`
Expected: paper title, abstract, authors load from search.db; citation count loads from OpenAlex

---
### Task 6: Author Network Page

**Files:**
- Create: `src/routes/authors/+page.svelte`
- Create: `src/lib/components/AuthorGraph.svelte`

- [ ] **Step 1: Write AuthorGraph component**

```svelte
<script lang="ts">
  import { onMount } from "svelte";
  import * as d3 from "d3";

  interface AuthorNode { id: string; label: string; weight: number; }
  interface AuthorEdge { source: string; target: string; weight: number; }
  interface AuthorGraphData {
    nodes: AuthorNode[];
    edges: AuthorEdge[];
    metadata: { total_nodes: number; total_edges: number };
  }

  let canvasEl: HTMLCanvasElement;
  let data: AuthorGraphData | null = $state(null);
  let loading = $state(true);
  let error: string | null = $state(null);

  onMount(async () => {
    try {
      const resp = await fetch("/data/author_graph.json");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      data = await resp.json();
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load author graph";
    } finally {
      loading = false;
    }
  });

  $effect(() => {
    if (!data || !canvasEl) return;
    renderCanvas(data, canvasEl);
  });

  function renderCanvas(graph: AuthorGraphData, canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d")!;
    const w = canvas.clientWidth || 800;
    const h = 600;
    canvas.width = w;
    canvas.height = h;

    const maxW = Math.max(...graph.nodes.map(n => n.weight), 1);
    const nodes = graph.nodes.map(n => ({ ...n, r: Math.max(1, Math.sqrt(n.weight / maxW) * 8) }));
    const edges = graph.edges;

    const simulation = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(edges).id((d: any) => d.id).distance(30))
      .force("charge", d3.forceManyBody().strength(-30))
      .force("center", d3.forceCenter(w / 2, h / 2))
      .force("collision", d3.forceCollide().radius((d: any) => d.r + 1))
      .alpha(0.3);

    simulation.on("tick", () => {
      ctx.clearRect(0, 0, w, h);

      ctx.strokeStyle = "rgba(74, 85, 104, 0.15)";
      ctx.lineWidth = 0.3;
      for (const e of edges) {
        const s = e.source as any;
        const t = e.target as any;
        if (s.x !== undefined && t.x !== undefined) {
          ctx.beginPath();
          ctx.moveTo(s.x, s.y);
          ctx.lineTo(t.x, t.y);
          ctx.stroke();
        }
      }

      for (const n of nodes as any[]) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, 2 * Math.PI);
        ctx.fillStyle = "rgba(79, 155, 209, 0.5)";
        ctx.fill();
        ctx.strokeStyle = "rgba(79, 155, 209, 0.8)";
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    });
  }
</script>

<div class="w-full">
  {#if loading}
    <div class="h-[600px] flex items-center justify-center animate-pulse text-gray-500">Loading author graph…</div>
  {:else if error}
    <div class="h-[600px] flex items-center justify-center text-red-400">
      {error}
      <button onclick={() => location.reload()} class="ml-2 underline">Retry</button>
    </div>
  {:else}
    <canvas bind:this={canvasEl} class="w-full h-[600px]" role="img" aria-label="Author collaboration network"></canvas>
  {/if}
</div>
```

- [ ] **Step 2: Wire up authors page**

**`src/routes/authors/+page.svelte`:**
```svelte
<script lang="ts">
  import AuthorGraph from "$lib/components/AuthorGraph.svelte";
</script>

<svelte:head>
  <title>Authors — arXiv Explorer</title>
</svelte:head>

<div class="space-y-4">
  <h1 class="text-2xl font-bold">Author Collaboration Network</h1>
  <p class="text-sm text-gray-400">
    Top 50,000 most prolific authors and their co-authorship connections.
    Bigger nodes = more papers.
  </p>
  <AuthorGraph />
</div>
```

---
### Task 7: Author Detail Page

**Files:**
- Create: `src/routes/authors/[id]/+page.svelte`

- [ ] **Step 1: Write author detail page**

```svelte
<script lang="ts">
  import { onMount } from "svelte";
  import * as d3 from "d3";
  import { initDb, searchPapers, type PaperResult } from "$lib/utils/db";

  let { params } = $props();
  let authorName = $derived(decodeURIComponent(params.id));
  let papers: PaperResult[] = $state([]);
  let paperCount = $state(0);
  let loading = $state(true);

  onMount(async () => {
    try {
      await initDb();
      const last = authorName.split(" ").pop() || authorName;
      const res = searchPapers(last, 50, 0);
      papers = res.results.filter(p =>
        p.authors.toLowerCase().includes(authorName.toLowerCase())
      );
      paperCount = papers.length;
    } catch {
      // silently fail
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>{authorName} — arXiv Explorer</title>
</svelte:head>

{#if loading}
  <div class="text-center py-12 animate-pulse text-gray-500">Loading author…</div>
{:else}
  <div class="max-w-3xl mx-auto space-y-6">
    <div>
      <h1 class="text-2xl font-bold">{authorName}</h1>
      <div class="text-sm text-gray-400">{paperCount} paper{paperCount !== 1 ? "s" : ""}</div>
    </div>

    {#if paperCount === 0}
      <div class="text-center py-12 text-gray-500">No papers found for this author</div>
    {:else}
      <div class="space-y-2">
        {#each papers as paper}
          <a href="/papers/{paper.id}" class="block p-4 rounded-lg border border-gray-800 hover:border-blue-500 transition-colors space-y-1">
            <div class="text-xs text-gray-500">{paper.date}</div>
            <div class="font-medium text-sm">{paper.title}</div>
            <div class="text-xs text-gray-400 truncate">{paper.authors}</div>
          </a>
        {/each}
      </div>
    {/if}

    <a href="/authors" class="inline-block text-sm text-blue-400 hover:underline">← All authors</a>
  </div>
{/if}
```

---
### Task 8: Categories + Causal Placeholder + About Pages

**Files:**
- Create: `src/routes/categories/+page.svelte`
- Create: `src/routes/causal/+page.svelte`
- Create: `src/routes/about/+page.svelte`

- [ ] **Step 1: Write categories page**

**`src/routes/categories/+page.svelte`:**
```svelte
<script lang="ts">
  import { onMount } from "svelte";

  interface Domain {
    id: string; label: string; color: string;
    papers: number; subcategories: { id: string; label: string; papers: number }[];
  }

  let domains: Domain[] = $state([]);
  let totalPapers = $state(0);
  let loading = $state(true);

  onMount(async () => {
    try {
      const resp = await fetch("/data/category_hierarchy.json");
      const d = await resp.json();
      domains = d.domains;
      totalPapers = d.total_papers;
    } catch {} finally { loading = false; }
  });
</script>

<svelte:head>
  <title>Categories — arXiv Explorer</title>
</svelte:head>

{#if loading}
  <div class="text-center py-12 animate-pulse text-gray-500">Loading categories…</div>
{:else}
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">Research Categories</h1>
    <p class="text-sm text-gray-400">{totalPapers.toLocaleString()} papers across {domains.length} domains</p>
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {#each domains as domain}
        <div class="rounded-lg border border-gray-800 p-4 space-y-2">
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-full" style="background:{domain.color}"></div>
            <div class="font-medium text-sm">{domain.label}</div>
          </div>
          <div class="text-xs text-gray-400">{domain.papers.toLocaleString()} papers · {domain.subcategories.length} subcategories</div>
          <div class="space-y-1">
            {#each domain.subcategories.slice(0, 5) as cat}
              <a href="/papers?category={cat.id}" class="block text-xs text-gray-500 hover:text-blue-400 truncate">
                {cat.id} ({cat.papers.toLocaleString()})
              </a>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  </div>
{/if}
```

- [ ] **Step 2: Write causal placeholder page**

**`src/routes/causal/+page.svelte`:**
```svelte
<svelte:head>
  <title>Causal Inference — arXiv Explorer</title>
</svelte:head>

<div class="max-w-xl mx-auto text-center space-y-6 py-12">
  <h1 class="text-2xl font-bold">Causal Inference with Bayesian UQ</h1>
  <div class="text-gray-400 space-y-2">
    <p>Explore causal relationships between research trends over time.</p>
    <p class="text-sm">Phase 2 — Coming when Pyodide + PyMC WASM integration is complete.</p>
  </div>
  <div class="bg-gray-900 rounded-lg p-8 border border-gray-800">
    <div class="text-4xl mb-4">🔬</div>
    <div class="text-sm text-gray-500">
      Time series data is precomputed at <code class="text-gray-300">/data/timeseries/</code>.
      The causal pipeline will load Pyodide + PyMC in-browser and run
      Bayesian structural time series models client-side.
    </div>
  </div>
</div>
```

- [ ] **Step 3: Write about page**

**`src/routes/about/+page.svelte`:**
```svelte
<svelte:head>
  <title>About — arXiv Explorer</title>
</svelte:head>

<div class="max-w-xl mx-auto space-y-6">
  <h1 class="text-2xl font-bold">About</h1>
  <div class="text-sm text-gray-300 space-y-4">
    <p>
      arXiv Research Explorer lets you explore over 3 million research papers
      through interactive network graphs and full-text search.
    </p>
    <p>
      <strong>Data source:</strong>
      <a href="https://huggingface.co/datasets/open-index/open-arxiv" target="_blank" class="text-blue-400 hover:underline">
        open-index/open-arxiv</a> on HuggingFace, updated monthly.
    </p>
    <p>
      <strong>Citation data:</strong>
      <a href="https://openalex.org" target="_blank" class="text-blue-400 hover:underline">OpenAlex</a>
      (free API, no key required).
    </p>
    <p>
      <strong>Tech stack:</strong> Svelte 5 + SvelteKit, D3.js, sql.js (FTS5), Tailwind CSS.
      Precomputed static data — no runtime servers.
    </p>
    <p>
      <strong>Source:</strong>
      <a href="https://github.com/narenprax/arxiv-data-explorer" target="_blank" class="text-blue-400 hover:underline">
        GitHub</a>
    </p>
  </div>
</div>
```

---
### Task 9: Error Page + Vercel Deployment Config

**Files:**
- Create: `src/routes/+error.svelte`
- Create: `src/routes/404.svelte` (or let SvelteKit fallback handle it)
- Modify: `package.json` with build script
- Modify/Add: `static/_headers` for sql.js-httpvfs Range request support
- Create: `vercel.json` (auto-detected by adapter-static, but needs config)

- [ ] **Step 1: Write error page**

**`src/routes/+error.svelte`:**
```svelte
<script lang="ts">
  let { status, error } = $props();
</script>

<div class="text-center py-12 space-y-4">
  <h1 class="text-4xl font-bold">{status}</h1>
  <p class="text-gray-400">{error?.message ?? "Something went wrong"}</p>
  <a href="/" class="inline-block text-blue-400 hover:underline">Go home</a>
</div>
```

- [ ] **Step 2: Configure Vercel headers for sql.js-httpvfs**

**`static/_headers`:**
```
/data/search.db
  Access-Control-Allow-Origin: *
  Cache-Control: public, max-age=31536000, immutable
```

- [ ] **Step 3: Add build script to package.json**

Ensure `package.json` has:
```json
{
  "scripts": {
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

- [ ] **Step 4: Verify production build**

```bash
pnpm build
pnpm preview
```

Expected: site builds without errors, all routes prerendered. Open browser to port from preview — nav, home graph, search, all pages work.

---
### Task 10: Final Integration Test

- [ ] **Step 1: Run data pipeline with full args**

```bash
uv run python scripts/build_data.py --sample 100000 --no-incremental
```

Expected: all static/data/ files created with 100K papers

- [ ] **Step 2: Build and preview**

```bash
pnpm build && pnpm preview
```

- [ ] **Step 3: Manual test checklist**
- [ ] Home page: category graph renders, hover shows tooltips
- [ ] /papers: type query → results appear, pagination works
- [ ] /papers/[id]: paper loads, OpenAlex data loads
- [ ] /authors: canvas renders with author nodes
- [ ] /authors/[id]: author info loads
- [ ] /categories: domain grid renders
- [ ] /causal: placeholder renders
- [ ] /about: renders
- [ ] Dark/light toggle works
- [ ] Mobile responsive: nav collapses, graphs reflow
- [ ] Inavlid paper ID: shows "Paper not found"
- [ ] Empty search: shows empty state
