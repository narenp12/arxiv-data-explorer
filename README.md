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
| `--gpu` | Compute | Enable Daft GPU UDFs (for NVIDIA machines — sentence-transformers auto-detects CUDA) |

### Output Files

| File | Builder | Description |
|------|---------|-------------|
| `static/data/category_graph.json` | metadata | Category co-occurrence network (93 nodes, ~290 weighted edges) |
| `static/data/author_rankings.json` | metadata | Top 1000 authors by paper count |
| `static/data/search.db` | metadata | SQLite FTS5 search index (id, title, abstract, authors, categories) |
| `static/data/category_hierarchy.json` | metadata | Category taxonomy tree (27 domains, 93 categories) |
| `static/data/category_stats.json` | metadata | Per-category paper counts with yearly breakdowns |
| `static/data/timeseries.json` | metadata | Global paper count per month (164 months) |
| `static/data/fulltext/papers.parquet` | fulltext | Extracted PDF text (id + fulltext) |
| `static/data/embeddings/papers.parquet` | embeddings | 384-dim vectors (id + embedding array) |
| `static/data/embeddings/faiss.index` | embeddings | FAISS IndexFlatIP for similarity search |
| `static/data/topics.json` | ml | KMeans clusters with TF-IDF topic keywords |
| `static/data/recommendations.json` | ml | Top-10 similar papers per paper |

### Two-Machine Workflow

Run metadata on MacBook, compute-heavy stages on a GPU box:

```bash
# MacBook — metadata only
uv run python scripts/build_data.py --no-incremental

# Sync code and metadata to GPU box
./scripts/sync_data.sh push

# GPU box — compute stages
# (SSH in) uv run python scripts/build_data.py --fulltext --embeddings --ml

# Sync artifacts back to MacBook
./scripts/sync_data.sh pull

# Or one command:
./scripts/sync_data.sh full
```

### Frontend Build

```bash
npm install
npm run build
```

### Packages

**Frontend**: SvelteKit 5, D3.js, Tailwind CSS 4, TypeScript, vis-network.  
**Data Pipeline**: Daft, HuggingFace Hub, httpx, PyMuPDF, sentence-transformers, FAISS, scikit-learn.
