# Daft-Based Data Pipeline — Design

> A single Daft pipeline that processes the complete arXiv corpus (metadata, full-text, embeddings, ML) and runs on both a MacBook (CPU) and an NVIDIA GPU machine with zero code changes.

## Motivation

Replace the planned Polars-based data pipeline with Daft to handle the full arXiv corpus end-to-end:
- **Metadata**: `open-index/open-arxiv` (1.4GB, 2.99M papers, 417 Parquet shards)
- **Full-text**: PDF/LaTeX extraction from GCS or HuggingFace
- **Embeddings**: GPU-accelerated inference for semantic search
- **ML**: Topic modeling, clustering, recommendation

Daft provides the single framework for all layers, with automatic CPU/GPU adaptation.

## Two-Machine Architecture

```
┌──────────────────────┐       ┌──────────────────────────┐
│   MacBook (dev)      │       │  NVIDIA GPU Box (compute)│
│                      │       │                          │
│  Daft CPU-only       │       │  Daft GPU UDFs           │
│  ───────────         │       │  ──────────────          │
│  • Metadata ETL      │       │  • Full-text extraction  │
│  • Data exploration  │  rsync│  • Embedding inference   │
│  • Frontend dev      │◄─────│  • Topic modeling         │
│  • Static site build │       │  • Clustering            │
│                      │       │                          │
│  Outputs → git       │       │  Outputs → static/data/  │
└──────────────────────┘       └──────────────────────────┘
```

**Same codebase**, same `scripts/build_data.py`. Daft's execution engine adapts:
- On MacBook: CPU-only, runs metadata stages, skips GPU stages gracefully
- On GPU box: `@daft.cls(gpus=1)` UDFs activate automatically

## Data Flow

```
open-index/open-arxiv (HuggingFace, 417 Parquet shards, 1.4GB)
  │
  ▼
Daft read_parquet() → deduplicate → materialize (~3-5GB Arrow)
  │
  ├──► Metadata outputs (JSON, SQLite, timeseries)
  │      Runs on: both machines
  │      Daft ops: explode, join, group_by, sort
  │
  ├──► Full-text extraction (PDF → text)
  │      Runs on: GPU box (or CPU, slow)
  │      Daft ops: partition by paper, iterate, save
  │      Tooling: PyMuPDF, GROBID, or Nougat
  │
  ├──► Embedding generation
  │      Runs on: GPU box (Daft GPU UDF)
  │      Daft ops: @daft.cls(gpus=1) → HuggingFace model inference
  │      Output: vector Parquet + FAISS index
  │
  └──► ML pipeline (topic modeling, clustering)
         Runs on: GPU box
         Input: embeddings
         Output: topic assignments, cluster labels
```

## Daft CPU/GPU Adaptation

Daft's GPU UDF pattern (`@daft.cls(gpus=1)`) lets you write one class that works on both machines:

```python
import daft
from daft.daft import cls

@daft.cls(gpus=1)  # ← ignored on CPU-only machines, activates on GPU box
class EmbeddingGenerator:
    def __init__(self):
        # Runs once per worker — loads model into GPU memory
        import torch
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)

    def __call__(self, text: str) -> list[float]:
        # Runs per row (or in batches via Daft's managed batching)
        emb = self.model.encode(text)
        return emb.tolist()
```

On MacBook: Daft silently skips GPU allocation, runs UDF on CPU.
On GPU box: Daft allocates GPU, manages batching, handles memory.

## API Mapping (Polars → Daft)

| Operation | Polars | Daft |
|-----------|--------|------|
| Read Parquet | `pl.read_parquet(path)` | `daft.read_parquet(path)` |
| Drop columns | `df.drop("col")` | `df.exclude("col")` |
| Deduplicate | `df.unique(subset=["id"])` | `df.distinct(subset=["id"])` |
| Filter | `df.filter(expr)` | `df.where(expr)` |
| Add columns | `df.with_columns(...)` | `df.with_column(...)` (singular) |
| Column ref | `pl.col("x")` | `daft.col("x")` |
| Count | `pl.len().alias("n")` | `daft.count().alias("n")` |
| Group + agg | `df.group_by("x").agg(...)` | `df.group_by("x").agg(...)` |
| Sort | `df.sort("x", descending=True)` | `df.sort(daft.col("x"), descending=True)` |
| Explode | `df.explode("col")` | `df.explode("col")` |
| Sample | `df.sample(n=5000)` | `df.sample(n=5000)` |
| Replace values | `pl.col("x").replace_strict(map)` | `daft.col("x").replace(map)` |
| Split string | `pl.col("x").str.split(" ")` | `daft.col("x").str.split(" ")` |
| Slice string | `pl.col("x").str.slice(0, 7)` | `daft.col("x").str.slice(0, 7)` |
| List get | `pl.element().list.get(1)` | `daft.col("col").list.get(1)` |
| JSON decode | `pl.col("x").str.json_decode(...)` | Python UDF via `.apply()` |
| Row index | `pl.int_range(0, pl.len())` | `daft.sql("ROW_NUMBER() OVER () - 1")` |
| Iterate rows | `df.iter_rows(named=True)` | `.to_pydict()` or `.to_arrow().to_pylist()` |
| Write Parquet | `df.write_parquet(path)` | `df.write_parquet(path)` |
| GPU inference | ❌ Not supported | `@daft.cls(gpus=1)` |

## Pipeline Stages

### Stage 1: Metadata ETL (both machines)

Same scope as the original plan — loads HuggingFace Parquet, deduplicates, strips vector columns if present:

- Category co-occurrence graph → `static/data/category_graph.json`
- Author graph → `static/data/author_graph.json`
- Author rankings → `static/data/author_rankings.json`
- FTS5 search DB → `static/data/search.db`
- Category hierarchy → `static/data/category_hierarchy.json`
- Network stats → `static/data/network_stats.json`
- Timeseries → `static/data/timeseries/*.json`
- Deduplicated master → `static/data/papers.parquet`

### Stage 2: Full-text Extraction (GPU box)

Process each paper's PDF/LaTeX to extract clean text for embeddings and search:

```
GCS bucket (gs://arxiv-dataset) or HuggingFace LaTeX shards
  → Download per paper
  → Extract text (PyMuPDF for PDFs, regex for LaTeX)
  → Store as `static/data/fulltext/papers.parquet` (id + text)
  → Checkpoint: track processed papers in a SQLite DB
```

Daft role: manage the processing queue (which papers are done), update checkpoint.

### Stage 3: Embedding Generation (GPU box only)

Daft GPU UDF processes the extracted text:

```python
@daft.cls(gpus=1)
class Embedder:
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cuda")

    def __call__(self, batch: list[str]) -> list[list[float]]:
        return self.model.encode(batch).tolist()

embeddings = df.with_column(
    daft.col("text").apply(Embedder, return_dtype=daft.DataType.python())
)
embeddings.write_parquet("static/data/embeddings.parquet")
```

Outputs:
- `static/data/embeddings.parquet` — paper ID + embedding vector
- `static/data/faiss.index` — FAISS index for client-side or API-side similarity search

### Stage 4: ML Pipeline (GPU box)

On the embeddings:
- **Topic modeling**: BERTopic or HDBSCAN clustering
- **Paper recommendations**: FAISS similarity
- **Outputs**: `static/data/topics.json`, `static/data/recommendations.json`

## Key Challenges & Mitigations

### JSON Decoding

Some HuggingFace shards store `authors_parsed` and `versions` as JSON strings. Daft lacks `str.json_decode()`.

**Mitigation**: Small Python UDF, only runs on first load. Incremental runs skip it.

### GPU UDF Portability

`@daft.cls(gpus=1)` fails on a machine with no NVIDIA GPU.

**Mitigation**: Daft's managed UDF runtime handles this — on CPU-only machines, the UDF runs without GPU allocation. Test on MacBook during development; GPU acceleration activates only on the NVIDIA box.

### Cross-Machine Data Sync

Metadata outputs are generated on MacBook; embedding/ML outputs are generated on GPU box.

**Mitigation**: All outputs land in `static/data/`. The GPU box rsyncs or is pointed at the same repo with git or a shared filesystem. Only the metadata outputs need to be committed to git (they're small JSON/Parquet). Embeddings and FAISS index can be gitignored.

## File Structure

```
scripts/
  build_data.py          — Daft pipeline (all stages, conditional by machine)
  utils.py               — existing LaTeX utils (unchanged)
static/data/
  papers.parquet         — deduplicated master (gitignored — too large)
  category_graph.json    — committed
  category_hierarchy.json — committed
  author_graph.json      — committed
  author_rankings.json   — committed
  network_stats.json     — committed
  search.db              — committed (small)
  timeseries/            — committed
  fulltext/              — gitignored (extracted text)
  embeddings/            — gitignored (large vectors)
  faiss.index            — gitignored
```

## Dependency Changes

```toml
# pyproject.toml
dependencies = [
    "daft>=0.3.0,<1.0.0",
    # "polars>=1.20"  ← replace with daft
    "huggingface-hub>=1.17.0",
    "numpy>=2.4",
]
```

GPU box extras (not in pyproject.toml — installed separately):
```
pip install sentence-transformers torch torchvision faiss-gpu
```

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Daft API maturity | Medium | Medium | Pin version, test on both machines |
| GPU UDF behavior on CPU-only machine | Low | Low | Daft handles this; test to confirm |
| Full-text extraction at scale (3M PDFs) | Medium | Medium | Incremental processing with checkpointing |
| Embedding generation time (3M papers × GPU) | Low | Medium | ~2 days on a single GPU; batch overnight |
| Cross-machine sync complexity | Low | Low | Git for committed data; rsync for artifacts |
