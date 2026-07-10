# Daft Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the planned Polars-based `build_data.py` with a Daft-based pipeline that processes the full `open-index/open-arxiv` HuggingFace dataset on both a MacBook (CPU) and an NVIDIA GPU machine from the same codebase.

**Architecture:** Single Daft pipeline in `scripts/build_data.py`. On MacBook, Daft runs CPU-only and handles metadata ETL. On GPU box, the same code activates `@daft.cls(gpus=1)` UDFs for embedding generation. Outputs land in `static/data/` — committed data (JSON, SQLite) lives in git; large artifacts (embeddings, FAISS index) are gitignored and synced via rsync.

**Tech Stack:** Python 3.11+, Daft 0.3+, HuggingFace Hub, sqlite3 (stdlib), sentence-transformers, PyTorch, FAISS (GPU box only)

## Global Constraints

- Python >= 3.11
- Daft >= 0.3.0, < 1.0.0 (replaces Polars)
- huggingface-hub >= 1.17 (existing dep)
- Output directory: `static/data/` relative to repo root
- Smaller committed outputs only — `papers.parquet`, `fulltext/`, `embeddings/`, `faiss.index` are gitignored
- GPU code uses `@daft.cls(gpus=1)` which silently degrades to CPU on machines without NVIDIA GPUs
- No pandas dependency (use Daft throughout)
- No Plotly dependency in the build script

---
### Task 1: Project Setup + Daft Data Loading

**Files:**
- Create: `scripts/build_data.py`
- Modify: `pyproject.toml` (replace Polars with Daft)
- Create: `scripts/__init__.py`

**Interfaces:**
- Produces: `load_shards(incremental: bool = True) -> daft.DataFrame` — loads all shards from HuggingFace, deduplicates, strips vector columns if present
- Produces: `parse_args() -> argparse.Namespace`

- [ ] **Step 1: Update pyproject.toml dependencies**

Replace `polars>=1.20` with `daft>=0.3.0,<1.0.0`:

```toml
dependencies = [
    "daft>=0.3.0,<1.0.0",
    "numpy>=2.4",
    "huggingface-hub>=1.17.0",
]
```

- [ ] **Step 2: Install and verify**

```bash
uv sync
uv run python -c "import daft; print(daft.__version__)"
```

Expected: prints version >= 0.3

- [ ] **Step 3: Create `scripts/__init__.py`**

Empty file.

- [ ] **Step 4: Write the data-loading skeleton and CLI entry point**

Write `scripts/build_data.py` with the argument parser and shard-loading logic:

```python
import argparse
import json
import os
import sqlite3
from pathlib import Path
from collections import defaultdict

import daft
from daft import col as c
from huggingface_hub import snapshot_download

HERE = Path(__file__).resolve().parent.parent
DATA_DIR = HERE / "static" / "data"

REMOTE_REPO = "open-index/open-arxiv"

# ── category aliases from labels.py (inline to avoid Streamlit dep) ──
CATEGORY_ALIASES = {
    "math-ph": "math.MP",
    "chao-dyn": "nlin.CD",
    "solv-int": "nlin.SI",
    "cmp-lg": "cs.CL",
    "patt-sol": "nlin.PS",
    "dg-ga": "math.DG",
    "comp-gas": "nlin.CG",
}

# ── domain grouping and colors ──
DOMAIN_NAMES = {
    "cs": "Computer Science",
    "math": "Mathematics",
    "stat": "Statistics",
    "physics": "Physics",
    "cond-mat": "Condensed Matter",
    "astro-ph": "Astrophysics",
    "eess": "Electrical Engineering & Systems Science",
    "q-bio": "Quantitative Biology",
    "q-fin": "Quantitative Finance",
    "econ": "Economics",
    "nlin": "Nonlinear Sciences",
    "nucl": "Nuclear Physics",
    "bayes-an": "Bayesian Analysis",
}

DOMAIN_COLORS = {
    "cs": "#1f77b4",
    "math": "#ff7f0e",
    "stat": "#2ca02c",
    "physics": "#d62728",
    "astro-ph": "#9467bd",
    "cond-mat": "#8c564b",
    "gr-qc": "#7f7f7f",
    "quant-ph": "#bcbd22",
    "eess": "#17becf",
    "q-bio": "#aec7e8",
    "q-fin": "#ffbb78",
    "econ": "#98df8a",
    "nlin": "#ff9896",
    "nucl": "#c5b0d5",
    "nucl-th": "#c5b0d5",
    "nucl-ex": "#c5b0d5",
    "hep-th": "#e377c2",
    "hep-ph": "#e377c2",
    "hep-lat": "#e377c2",
    "hep-ex": "#e377c2",
    "bayes-an": "#9edae5",
}


def load_shards(incremental: bool = True) -> daft.DataFrame:
    """Load all Parquet shards from HuggingFace, deduplicate, strip vectors."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if incremental and (DATA_DIR / "papers.parquet").exists():
        existing = daft.read_parquet(str(DATA_DIR / "papers.parquet"))
        max_date = existing.select(c("update_date").max()).collect()[0]["update_date"]
        print(f"Existing dataset: {len(existing):,} papers, last date {max_date}")
    else:
        existing = None
        max_date = None

    print("Downloading shards from HuggingFace…")
    cache_path = snapshot_download(REMOTE_REPO, repo_type="dataset")
    shard_files = sorted(Path(cache_path).glob("*.parquet"))

    dfs = []
    for f in shard_files:
        print(f"  Loading {f.name}…")
        df = daft.read_parquet(str(f))
        if "vector" in df.schema().column_names():
            df = df.exclude("vector")

        if max_date is not None and "update_date" in df.schema().column_names():
            df = df.where(c("update_date") > max_date)

        if "authors_parsed" in df.schema().column_names():
            col_type = df.schema()["authors_parsed"]
            if col_type == daft.DataType.string():
                df = df.with_column(c("authors_parsed").apply(
                    json.loads,
                    return_dtype=daft.DataType.python(),
                ))

        if "versions" in df.schema().column_names():
            col_type = df.schema()["versions"]
            if col_type == daft.DataType.string():
                df = df.with_column(c("versions").apply(
                    json.loads,
                    return_dtype=daft.DataType.python(),
                ))

        dfs.append(df)

    if not dfs:
        print("No new shards to process.")
        return existing

    full = daft.concat(dfs)
    full = full.distinct(subset=["id"])
    print(f"New papers loaded: {len(full):,}")

    if existing is not None:
        full = daft.concat([existing, full]).distinct(subset=["id"])

    return full


def parse_args():
    parser = argparse.ArgumentParser(description="Build arXiv explorer static data")
    parser.add_argument("--incremental", action="store_true", default=True,
                        help="Only process new shards (default: True)")
    parser.add_argument("--no-incremental", action="store_false", dest="incremental",
                        help="Full rebuild from all shards")
    parser.add_argument("--sample", type=int, default=0,
                        help="Use a random sample of N papers (for testing)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    df = load_shards(incremental=args.incremental)

    if df is None:
        print("No data to process.")
        exit(0)

    if args.sample:
        df = df.sample(min(args.sample, len(df)))
        print(f"Using sample of {len(df):,} papers")

    print(f"Total papers: {len(df):,}")
    print(f"Columns: {df.schema().column_names()}")
```

- [ ] **Step 5: Verify the script parses and imports**

Run: `uv run python scripts/build_data.py --help`

Expected: prints help text without errors

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock scripts/__init__.py scripts/build_data.py
git commit -m "feat: initial Daft data pipeline skeleton with shard loading"
```

---
### Task 2: Category Co-occurrence Graph Export

**Files:**
- Modify: `scripts/build_data.py`

**Interfaces:**
- Consumes: `df: daft.DataFrame` from Task 1
- Produces: `build_category_graph(df: daft.DataFrame) -> dict` — returns `{nodes, edges, metadata}`
- Writes: `static/data/category_graph.json`

- [ ] **Step 1: Write the category graph builder**

Add after `load_shards`:

```python
def build_category_graph(df: daft.DataFrame) -> dict:
    """Build category co-occurrence graph from papers DataFrame."""
    indexed = daft.sql("""
        SELECT ROW_NUMBER() OVER () - 1 AS _row_idx, categories
        FROM df
    """)

    exploded = indexed.with_column(
        c("categories").str.split(" ").alias("cat_list")
    ).explode("cat_list").with_column(
        c("cat_list").replace(CATEGORY_ALIASES).alias("cat_list")
    ).distinct(subset=["_row_idx", "cat_list"])

    paper_counts = exploded.group_by("cat_list").agg(
        daft.count().alias("count")
    ).sort(c("count"), descending=True)

    cooc = exploded.join(
        exploded, on="_row_idx", strategy="inner", suffix="_b"
    ).where(c("cat_list") < c("cat_list_b"))

    cooc_counts = cooc.group_by(["cat_list", "cat_list_b"]).agg(
        daft.count().alias("count")
    )

    top_n = 200
    top = paper_counts.head(top_n)
    cat_set = set(top.to_pandas()["cat_list"].tolist())

    filtered = cooc_counts.where(
        c("cat_list").is_in(list(cat_set))
        & c("cat_list_b").is_in(list(cat_set))
        & (c("count") >= 5)
    )

    pdf = filtered.to_pandas()
    node_pdf = paper_counts.to_pandas()
    node_weight = dict(zip(node_pdf["cat_list"], node_pdf["count"]))

    edge_list = pdf.to_dict("records")
    edge_list.sort(key=lambda x: -x["count"])

    top_20_per_cat: dict[str, list[dict]] = {}
    for e in edge_list:
        cat_a = e["cat_list"]
        cat_b = e["cat_list_b"]
        top_20_per_cat.setdefault(cat_a, []).append(e)
        top_20_per_cat.setdefault(cat_b, []).append(e)

    pruned_edges = []
    seen_pairs = set()
    for edges in top_20_per_cat.values():
        edges.sort(key=lambda x: -x["count"])
        for e in edges[:20]:
            pair = (e["cat_list"], e["cat_list_b"])
            if pair not in seen_pairs and e["cat_list"] in cat_set and e["cat_list_b"] in cat_set:
                seen_pairs.add(pair)
                pruned_edges.append(e)

    def domain_of(cat: str) -> str:
        return cat.split(".")[0]

    nodes = []
    for cat, weight in node_weight.items():
        if cat not in cat_set:
            continue
        dom = domain_of(cat)
        nodes.append({
            "id": cat,
            "label": cat,
            "domain": dom,
            "group": DOMAIN_NAMES.get(dom, dom),
            "weight": int(weight),
            "color": DOMAIN_COLORS.get(dom, "#999999"),
        })

    edges = [
        {"source": e["cat_list"], "target": e["cat_list_b"], "weight": int(e["count"])}
        for e in pruned_edges
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "last_updated": str(df["update_date"].max()),
        },
    }
```

- [ ] **Step 2: Wire it into main**

```python
print("Building category graph…")
cat_graph = build_category_graph(df)
(DATA_DIR / "category_graph.json").write_text(json.dumps(cat_graph, separators=(",", ":")))
print(f"  {cat_graph['metadata']['total_nodes']} nodes, {cat_graph['metadata']['total_edges']} edges")
```

- [ ] **Step 3: Test with a small sample**

Run: `uv run python scripts/build_data.py --sample 10000 --no-incremental`

Expected: `static/data/category_graph.json` created with a small graph

- [ ] **Step 4: Commit**

```bash
git add scripts/build_data.py static/data/category_graph.json
git commit -m "feat: add Daft-based category co-occurrence graph builder"
```

---
### Task 3: Author Data Export

**Files:**
- Modify: `scripts/build_data.py`

**Interfaces:**
- Consumes: `df: daft.DataFrame`
- Produces: `build_author_graph(df: daft.DataFrame) -> dict` — `{nodes, edges, metadata}`
- Produces: `build_author_rankings(df: daft.DataFrame) -> list[dict]`

- [ ] **Step 1: Write author graph builder**

```python
def build_author_graph(df: daft.DataFrame) -> dict:
    def format_author(names: list | None) -> str:
        if not names or len(names) < 2:
            return ""
        first = names[0] or ""
        last = names[1] or ""
        return f"{last} {first}".strip()

    authors = df.with_column(
        c("authors_parsed").apply(
            format_author,
            return_dtype=daft.DataType.string(),
        ).alias("full_name")
    )

    author_counts = authors.group_by("full_name").agg(
        daft.count().alias("weight")
    ).sort(c("weight"), descending=True)

    top_authors = author_counts.head(50000)
    author_set = set(top_authors.to_pandas()["full_name"].tolist())

    exploded = authors.with_column(
        c("authors_parsed").apply(
            lambda names: [format_author(n) for n in (names or []) if n and len(n) >= 2],
            return_dtype=daft.DataType.python(),
        ).alias("author_list")
    )

    pair_results = []
    for row in exploded.to_pydict():
        paper_authors = row["author_list"]
        for i in range(len(paper_authors)):
            for j in range(i + 1, len(paper_authors)):
                a, b = paper_authors[i], paper_authors[j]
                if a in author_set and b in author_set:
                    pair_results.append((a, b) if a < b else (b, a))

    from collections import Counter
    pair_counts = Counter(pair_results)
    top_pairs = pair_counts.most_common(200000)

    node_weight = dict(zip(top_authors.to_pandas()["full_name"], top_authors.to_pandas()["weight"]))
    nodes = [{"id": name, "label": name, "weight": int(w)} for name, w in node_weight.items() if name in author_set]
    edges = [{"source": a, "target": b, "weight": cnt} for (a, b), cnt in top_pairs]

    return {"nodes": nodes, "edges": edges, "metadata": {"total_nodes": len(nodes), "total_edges": len(edges)}}


def build_author_rankings(df: daft.DataFrame) -> list[dict]:
    def format_author(names: list | None) -> str:
        if not names or len(names) < 2:
            return ""
        first = names[0] or ""
        last = names[1] or ""
        return f"{last} {first}".strip()

    authors = df.with_column(
        c("authors_parsed").apply(
            format_author,
            return_dtype=daft.DataType.string(),
        ).alias("full_name")
    )

    author_counts = authors.group_by("full_name").agg(
        daft.count().alias("papers")
    ).sort(c("papers"), descending=True).head(1000)

    pdf = author_counts.to_pandas()
    max_papers = pdf["papers"].max()
    result = []
    for _, row in pdf.iterrows():
        result.append({
            "name": row["full_name"],
            "papers": int(row["papers"]),
            "relative": round(int(row["papers"]) / max_papers * 100) if max_papers else 0,
        })
    return result
```

- [ ] **Step 2: Wire into main**

```python
print("Building author graph…")
author_graph = build_author_graph(df)
(DATA_DIR / "author_graph.json").write_text(json.dumps(author_graph, separators=(",", ":")))
print(f"  {author_graph['metadata']['total_nodes']:,} nodes, {author_graph['metadata']['total_edges']:,} edges")

print("Building author rankings…")
author_rankings = build_author_rankings(df)
(DATA_DIR / "author_rankings.json").write_text(json.dumps(author_rankings, separators=(",", ":")))
print(f"  {len(author_rankings):,} ranked authors")
```

- [ ] **Step 3: Test**

Run: `uv run python scripts/build_data.py --sample 10000 --no-incremental`

Expected: `author_graph.json` and `author_rankings.json` created

- [ ] **Step 4: Commit**

```bash
git add scripts/build_data.py static/data/author_graph.json static/data/author_rankings.json
git commit -m "feat: add Daft-based author graph and rankings builders"
```

---
### Task 4: FTS5 Search Database

**Files:**
- Modify: `scripts/build_data.py`

**Interfaces:**
- Consumes: `df: daft.DataFrame`
- Produces: `build_search_db(df: daft.DataFrame, db_path: Path)` — creates sqlite3 FTS5 index on titles

- [ ] **Step 1: Write the FTS5 builder**

```python
def build_search_db(df: daft.DataFrame, db_path: Path):
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA cache_size = -8000000")

    conn.execute("""
        CREATE TABLE papers(
            id TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            authors TEXT,
            categories TEXT,
            date TEXT,
            domain TEXT
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE papers_fts USING fts5(
            id UNINDEXED, title, authors,
            tokenize='porter unicode61'
        )
    """)

    pdf = df.to_pandas()
    rows = []
    fts_rows = []
    for _, r in pdf.iterrows():
        cat_str = r.get("categories", "")
        domain = cat_str.split(".")[0] if cat_str else ""
        rows.append((
            r["id"], r.get("title", ""), r.get("abstract", "") or "",
            r.get("authors", "") or "", r.get("categories", ""),
            str(r.get("update_date", "")), domain,
        ))
        fts_rows.append((r["id"], r.get("title", ""), r.get("authors", "") or ""))

    conn.executemany("INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    conn.executemany("INSERT INTO papers_fts VALUES (?, ?, ?)", fts_rows)
    conn.execute("INSERT INTO papers_fts(papers_fts) VALUES('optimize')")
    conn.commit()
    conn.close()
```

- [ ] **Step 2: Wire into main**

```python
print("Building FTS5 search database…")
db_path = DATA_DIR / "search.db"
build_search_db(df, db_path)
size_mb = db_path.stat().st_size / 1024 / 1024
print(f"  search.db: {size_mb:.1f} MB")
```

- [ ] **Step 3: Test**

Run: `uv run python scripts/build_data.py --sample 10000 --no-incremental`

Expected: `search.db` created and queryable

```bash
uv run python -c "
import sqlite3
conn = sqlite3.connect('static/data/search.db')
cur = conn.execute(\"SELECT COUNT(*) FROM papers_fts WHERE papers_fts MATCH 'learning'\")
print(f'Search results: {cur.fetchone()[0]}')
"
```

Expected: integer count > 0

- [ ] **Step 4: Commit**

```bash
git add scripts/build_data.py static/data/search.db
git commit -m "feat: add FTS5 search database builder"
```

---
### Task 5: Category Hierarchy + Network Stats + Timeseries

**Files:**
- Modify: `scripts/build_data.py`

- [ ] **Step 1: Write builders**

```python
def build_category_hierarchy(df: daft.DataFrame) -> dict:
    exploded = df.with_column(
        c("categories").str.split(" ").alias("cat_list")
    ).explode("cat_list").with_column(
        c("cat_list").replace(CATEGORY_ALIASES).alias("cat_list")
    )

    counts = exploded.group_by("cat_list").agg(
        daft.count().alias("count")
    ).sort(c("count"), descending=True)

    pdf = counts.to_pandas()
    domains: dict[str, dict] = {}
    for _, row in pdf.iterrows():
        cat = row["cat_list"]
        cnt = int(row["count"])
        parts = cat.split(".")
        dom = parts[0]
        if dom not in domains:
            domains[dom] = {
                "id": dom,
                "label": DOMAIN_NAMES.get(dom, dom),
                "color": DOMAIN_COLORS.get(dom, "#999999"),
                "papers": 0,
                "subcategories": [],
            }
        domains[dom]["papers"] += cnt
        if len(parts) > 1:
            domains[dom]["subcategories"].append({
                "id": cat,
                "label": cat,
                "papers": cnt,
            })

    for d in domains.values():
        d["subcategories"].sort(key=lambda x: -x["papers"])

    return {
        "domains": sorted(domains.values(), key=lambda x: -x["papers"]),
        "total_papers": len(df),
        "total_categories": len(pdf),
    }


def build_network_stats(df: daft.DataFrame) -> dict:
    pdf = df.to_pandas()

    solo = pdf["authors_parsed"].apply(lambda x: len(x) if x else 0).sum()
    multi_cat = pdf["categories"].apply(lambda x: len(x.split()) > 1 if x else False).sum()

    authors_set = set()
    for _, r in pdf.iterrows():
        authors = r.get("authors_parsed") or []
        for a in authors:
            if a and len(a) >= 2:
                authors_set.add(f"{a[1] or ''} {a[0] or ''}".strip())

    cats_set = set()
    for _, r in pdf.iterrows():
        c = r.get("categories") or ""
        for cat in c.split():
            cats_set.add(CATEGORY_ALIASES.get(cat, cat))

    return {
        "total_papers": len(df),
        "single_author_papers": int(solo),
        "multi_author_papers": len(df) - int(solo),
        "multi_category_papers": int(multi_cat),
        "categories": len(cats_set),
        "authors": len(authors_set),
    }


def build_timeseries(df: daft.DataFrame, ts_dir: Path):
    ts_dir.mkdir(parents=True, exist_ok=True)

    monthly = df.with_column(
        c("update_date").cast(daft.DataType.string()).str.slice(0, 7).alias("year_month"),
        c("categories").str.split(" ").alias("cat_list"),
    ).explode("cat_list").with_column(
        c("cat_list").replace(CATEGORY_ALIASES).alias("cat_list")
    ).group_by(["year_month", "cat_list"]).agg(
        daft.count().alias("count")
    ).sort(c("year_month"))

    pdf = monthly.to_pandas()
    by_month: dict[str, dict[str, int]] = {}
    for _, row in pdf.iterrows():
        ym = row["year_month"]
        cat = row["cat_list"]
        cnt = int(row["count"])
        if ym not in by_month:
            by_month[ym] = {}
        by_month[ym][cat] = cnt

    for ym, cats in sorted(by_month.items()):
        (ts_dir / f"{ym}.json").write_text(
            json.dumps(cats, separators=(",", ":"))
        )
```

- [ ] **Step 2: Wire into main**

```python
print("Building category hierarchy…")
hierarchy = build_category_hierarchy(df)
(DATA_DIR / "category_hierarchy.json").write_text(json.dumps(hierarchy, separators=(",", ":")))
print(f"  {len(hierarchy['domains'])} domains")

print("Building network stats…")
stats = build_network_stats(df)
(DATA_DIR / "network_stats.json").write_text(json.dumps(stats, separators=(",", ":")))
print(f"  {stats['total_papers']:,} papers, {stats['authors']:,} authors")

print("Building time series…")
ts_dir = DATA_DIR / "timeseries"
build_timeseries(df, ts_dir)
ts_files = list(ts_dir.glob("*.json"))
print(f"  {len(ts_files)} monthly files")

print("Saving deduplicated master…")
df.write_parquet(str(DATA_DIR / "papers.parquet"))
print("Done.")
```

- [ ] **Step 3: Test**

Run: `uv run python scripts/build_data.py --sample 5000 --no-incremental`

Expected all output files created:
```
static/data/category_graph.json
static/data/category_hierarchy.json
static/data/author_graph.json
static/data/author_rankings.json
static/data/network_stats.json
static/data/search.db
static/data/timeseries/2024-01.json (etc.)
static/data/papers.parquet
```

- [ ] **Step 4: Verify search.db is queryable**

```bash
uv run python -c "
import sqlite3
conn = sqlite3.connect('static/data/search.db')
cur = conn.execute('SELECT COUNT(*) FROM papers_fts')
print(f'Total indexed: {cur.fetchone()[0]}')
cur = conn.execute(\"SELECT id, title FROM papers_fts WHERE papers_fts MATCH 'machine' LIMIT 3\")
for row in cur:
    print(f'  {row[0]}: {row[1][:60]}...')
"
```

- [ ] **Step 5: Verify JSON files are valid**

```bash
uv run python -c "
import json
files = ['category_graph.json', 'category_hierarchy.json', 'author_rankings.json', 'network_stats.json']
for f in files:
    data = json.load(open(f'static/data/{f}'))
    print(f'{f}: OK ({len(data)} keys)')
author_graph = json.load(open('static/data/author_graph.json'))
print(f'author_graph.json: {author_graph[\"metadata\"][\"total_nodes\"]} nodes, {author_graph[\"metadata\"][\"total_edges\"]} edges')
"
```

- [ ] **Step 6: Add .gitignore for large generated files**

```bash
cat >> .gitignore << 'EOF'

# Daft pipeline large generated data
static/data/papers.parquet
static/data/fulltext/
static/data/embeddings/
static/data/faiss.index
EOF
```

- [ ] **Step 7: Commit**

```bash
git add scripts/build_data.py static/data/ .gitignore
git commit -m "feat: complete Daft metadata pipeline with hierarchy, stats, and timeseries"
```

---
### Task 6: Full-text Extraction Pipeline (Phase 2)

> **Note:** Full-text extraction from actual arXiv PDFs/LaTeX requires access to `gs://arxiv-dataset` (1.1TB) or `Vidushee/ArXiv-Papers-150K` (285GB). This task implements the architecture with an abstract-only fallback by default. Enable actual PDF/LaTeX extraction once the storage sources are configured.

**Files:**
- Modify: `scripts/build_data.py` (add extract mode)
- Create: `scripts/text_extractor.py` — modular PDF/LaTeX text extraction

**Interfaces:**
- Produces: `static/data/fulltext/papers.parquet` — `id` + `text` columns
- Checkpoint: `static/data/fulltext/checkpoint.db` — tracks processed papers

- [ ] **Step 1: Write text extraction module**

```python
"""Text extraction from arXiv PDFs and LaTeX sources."""

import json
import sqlite3
from pathlib import Path

import daft
from daft import col as c


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    import fitz
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def extract_text_from_latex(latex_path: str) -> str:
    """Extract clean text from LaTeX source."""
    import re
    raw = Path(latex_path).read_text(encoding="utf-8", errors="replace")
    # Remove comments
    text = re.sub(r"(?<!\\)%.*", "", raw)
    # Remove LaTeX commands
    text = re.sub(r"\\[a-zA-Z]+(\[[^\]]*\])*(\{[^}]*\})*", " ", text)
    # Remove math mode
    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(r"\\\[.*?\\\]", " ", text, flags=re.DOTALL)
    # Clean whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def run_text_extraction(
    df: daft.DataFrame,
    text_dir: Path,
    source: str = "gcs",
):
    """Extract full text for all papers in the DataFrame."""
    text_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = text_dir / "checkpoint.db"

    conn = sqlite3.connect(str(checkpoint_path))
    conn.execute("CREATE TABLE IF NOT EXISTS processed (id TEXT PRIMARY KEY)")

    processed = set(row[0] for row in conn.execute("SELECT id FROM processed"))

    texts = []
    batch_size = 1000

    pdf = df.to_pandas()
    for i, (_, row) in enumerate(pdf.iterrows()):
        paper_id = row["id"]
        if paper_id in processed:
            continue

        try:
            # Sources:
        #   GCS:           gs://arxiv-dataset (1.1TB PDFs, public bucket)
        #   HuggingFace:   Vidushee/ArXiv-Papers-150K (285GB LaTeX, 150K AI/ML papers)
        # For now, fall back to abstract-only extraction.
            if source == "abstract":
                text = row.get("abstract", "") or ""
            else:
                print(f"  Source '{source}' not yet implemented — using abstract fallback")
                text = row.get("abstract", "") or ""

            texts.append({"id": paper_id, "text": text})
            conn.execute("INSERT INTO processed VALUES (?)", (paper_id,))
            conn.commit()

            if len(texts) >= batch_size:
                daft.from_pydict({k: [d[k] for d in texts] for k in texts[0]}).write_parquet(
                    str(text_dir / "papers.parquet"),
                    mode="append",
                )
                texts = []
                print(f"  Processed {i + 1}/{len(pdf)} papers")

        except Exception as e:
            print(f"  Failed on {paper_id}: {e}")

    if texts:
        daft.from_pydict({k: [d[k] for d in texts] for k in texts[0]}).write_parquet(
            str(text_dir / "papers.parquet"),
            mode="append",
        )

    conn.close()
    print(f"Text extraction complete. {len(pdf)} papers processed.")
```

- [ ] **Step 2: Wire text extraction mode into CLI**

```python
def parse_args():
    # ... existing args ...
    parser.add_argument("--extract-text", action="store_true",
                        help="Run full-text extraction (GPU box only)")
    parser.add_argument("--text-source", choices=["gcs", "huggingface", "abstract"], default="abstract",
                        help="Source for full-text extraction")
```

- [ ] **Step 3: Run extraction on a small test sample**

Run: `uv run python scripts/build_data.py --sample 100 --no-incremental --extract-text`

Expected: `static/data/fulltext/papers.parquet` created with extracted text

- [ ] **Step 4: Commit**

```bash
git add scripts/text_extractor.py scripts/build_data.py
git commit -m "feat: add full-text extraction pipeline with checkpointing"
```

---
### Task 7: Embedding Generation with Daft GPU UDF (Phase 2)

**Files:**
- Create: `scripts/embedder.py` — Daft GPU UDF for embedding generation
- Modify: `scripts/build_data.py` (add embed mode)

**Interfaces:**
- Consumes: `static/data/fulltext/papers.parquet` from Task 6
- Produces: `static/data/embeddings/papers.parquet` — `id` + `embedding` columns
- Produces: `static/data/embeddings/faiss.index` — FAISS index for similarity search

- [ ] **Step 1: Write Daft GPU UDF embedder**

```python
"""GPU-accelerated embedding generation using Daft's @daft.cls(gpus=1)."""

import daft
from daft import col as c
from pathlib import Path


@daft.cls(gpus=1)
class EmbeddingGenerator:
    """Daft GPU UDF. On CPU-only machines, Daft degrades gracefully."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        import torch
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        self.dim = self.model.get_sentence_embedding_dimension()

    def __call__(self, texts: list[str]) -> list[list[float]]:
        """Process a batch of texts. Managed automatically by Daft."""
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()


@daft.cls(gpus=1)
class FaissIndexBuilder:
    """Build a FAISS index from generated embeddings."""

    def __init__(self):
        import faiss
        self.faiss = faiss

    def __call__(self, embeddings: list[list[float]]) -> bytes:
        import numpy as np
        dim = len(embeddings[0]) if embeddings else 0
        index = self.faiss.IndexFlatIP(dim)
        index.add(np.array(embeddings, dtype=np.float32))
        import io
        buf = io.BytesIO()
        self.faiss.write_index(index, buf)
        return buf.getvalue()
```

- [ ] **Step 2: Wire embedding mode into build_data.py**

```python
def run_embeddings(text_parquet: Path, embed_dir: Path):
    """Generate embeddings from extracted text using Daft GPU UDF."""
    embed_dir.mkdir(parents=True, exist_ok=True)

    df = daft.read_parquet(str(text_parquet))

    print(f"Generating embeddings for {len(df):,} papers on {('GPU' if ___ else 'CPU')}…")

    embedded = df.with_column(
        c("text").apply(EmbeddingGenerator(), return_dtype=daft.DataType.python()).alias("embedding")
    )

    embedded = embedded.exclude("text")
    embedded.write_parquet(str(embed_dir / "papers.parquet"))

    print(f"Embeddings saved to {embed_dir / 'papers.parquet'}")
```

- [ ] **Step 3: Build FAISS index**

```python
def build_faiss_index(embed_parquet: Path, index_path: Path):
    """Build FAISS index from generated embeddings."""
    df = daft.read_parquet(str(embed_parquet))
    embeddings = df.select(c("embedding")).to_pandas()["embedding"].tolist()

    import numpy as np
    import faiss

    dim = len(embeddings[0])
    index = faiss.IndexFlatIP(dim)
    index.add(np.array(embeddings, dtype=np.float32))
    faiss.write_index(index, str(index_path))
    print(f"FAISS index saved to {index_path} ({os.path.getsize(index_path) / 1024 / 1024:.1f} MB)")
```

- [ ] **Step 4: Test on GPU box**

Run on the NVIDIA machine:
```bash
uv run python scripts/build_data.py --sample 1000 --no-incremental --extract-text
uv run python scripts/build_data.py --run-embeddings
```

Expected: embeddings generated, FAISS index created

- [ ] **Step 5: Commit**

```bash
git add scripts/embedder.py scripts/build_data.py
git commit -m "feat: add GPU-accelerated embedding generation with Daft GPU UDF"
```

---
### Task 8: ML Pipeline (Phase 2)

**Files:**
- Create: `scripts/ml_pipeline.py`
- Modify: `scripts/build_data.py` (add ml mode)

**Interfaces:**
- Consumes: embeddings from Task 7
- Produces: `static/data/topics.json` — paper → topic assignments
- Produces: `static/data/recommendations.json` — paper → top-10 similar papers

- [ ] **Step 1: Write topic modeling module**

```python
"""Topic modeling and clustering on arXiv embeddings."""

import json
from pathlib import Path

import daft
from daft import col as c
import numpy as np
from sklearn.cluster import HDBSCAN


def run_topic_modeling(embed_parquet: Path, output_path: Path):
    """Run HDBSCAN clustering on paper embeddings."""
    df = daft.read_parquet(str(embed_parquet))
    pdf = df.to_pandas()

    embeddings = np.array(pdf["embedding"].tolist(), dtype=np.float32)
    ids = pdf["id"].tolist()

    print(f"Clustering {len(embeddings):,} papers with HDBSCAN…")
    clusterer = HDBSCAN(min_cluster_size=50, metric="euclidean")
    labels = clusterer.fit_predict(embeddings)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int((labels == -1).sum())

    topics = [
        {"id": pid, "topic": int(label)}
        for pid, label in zip(ids, labels)
    ]

    result = {
        "papers": topics,
        "metadata": {
            "n_papers": len(topics),
            "n_clusters": n_clusters,
            "n_noise": n_noise,
            "method": "HDBSCAN",
        },
    }

    output_path.write_text(json.dumps(result, separators=(",", ":")))
    print(f"Topics saved to {output_path}: {n_clusters} clusters, {n_noise} noise points")
```

- [ ] **Step 2: Write recommendation module**

```python
def build_recommendations(embed_parquet: Path, index_path: Path, output_path: Path, top_k: int = 10):
    """Build paper recommendations from FAISS index."""
    import faiss

    df = daft.read_parquet(str(embed_parquet))
    pdf = df.to_pandas()
    ids = pdf["id"].tolist()
    embeddings = np.array(pdf["embedding"].tolist(), dtype=np.float32)

    index = faiss.read_index(str(index_path))
    distances, indices = index.search(embeddings, top_k + 1)

    recommendations = []
    for i, paper_id in enumerate(ids):
        # Skip self-match (first result)
        similar = [
            {"id": ids[idx], "score": float(dist)}
            for idx, dist in zip(indices[i][1:], distances[i][1:])
            if idx < len(ids)
        ]
        recommendations.append({
            "id": paper_id,
            "similar": similar[:top_k],
        })

    output_path.write_text(json.dumps(recommendations, separators=(",", ":")))
    print(f"Recommendations saved to {output_path}")
```

- [ ] **Step 3: Wire into CLI**

```python
parser.add_argument("--run-ml", action="store_true",
                    help="Run topic modeling and recommendations")
```

- [ ] **Step 4: Test on GPU box**

```bash
uv run python scripts/build_data.py --sample 5000 --no-incremental --extract-text --run-embeddings --run-ml
```

Expected: `topics.json` and `recommendations.json` created

- [ ] **Step 5: Commit**

```bash
git add scripts/ml_pipeline.py scripts/build_data.py
git commit -m "feat: add HDBSCAN topic modeling and FAISS recommendation pipeline"
```

---
### Task 9: Cross-Machine Sync and Final Integration (Phase 2)

**Files:**
- Modify: `.gitignore`
- Create: `scripts/sync_from_gpu.sh`

- [ ] **Step 1: Write GPU sync script**

```bash
#!/usr/bin/env bash
# Sync generated artifacts from GPU machine to local dev machine.
# Run on the MacBook after the GPU box finishes a pipeline run.
set -euo pipefail

GPU_HOST="${1:-gpu-box}"
REPO_DIR="${2:-$(dirname "$0")/..}"

rsync -avz --progress \
  "$GPU_HOST:arxiv-data-explorer/static/data/fulltext/" \
  "$REPO_DIR/static/data/fulltext/"

rsync -avz --progress \
  "$GPU_HOST:arxiv-data-explorer/static/data/embeddings/" \
  "$REPO_DIR/static/data/embeddings/"

rsync -avz --progress \
  "$GPU_HOST:arxiv-data-explorer/static/data/faiss.index" \
  "$REPO_DIR/static/data/faiss.index"

echo "Sync complete."
```

- [ ] **Step 2: Update .gitignore for large artifacts**

```bash
cat >> .gitignore << 'EOF'

# Daft pipeline large generated data
static/data/papers.parquet
static/data/fulltext/
static/data/embeddings/
static/data/faiss.index
static/data/timeseries/
EOF
```

- [ ] **Step 3: Run full pipeline on MacBook (metadata only)**

```bash
uv run python scripts/build_data.py --no-incremental
```

Expected: all metadata JSON/SQLite files generated, committed outputs work

- [ ] **Step 4: Verify frontend still works**

```bash
npm run build
```

Expected: site builds without errors, all data files present

- [ ] **Step 5: Commit final integration**

```bash
git add scripts/sync_from_gpu.sh .gitignore
git commit -m "chore: add GPU sync script and finalize pipeline integration"
git add scripts/build_data.py static/data/
git commit -m "feat: complete Daft pipeline — metadata, fulltext, embeddings, ML"
```
