# ArXiv Data Explorer — Architecture & Design Spec

**Date**: 2026-07-04
**Status**: Draft
**Author**: AI-assisted design session

---

## 1. Problem & Goal

### 1.1 Current State

The project is a **Streamlit** app deployed at `arxivexplorer.streamlit.app` using:

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit (Python) |
| Data loading | HuggingFace Hub + Polars |
| Network graphs | NetworkX + Plotly |
| Search | Polars filtering (no index) |
| Deployment | Streamlit Cloud |

### 1.2 Problems

- **Can't self-host** — Streamlit Cloud only
- **No real search** — Polars filtering is O(n) scan over 3M papers
- **Slow** — every interaction reloads Python runtime
- **No offline/static mode** — requires live Python backend
- **Limited visual design** — Streamlit components constrain layout

### 1.3 Goal

Migrate to a **host-anywhere** architecture (Svelte 5 + SvelteKit) that:

- Deploys to **Vercel free tier** (Hobby plan)
- Runs locally on **8GB M1 MacBook** with zero extra infra
- Uses **precomputed static data** — no runtime Python server
- Supports **causal inference + Bayesian UQ** in a future phase via Pyodide + PyMC in-browser
- **Fits within Vercel free tier limits**: 100 deploys/day, 10s timeout, 512MB functions, 100GB bandwidth

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Data Pipeline (Python)                  │
│  open-index/open-arxiv (HF) → Polars → precompute JSON   │
│  Output: static/data/*.json, static/data/search.db       │
│  Frequency: monthly (when new Parquet shards drop)       │
└──────────────────────┬──────────────────────────────────┘
                       │  git commit / push
                       ▼
┌─────────────────────────────────────────────────────────┐
│              SvelteKit Static Site (Vercel)               │
│                                                          │
│  /                Home — category network graph          │
│  /papers          Full-text search (sql.js FTS5)          │
│  /papers/[id]     Paper detail page                       │
│  /authors         Author network graph                    │
│  /authors/[id]    Author detail page                      │
│  /categories      Category drill-down                     │
│  /causal          Placeholder — lazy loads Pyodide+PyMC   │
│  /about           About / methodology page                │
│                                                          │
│  Data: static/data/*.json served via HTTP Range requests  │
│  Search: sql.js-httpvfs loads from static/data/search.db  │
└─────────────────────────────────────────────────────────┘
```

### 2.1 Data Pipeline (build time only)

**Location**: `scripts/build_data.py`

Runs on:
- **Local MacBook**: `uv run scripts/build_data.py`
- **GitHub Actions** (future): monthly cron triggered by new open-index shards

**Input**: `open-index/open-arxiv` on HuggingFace — monthly Parquet shards, each covering ~2 weeks of submissions. Latest shard is always the small incremental update; full re-index requires all shards.

**Pipeline steps**:

1. **Load shards** — iterate all Parquet shards from HF hub, concatenate into single Polars DataFrame
   - Incremental mode: if previous `static/data/papers.parquet` exists, load only new shards, merge
2. **Deduplicate** — title/arXiv ID hash dedup
3. **Embedding vector stripped** — drop the `vector` column (~8GB per shard) before further processing
4. **Export artifacts**:
   - `static/data/papers.parquet` — full deduplicated dataset (for incremental rebuilds)
   - `static/data/category_graph.json` — category co-occurrence graph
   - `static/data/author_graph.json` — top 50K author ego-network
   - `static/data/author_rankings.json` — prolific author stats
   - `static/data/category_hierarchy.json` — category drill-down tree
   - `static/data/network_stats.json` — degree distributions, multi-category counts
   - `static/data/search.db` — sql.js FTS5 full-text index
   - `static/data/timeseries/` — aggregate counts per category per month (placeholder for causal phase)
5. **Commit and push** — new data files to GitHub repo → auto-deploy to Vercel

### 2.2 Data Flow at Runtime

```
User browser
    │
    ├── / route → loads category_graph.json (5KB gzip)
    │
    ├── /papers → loads search.db ~30MB (sql.js-httpvfs lazy Range requests)
    │   └── query → sql.js FTS5 → render results
    │
    ├── /authors → loads author_graph.json (~3MB gzip)
    │   └── D3.js force simulation → canvas render
    │
    ├── /papers/[id] → tiny metadata blob (inline in page JSON)
    │   └── could also fetch OpenAlex API on-demand for citation count
    │
    └── /causal → lazy loads Pyodide + PyMC runtime (~10MB WASM)
        └── loads timeseries/ → runs inference in browser
```

---

## 3. Technology Decisions

### 3.1 Frontend: Svelte 5 + SvelteKit

| Why Svelte 5 | Details |
|-------------|---------|
| Runes (`$state`, `$derived`, `$effect`) | No virtual DOM, reactive at compile time |
| Bundle size | ~12KB gzip base (React is ~45KB) |
| DOM perf | Better for 200+ node force-simulated D3 graphs |
| SvelteKit | File-based routing, static adapter, minimal config |

### 3.2 Search: sql.js FTS5 with sql.js-httpvfs

| Why this stack | Details |
|---------------|---------|
| sql.js | SQLite compiled to WASM — runs full FTS5 in browser |
| sql.js-httpvfs | Loads individual DB pages via HTTP Range — no full download needed |
| FTS5 | Proven at 50M records (Charisol Pulse, Apr 2026): 250GB → 40ms |
| Index size | ~225MB for 3M paper titles (titles-only FTS5 fits Vercel Hobby's 250MB per-file limit) |
| Cold start | First Range request loads page 0 (~17KB), then on-demand |

**Search features**:
- Full-text on title, abstract, author names
- Category filter (dropdown/checkbox)
- Date range slider
- Sort by relevance (BM25), date, or citation count
- Paginated results (lazy load as user scrolls)
- Regex mode (SQLite REGEXP via JS callback)

### 3.3 Network Graphs: D3.js

| Why D3.js | Details |
|-----------|---------|
| Force simulation | `d3-force` does layout in-browser from precomputed JSON |
| Canvas fallback | D3 + Canvas for author graphs (50K nodes) |
| SVG for small graphs | Category graph (< 200 nodes) kept in SVG for crisp interaction |
| No WebGL dependency | Works on all browsers, no GPU required |

**Precomputed data**:
- Nodes: stable IDs, labels, weights
- Edges: source, target, weight (top-20 neighbors only to keep graph sparse)
- No layout positions stored — D3 computes layout client-side for responsive reflow

### 3.4 Live Enrichment: OpenAlex API

| Why OpenAlex | Details |
|-------------|---------|
| Free | No API key needed for basic queries |
| Citation data | Returns cited_by_count, concepts, publication date |
| Rate limit | 10 req/s without key — sufficient for on-demand paper detail |
| Coverage | Indexes arXiv + many other sources |

**Used for**: Paper detail pages (`/papers/[id]`) — fetch citation count, related works, concept tags on demand. Data is NOT precomputed (would inflate build artifacts).

### 3.5 Causal Inference: Pyodide + PyMC (Phase 2)

- **Not included in v1 build**
- Architecture reserved: `/causal` route, `static/data/timeseries/` data
- When loaded: Pyodide runtime (~10MB WASM) + PyMC-WASM + DoWhy
- User selects treatment + outcome variables from category/month counts
- Bayesian structural time series model runs entirely in browser
- Results: causal effect estimate + Bayesian credible intervals + robustness checks

Pyodide + PyMC WASM confirmed working as of 2026 (Eric J. Ma blog, Mar 2026; Pyodide 0.314.0 release, Jun 2026).

---

## 4. Routes / Pages

### 4.1 Home (`/`)

| Element | Implementation |
|---------|---------------|
| Category co-occurrence network | D3.js force-directed graph, SVG render |
| Sidebar stats | Total papers, categories, authors |
| Quick search bar | Text input → navigates to `/papers?q=...` |
| Featured categories | Top-10 largest categories |

Data source: `static/data/category_graph.json`

### 4.2 Search (`/papers`)

| Element | Implementation |
|---------|---------------|
| Search input | Debounced (300ms) → sql.js FTS5 query |
| Faceted filters | Category tree, date range, author |
| Results list | Paper card with title, authors, date, snippet |
| Sort controls | Relevance, date, citations |
| Pagination | Infinite scroll (30 per page) |
| Status placeholder | Empty state, loading state, error state — all handled |

Data source: `static/data/search.db` via sql.js-httpvfs

### 4.3 Paper Detail (`/papers/[id]`)

| Element | Implementation |
|---------|---------------|
| Title, abstract, authors | From static metadata |
| Citation count | OpenAlex API (client-side fetch) |
| Related papers | OpenAlex API or precomputed nearest-neighbor |
| Category breadcrumb | Link to category filter |
| Download BibTeX | Client-side generated |
| 404 handling | Fallback when ID not found |

Data source: Static metadata for core fields, OpenAlex for enrichment.

### 4.4 Authors (`/authors`)

| Element | Implementation |
|---------|---------------|
| Author ego-network | D3.js force-directed graph, Canvas render |
| Top authors list | Sorted by paper count |
| Search/filter | Filter by name fragment |
| Click → author detail | Navigate to `/authors/[id]` |

Data source: `static/data/author_graph.json`, `static/data/author_rankings.json`

### 4.5 Author Detail (`/authors/[id]`)

| Element | Implementation |
|---------|---------------|
| Author name, stats | Papers count, categories, co-authors |
| Publication timeline | Monthly bar chart |
| Co-author network | Subgraph of ego-network |
| Paper list | Paginated, sortable |
| Missing author | Handle gracefully (e.g., "Unknown author" with option to search) |

Data source: Static metadata subset, `static/data/author_graph.json`

### 4.6 Categories (`/categories`)

| Element | Implementation |
|---------|---------------|
| Category tree | D3 collapsible tree or nested list |
| Size indicators | Bar chart per category |
| Cross-category flow | Sankey-like diagram |
| Click → filtered search | Navigate to `/papers?category=...` |

Data source: `static/data/category_hierarchy.json`

### 4.7 Causal (`/causal`)

| Element | Implementation |
|---------|---------------|
| Placeholder page | "Coming soon — Causal inference with Bayesian UQ" |
| Architecture hook | `/causal` route exists with stub component |
| Data ready | `static/data/timeseries/` populated by build pipeline |
| Lazy Pyodide load | `import('pyodide')` on first visit to `/causal` |
| Dynamic import | Only downloaded when user navigates to causal page |

Data source: Phase 2 implementation.

### 4.8 About (`/about`)

Static page with methodology, data sources, citation info.

---

## 5. UI/UX Design

### 5.1 Layout System

```
┌─────────────────────────────────────────────────────────┐
│  Nav bar: [Logo] [Search] [Papers] [Authors] [About]    │
├─────────────────────┬───────────────────────────────────┤
│                     │                                   │
│  Sidebar (optional) │  Main content area                │
│  - Filters          │  (graph, results, detail)         │
│  - Stats            │                                   │
│  - Controls         │                                   │
│                     │                                   │
└─────────────────────┴───────────────────────────────────┘
```

- **Responsive**: sidebar collapses to top sheet on mobile
- **Theme**: dark mode default, light mode toggle
- **Font**: system UI stack (Inter / SF Pro fallback)

### 5.2 States

Every interactive component handles:

| State | Behavior |
|-------|----------|
| **Loading** | Skeleton placeholders, not spinners |
| **Empty** | "No papers found matching your query" with suggestions |
| **Error** | "Failed to load graph" with retry button |
| **Offline** | Detect network loss, show cached data, degrade gracefully |
| **First load / cold start** | sql.js WASM compilation (~100ms) shown as progress indicator |

### 5.3 Performance Targets

| Metric | Target |
|--------|--------|
| First paint | < 1.5s (static prerender) |
| Time to interactive | < 3s (sql.js + D3 lazy loaded) |
| Search response | < 100ms (sql.js FTS5) |
| Graph render | < 500ms (200-node category graph) |
| Lighthouse score | > 95 on all axes |
| Bundle size (base) | < 50KB JS gzip |
| Bundle size (sql.js) | ~1.2MB WASM (lazy loaded on `/papers`) |

### 5.4 Accessibility

- Keyboard navigable graphs (tab + arrow keys)
- Screen reader labels on all interactive elements
- Focus management on search results
- Color-blind friendly palette for network graphs

---

## 6. Search Architecture (sql.js FTS5)

### 6.1 Index Schema

```sql
CREATE VIRTUAL TABLE papers_fts USING fts5(
  id, title, abstract, authors,
  content='papers', content_rowid='rowid',
  tokenize='porter unicode61'
);

CREATE TABLE papers(
  rowid INTEGER PRIMARY KEY,
  id TEXT,           -- arXiv ID
  title TEXT,
  abstract TEXT,
  authors TEXT,       -- JSON array
  categories TEXT,    -- JSON array
  date TEXT,          -- YYYY-MM-DD
  citations INTEGER
);

-- Auxiliary indexes for filtering
CREATE INDEX idx_date ON papers(date);
CREATE INDEX idx_categories ON papers(categories);
```

### 6.2 Query Flow

1. User types query → debounce 300ms
2. sql.js executes: `SELECT ... FROM papers_fts WHERE papers_fts MATCH ? ORDER BY rank`
3. Apply filters: `AND date BETWEEN ? AND ? AND categories MATCH ?`
4. Render first 30 results
5. On scroll: `SELECT ... LIMIT 30 OFFSET $offset`
6. Total count from: `SELECT COUNT(*) FROM papers_fts WHERE ...`

### 6.3 Index Build (in Python)

```python
import sqlite3

conn = sqlite3.connect("static/data/search.db")
conn.execute("CREATE VIRTUAL TABLE papers_fts USING fts5(...)")
conn.execute("INSERT INTO papers_fts SELECT ... FROM papers")
conn.execute("INSERT INTO papers_fts(papers_fts) VALUES('optimize')")  # VACUUM-like
conn.commit()
```

Updated monthly when new Parquet shards arrive.

---

## 7. Network Graph Architecture

### 7.1 Category Co-occurrence Graph

**Build**: For each paper, increment co-occurrence count for every pair of its categories. Keep top-20 neighbors per category.

**JSON structure** (`category_graph.json`):

```json
{
  "nodes": [
    {"id": "cs.AI", "label": "Artificial Intelligence", "weight": 45231, "group": "cs"}
  ],
  "edges": [
    {"source": "cs.AI", "target": "cs.LG", "weight": 12340}
  ],
  "metadata": {
    "total_nodes": 194,
    "total_edges": 3840,
    "last_updated": "2026-07-01"
  }
}
```

**Rendering**: D3.js `forceSimulation`
- `forceManyBody()` for repulsion
- `forceLink()` with edge weight scaling
- `forceCenter()` for centering
- Node size proportional to paper count
- Edge thickness proportional to co-occurrence
- Color by top-level group (cs, math, physics, ...)

### 7.2 Author Ego-Network

**Build**: Extract top 50K authors by paper count. For each, link to co-authors (up to 20 edges per author).

**JSON structure** (`author_graph.json`):

```json
{
  "nodes": [
    {"id": "andrew-ng", "label": "Andrew Ng", "weight": 245, "affiliation": "Stanford"}
  ],
  "edges": [
    {"source": "andrew-ng", "target": "jiah-wu", "weight": 12}
  ]
}
```

**Rendering**: D3.js with Canvas (50K nodes, 200K edges — SVG would choke).

### 7.3 Interaction Model

| Action | Behavior |
|--------|----------|
| Hover node | Tooltip with label + stats |
| Click node | Navigate to detail page |
| Drag node | Reposition (released node returns) |
| Scroll | Zoom in/out |
| Pinch (mobile) | Zoom |
| Double-click | Zoom to node + neighbors |
| Right-click | Context menu (open in new tab) |

---

## 8. Deployment Matrix

### 8.1 Vercel (Production)

| Setting | Value |
|---------|-------|
| Adapter | `@sveltejs/adapter-static` |
| Static data | In `static/data/`, deployed as assets |
| API routes | None currently (all static) |
| Edge functions | None |
| Serverless functions | None |
| CDN | Vercel Edge Network |
| Cost | Free (Hobby plan) |

### 8.2 Local (MacBook Dev)

| Setting | Value |
|---------|-------|
| Serve | `vite dev` with static data symlink |
| Data | `static/data/` from local build |
| Python | `uv run scripts/build_data.py` |
| Node | pnpm, latest LTS |
| RAM | < 512MB for frontend dev server |

### 8.3 CI/CD (Future)

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 0 1 * *'  # Monthly data refresh

jobs:
  build-data:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run scripts/build_data.py
      - run: git add static/data/ && git commit -m "update data"
      - run: git push
```

---

## 9. Data Pipeline Detail

### 9.1 HuggingFace Dataset Loading

```python
import polars as pl
from huggingface_hub import snapshot_download

shards = snapshot_download("open-index/open-arxiv", repo_type="dataset")
dfs = []
for parquet in sorted(Path(shards).glob("*.parquet")):
    df = pl.read_parquet(parquet)
    df = df.drop("vector")  # strip embeddings (~8GB)
    dfs.append(df)

full = pl.concat(dfs).unique(subset=["id"])
```

### 9.2 Incremental Mode

```
If static/data/papers.parquet exists:
  1. Load existing → get max date
  2. Only load new shards with date > max date
  3. Merge + deduplicate
else:
  Full load all shards
```

### 9.3 Output Sizes (Estimated)

| Artifact | Size | Compressed | Hosting |
|----------|------|------------|---------|
| `papers.parquet` (deduped master) | ~200MB | ~50MB | Build cache only |
| `category_graph.json` | ~200KB | ~5KB | Vercel static |
| `author_graph.json` | ~12MB | ~3MB | Vercel static |
| `search.db` (FTS5 titles-only) | ~225MB | — | Vercel static. sql.js-httpvfs loads pages on demand via HTTP Range; full file never downloaded. |
| `author_rankings.json` | ~4MB | ~1MB | Vercel static |
| `category_hierarchy.json` | ~300KB | ~15KB | Vercel static |
| `network_stats.json` | ~10KB | ~2KB | Vercel static |
| `timeseries/*.json` | ~2MB | ~500KB | Vercel static |

### 9.4 Build Time (Local MacBook M1)

| Step | Time |
|------|------|
| Download HF shards (first time) | ~5-10 min |
| Polars load + dedup | ~30s |
| Category graph build | ~10s |
| Author graph build | ~30s |
| FTS5 index build | ~2 min |
| Timeseries aggregate | ~10s |
| **Total (cached incremental)** | **~3 min** |
| **Total (cold)** | **~8-13 min** |

---

## 10. Phase 2: Causal Inference + Bayesian UQ

### 10.1 Scope

Not built in v1. Reserved as the novel differentiator — no existing arXiv explorer offers interactive causal inference with Bayesian uncertainty quantification.

### 10.2 Architecture Hook

```
static/data/timeseries/2022-01.json
static/data/timeseries/2022-02.json
...
static/data/timeseries/2026-06.json
```

Each file: `{ "cs.AI": 452, "cs.LG": 891, ... }` — submission counts per category per month.

Already computed by build pipeline, just not loaded in v1 frontend.

### 10.3 Stack (Phase 2)

- **Pyodide** — Python runtime compiled to WASM, loaded in browser
- **PyMC** — Bayesian statistical modeling (confirmed working on Pyodide)
- **DoWhy** — Causal inference framework (optional, may use PyMC directly)
- **UI**: User selects treatment variable (e.g., "LLM papers"), outcome variable (e.g., "total cs.AI submissions"), date range
- **Model**: Bayesian structural time series with counterfactual prediction
- **Output**: Causal effect estimate + credible interval + robustness checks

### 10.4 Performance Warning

Pyodide + PyMC WASM is ~10MB. Lazy-loaded only when user visits `/causal` route. Model inference on time series of ~200 data points takes ~5-10s in browser.

---

## 11. SvelteKit Project Structure

```
arxiv-data-explorer/
├── scripts/
│   └── build_data.py          # Data pipeline
├── src/
│   ├── app.html
│   ├── app.css
│   ├── routes/
│   │   ├── +layout.svelte
│   │   ├── +page.svelte       # Home — category graph
│   │   ├── papers/
│   │   │   ├── +page.svelte   # Search page
│   │   │   └── [id]/
│   │   │       └── +page.svelte
│   │   ├── authors/
│   │   │   ├── +page.svelte   # Author network
│   │   │   └── [id]/
│   │   │       └── +page.svelte
│   │   ├── categories/
│   │   │   └── +page.svelte
│   │   └── causal/
│   │       └── +page.svelte   # Placeholder
│   ├── lib/
│   │   ├── components/
│   │   │   ├── CategoryGraph.svelte
│   │   │   ├── AuthorGraph.svelte
│   │   │   ├── SearchBar.svelte
│   │   │   ├── PaperCard.svelte
│   │   │   ├── PaperList.svelte
│   │   │   └── StatsPanel.svelte
│   │   ├── stores/
│   │   │   ├── search.svelte.ts
│   │   │   └── graph.svelte.ts
│   │   └── utils/
│   │       ├── openalex.ts
│   │       └── db.ts          # sql.js-httpvfs wrapper
│   └── param/                 # (tombstone placeholder)
├── static/
│   ├── data/
│   │   ├── category_graph.json
│   │   ├── author_graph.json
│   │   ├── search.db
│   │   ├── timeseries/
│   │   └── ...
│   └── favicon.ico
├── svelte.config.js
├── vitest.config.ts
├── tailwind.config.ts
├── package.json
├── tsconfig.json
└── .github/workflows/
    └── deploy.yml
```

---

## 12. Implementation Plan

### Phase 1a: Foundation (this session)

| Step | Description | Time |
|------|-------------|------|
| 1 | Write design spec ✓ | Done |
| 2 | Build data pipeline script | ~2h |
| 3 | Scaffold SvelteKit + routes | ~30min |
| 4 | Implement search page | ~2h |
| 5 | Implement category graph | ~1.5h |
| 6 | Implement author graph | ~1.5h |
| 7 | Wire up detail pages | ~1h |
| 8 | Deploy to Vercel | ~30min |
| 9 | Verify on MacBook | ~30min |

### Phase 1b: Polish (next session)

| Step | Description |
|------|-------------|
| 10 | Tailwind design pass |
| 11 | Accessibility audit |
| 12 | Lighthouse optimization |
| 13 | Error/loading/empty states |
| 14 | Responsive breakpoints |
| 15 | OpenAlex enrichment |

### Phase 2: Causal Inference (future)

| Step | Description |
|------|-------------|
| 16 | Implement `/causal` UI |
| 17 | Pyodide + PyMC integration |
| 18 | Bayesian model |
| 19 | Causal UI + visualization |

---

## 13. Open Questions / Risks

| Risk | Mitigation |
|------|-----------|
| sql.js WASM compilation on mobile | Show progress indicator; ~100ms on modern phones |
| HF shards change schema | Pin to specific shard date; add schema validation |
| Vercel 250MB per-file limit | Titles-only FTS5 index estimated ~225MB — fits the limit. If exceeded, build yearly shards (2020.db, 2021.db, ...) and search all in parallel. |
| Vercel bandwidth (100GB on Hobby) | sql.js-httpvfs loads pages on demand (~5-15KB per query, ~1-5MB per session for search). 100GB/mo supports ~20K search sessions. If exceeded, upgrade to Pro ($20/mo, 1TB) or move DB to Cloudflare R2 (free tier 10GB, zero egress). |
| Author disambiguation | Authors are string-based; no ORCID. Future: clustering by name+co-author graph |
| PyMC in WASM performance | Target ~5-10s. If too slow, precompute Bayesian posteriors server-side and serve as JSON |
| Build time growing with data | Incremental mode handles new shards only |

---

## 14. Migration Path from Streamlit

The old Streamlit app remains at `arxiv_explorer/` and `main.py` during development. Once the SvelteKit version matches feature parity:

1. Add redirect from `arxivexplorer.streamlit.app` to new Vercel URL
2. Deprecate `arxiv_explorer/` directory
3. Update README
4. Archive old app in git history (don't delete — reference for features)
