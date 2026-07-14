# arXiv Network Explorer

A pre-rendered SvelteKit 5 static site for exploring 3M+ arXiv papers. Features D3.js force-directed category graphs, author rankings, paper search, category hierarchy, and a unified Daft-based data pipeline.

### Pages

- **Home** — hero, stats band, interactive category co-occurrence network
- **Papers** — search with Semantic Scholar API, paginated results
- **Authors** — ranked author list with paper counts
- **Categories** — domain/category hierarchy with color-coded indicators
- **Trends** — causal inference graph from Bayesian Poisson VAR

## Data Pipeline

A single Daft-based Python script (`scripts/build_data.py`) processes the `open-index/open-arxiv` HuggingFace dataset (2.99M papers, 417 Parquet shards) into the JSON and SQLite files the frontend consumes.

### Setup

```bash
uv sync
```

### Usage

```bash
# Metadata only (categories, authors, search, timeseries) — ~3 min for 10K sample
uv run python scripts/build_data.py --sample 10000

# Full pipeline on sample
uv run python scripts/build_data.py --sample 10000 --fulltext --embeddings --ml
```

### CLI Flags

| Flag | Phase | Description |
|------|-------|-------------|
| `--sample N` | — | Process ~N papers (reads ~N/7200 shards). Omit for all 2.99M. |
| `--no-incremental` | — | Force full rebuild (skip checkpoint cache) |
| *(no flag)* | Metadata | Runs all metadata builders: category graph, author graph, author rankings, FTS5 search DB, category hierarchy, category stats, timeseries |
| `--fulltext` | Compute | Download PDFs via httpx and extract text via PyMuPDF (concurrent, resumable) |
| `--embeddings` | Compute | Generate 384-dim vectors via sentence-transformers (all-MiniLM-L6-v2), save FAISS index |
| `--ml` | Compute | KMeans clustering with TF-IDF topic keywords + FAISS paper recommendations |
| `--gpu` | Compute | Enable Daft GPU UDFs and CUDA acceleration (NVIDIA machines only). `sentence-transformers` auto-detects CUDA. |

### Output Files

| File | Builder | Description |
|------|---------|-------------|
| `static/data/category_graph.json` | metadata | Category co-occurrence network (~N nodes, weighted edges) |
| `static/data/author_rankings.json` | metadata | Top 1000 authors by paper count |
| `static/data/search.db` | metadata | SQLite FTS5 search index (id, title, abstract, authors, categories) |
| `static/data/category_hierarchy.json` | metadata | Category taxonomy tree (N domains, M categories) |
| `static/data/category_stats.json` | metadata | Per-category paper counts with yearly breakdowns |
| `static/data/timeseries.json` | metadata | Global paper count per month |
| `static/data/fulltext/papers.parquet` | fulltext | Extracted PDF text (id + fulltext) |
| `static/data/embeddings/papers.parquet` | embeddings | 384-dim vectors (id + embedding array) |
| `static/data/embeddings/faiss.index` | embeddings | FAISS IndexFlatIP for similarity search |
| `static/data/topics.json` | ml | KMeans clusters with TF-IDF topic keywords |
| `static/data/recommendations.json` | ml | Top-10 similar papers per paper |

### Two-Machine Workflow (3M Papers)

Full pipeline for all ~3M papers. Run metadata on MacBook (fast), compute-heavy stages on a GPU box.

#### GPU Box Setup (One-Time)

```bash
# Clone and install deps on GPU machine
git clone git@github.com:<your>/arxiv-data-explorer.git
cd arxiv-data-explorer
uv sync --python 3.12
```

Ensure GPU box has CUDA + `nvidia-smi` working. `sentence-transformers` auto-detects CUDA.

#### Full 3M Paper Run

```bash
# 1. Commit changes (uncommitted work won't sync)
git add -A && git commit -m "data: regenerate for 3M papers"

# 2. MacBook — metadata only (categories, authors, search, suggests)
#    Reads all shards from HuggingFace (~10 min, no GPU needed)
uv run python scripts/build_data.py --no-incremental

# 3. Push code + metadata to GPU box
./scripts/sync_data.sh push

# 4. SSH to GPU box, run compute stages
cd ~/arxiv-data-explorer
uv run python scripts/build_data.py --no-incremental --fulltext --embeddings --ml --gpu

# 5. Pull artifacts back to MacBook
./scripts/sync_data.sh pull

# 6. Build the static site (MacBook)
npm run build
```

> Estimated output for 3M papers: suggest shards ~200MB, embeddings ~4-6GB. search.db ~3GB (not served to frontend — local reference). Ensure sufficient disk on both machines.

#### Sync Script

`scripts/sync_data.sh` manages data transfer:

```bash
./scripts/sync_data.sh push     # git push + SSH checkout to GPU box
./scripts/sync_data.sh pull     # rsync fulltext, embeddings, ML output back
GPU_HOST=my-gpu ./scripts/sync_data.sh full  # push → run remotely → pull
```

Set `GPU_HOST` env var (default: `gpu-box`) to your GPU machine hostname.

#### Running on GPU Box Standalone

```bash
uv run python scripts/build_data.py --no-incremental --fulltext --embeddings --ml --gpu
npm install && npm run build
```

The `--gpu` flag enables Daft GPU UDFs for accelerated processing on NVIDIA machines.

### Deployment

Deployed as a static site to Cloudflare Pages (uses `@sveltejs/adapter-static`). Cloudflare Pages Functions in `functions/api/` proxy arXiv, Semantic Scholar, and OpenAlex APIs to avoid CORS issues.

```bash
npm run build     # outputs to build/
npx wrangler pages deploy build/
```

Or connect the GitHub repo to the Cloudflare Pages dashboard — auto-deploys on push.

> **Size constraints:** Cloudflare Pages free plan has a 500MB asset limit. Suggest shards at 3M papers will be ~200MB, leaving ~300MB for the rest of the site. If you exceed the limit, host suggest shards on R2 or serve from a separate domain.

### Frontend Build

```bash
npm install
npm run build
```

### Packages

**Frontend**: SvelteKit 5, D3.js, Tailwind CSS 4, TypeScript, vis-network.  
**Data Pipeline**: Daft, HuggingFace Hub, httpx, PyMuPDF, sentence-transformers, FAISS, scikit-learn.
