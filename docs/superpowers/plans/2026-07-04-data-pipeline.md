# Data Pipeline Build Script — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Single Python script (`scripts/build_data.py`) that downloads open-index/open-arxiv from HuggingFace, processes 3M papers with Polars, and exports static JSON/DB artifacts for the SvelteKit frontend.

**Architecture:** Load all Parquet shards → deduplicate → strip vector columns → build category co-occurrence graph → extract top 50K authors → build FTS5 search index on titles → export all as static files. Incremental: load existing `papers.parquet`, only process new shards.

**Tech Stack:** Python 3.11+, Polars, HuggingFace Hub, sqlite3 (stdlib), NetworkX for graph logic.

## Global Constraints

- Python >= 3.11
- Polars >= 1.20 (existing dep in pyproject.toml)
- NetworkX >= 3.4 (existing dep)
- huggingface-hub >= 1.17 (existing dep)
- Must strip `vector` column on load (~8GB per shard, not needed)
- Output directory: `static/data/` relative to repo root
- `static/data/` must be git-committable (deployed as Vercel static assets)
- No pandas dependency (use Polars throughout)
- No Plotly dependency in the build script (frontend handles viz)
- No runtime Python server needed — all outputs are static files

---
## File Structure

- `scripts/build_data.py` — the entire build pipeline
- `scripts/__init__.py` — empty, mark as package
- `static/data/papers.parquet` — deduplicated master (for incremental rebuilds)
- `static/data/category_graph.json` — category co-occurrence graph
- `static/data/category_hierarchy.json` — category drill-down tree
- `static/data/author_graph.json` — top 50K author ego-network
- `static/data/author_rankings.json` — prolific author stats
- `static/data/network_stats.json` — aggregate stats
- `static/data/search.db` — sqlite3 FTS5 index on titles
- `static/data/timeseries/` — monthly submission counts per category

---
### Task 1: Project Setup + Data Loading

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/build_data.py`

**Interfaces:**
- Produces: `load_shards()` → `pl.DataFrame` — loads all shards from HuggingFace or local cache, returns deduplicated DataFrame without `vector` column

- [ ] **Step 1: Create `scripts/__init__.py`**

Empty file.

- [ ] **Step 2: Write the data-loading skeleton and CLI entry point**

Write `scripts/build_data.py` with the argument parser and shard-loading logic:

```python
import argparse
import json
import os
import sqlite3
from pathlib import Path
from collections import defaultdict

import polars as pl
from huggingface_hub import snapshot_download

HERE = Path(__file__).resolve().parent.parent
DATA_DIR = HERE / "static" / "data"

REMOTE_REPO = "open-index/open-arxiv"
LOCAL_SAMPLE = HERE / "arxiv_random_sample.parquet"

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

# ── domain grouping and colors (from network_app.py) ──
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


def load_shards(incremental: bool = True) -> pl.DataFrame:
    """Load all Parquet shards from HuggingFace, deduplicate, strip vectors."""
    data_dir.mkdir(parents=True, exist_ok=True)

    if incremental and (DATA_DIR / "papers.parquet").exists():
        existing = pl.read_parquet(DATA_DIR / "papers.parquet")
        max_date = existing["update_date"].max()
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
        df = pl.read_parquet(f)
        if "vector" in df.columns:
            df = df.drop("vector")

        if max_date is not None and "update_date" in df.columns:
            df = df.filter(pl.col("update_date") > max_date)

        if "authors_parsed" in df.columns and df.schema["authors_parsed"] == pl.String:
            df = df.with_columns(
                pl.col("authors_parsed").str.json_decode(
                    pl.List(pl.List(pl.Utf8))
                )
            )
        if "versions" in df.columns and df.schema["versions"] == pl.String:
            df = df.with_columns(
                pl.col("versions").str.json_decode(
                    pl.List(pl.Struct([
                        pl.Field("version", pl.Utf8),
                        pl.Field("created", pl.Utf8),
                    ]))
                )
            )
        dfs.append(df)

    if not dfs:
        print("No new shards to process.")
        return existing

    full = pl.concat(dfs)
    full = full.unique(subset=["id"])
    print(f"New papers loaded: {len(full):,}")

    if existing is not None:
        full = pl.concat([existing, full]).unique(subset=["id"])

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

    if args.sample:
        df = df.sample(n=min(args.sample, len(df)))
        print(f"Using sample of {len(df):,} papers")

    print(f"Total papers: {len(df):,}")
    print(f"Columns: {df.columns}")
```

- [ ] **Step 3: Verify the script parses and imports**

Run: `uv run python scripts/build_data.py --help`
Expected: prints help text without errors

---
### Task 2: Category Co-occurrence Graph Export

**Files:**
- Modify: `scripts/build_data.py`

**Interfaces:**
- Consumes: `df: pl.DataFrame` from Task 1
- Produces: `static/data/category_graph.json` — `{nodes: [{id, label, domain, group, weight, color}], edges: [{source, target, weight}]}`

- [ ] **Step 1: Write the category graph builder**

Add after `load_shards`:

```python
def build_category_graph(df: pl.DataFrame) -> dict:
    """Build category co-occurrence graph from papers DataFrame."""
    exploded = df.select(
        pl.int_range(0, pl.len()).alias("_row_idx"),
        pl.col("categories").str.split(" "),
    ).explode("categories").with_columns(
        pl.col("categories").replace_strict(
            list(CATEGORY_ALIASES.keys()),
            list(CATEGORY_ALIASES.values()),
            default=pl.col("categories"),
        ).alias("categories")
    ).unique(subset=["_row_idx", "categories"])

    paper_counts = exploded.group_by("categories").agg(
        pl.len().alias("count")
    ).sort("count", descending=True)

    cooc = exploded.join(exploded, on="_row_idx", suffix="_b").filter(
        pl.col("categories") < pl.col("categories_b")
    )
    cooc_counts = cooc.group_by(["categories", "categories_b"]).agg(
        pl.len().alias("count")
    )

    top_n = 200
    top = paper_counts.head(top_n)
    cat_set = set(top["categories"].to_list())

    filtered = cooc_counts.filter(
        pl.col("categories").is_in(cat_set)
        & pl.col("categories_b").is_in(cat_set)
        & (pl.col("count") >= 5)
    )

    node_weight = {r["categories"]: r["count"] for r in top.iter_rows(named=True)}
    edge_list = list(filtered.iter_rows(named=True))
    edge_list.sort(key=lambda x: -x["count"])
    top_20_per_cat: dict[str, list[dict]] = {}
    for e in edge_list:
        cat_a = e["categories"]
        cat_b = e["categories_b"]
        top_20_per_cat.setdefault(cat_a, []).append(e)
        top_20_per_cat.setdefault(cat_b, []).append(e)
    pruned_edges = []
    seen_pairs = set()
    for edges in top_20_per_cat.values():
        edges.sort(key=lambda x: -x["count"])
        for e in edges[:20]:
            pair = (e["categories"], e["categories_b"])
            if pair not in seen_pairs and e["categories"] in cat_set and e["categories_b"] in cat_set:
                seen_pairs.add(pair)
                pruned_edges.append(e)

    def domain_of(cat: str) -> str:
        return cat.split(".")[0]

    nodes = []
    for cat, weight in node_weight.items():
        dom = domain_of(cat)
        nodes.append({
            "id": cat,
            "label": cat,
            "domain": dom,
            "group": DOMAIN_NAMES.get(dom, dom),
            "weight": weight,
            "color": DOMAIN_COLORS.get(dom, "#999999"),
        })

    edges = [{"source": e["categories"], "target": e["categories_b"], "weight": e["count"]} for e in pruned_edges]

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

- [ ] **Step 2: Wire it into main() and write the output**

In `if __name__ == "__main__":`, after loading df:

```python
print("Building category graph…")
cat_graph = build_category_graph(df)
(DATA_DIR / "category_graph.json").write_text(json.dumps(cat_graph, separators=(",", ":")))
print(f"  {cat_graph['metadata']['total_nodes']} nodes, {cat_graph['metadata']['total_edges']} edges")
```

- [ ] **Step 3: Test with a small sample**

Run: `uv run python scripts/build_data.py --sample 10000 --no-incremental`
Expected: script runs, `static/data/category_graph.json` created with a small graph

---
### Task 3: Author Data Export

**Files:**
- Modify: `scripts/build_data.py`

**Interfaces:**
- Consumes: `df: pl.DataFrame`
- Produces: `static/data/author_graph.json`, `static/data/author_rankings.json`

- [ ] **Step 1: Write author graph builder**

Add after `build_category_graph`:

```python
def build_author_graph(df: pl.DataFrame) -> dict:
    name_expr = (
        pl.element().list.get(1, null_on_oob=True).fill_null("")
        + " "
        + pl.element().list.get(0, null_on_oob=True).fill_null("")
    ).str.strip_chars()

    author_counts = df.select(
        pl.col("authors_parsed").list.eval(name_expr).alias("full_name")
    ).explode("full_name").group_by("full_name").agg(
        pl.len().alias("weight")
    ).sort("weight", descending=True)

    top_authors = author_counts.head(50000)
    author_set = set(top_authors["full_name"].to_list())

    exploded = df.select(
        pl.int_range(0, pl.len()).alias("_row_idx"),
        pl.col("authors_parsed").list.eval(name_expr).alias("author"),
    ).explode("author").filter(pl.col("author").is_in(author_set))

    pairs = exploded.join(
        exploded, on="_row_idx", suffix="_b"
    ).filter(pl.col("author") < pl.col("author_b")).group_by(
        ["author", "author_b"]
    ).agg(pl.len().alias("count")).sort("count", descending=True)

    node_weight = {r["full_name"]: r["weight"] for r in top_authors.iter_rows(named=True)}
    nodes = [{"id": name, "label": name, "weight": w} for name, w in node_weight.items()]
    edges = [{"source": r["author"], "target": r["author_b"], "weight": r["count"]}
             for r in pairs.head(200000).iter_rows(named=True)]

    return {"nodes": nodes, "edges": edges, "metadata": {"total_nodes": len(nodes), "total_edges": len(edges)}}


def build_author_rankings(df: pl.DataFrame) -> list[dict]:
    author_counts = df.select(
        pl.col("authors_parsed")
        .list.eval(
            (pl.element().list.get(1, null_on_oob=True).fill_null("")
             + " "
             + pl.element().list.get(0, null_on_oob=True).fill_null(""))
            .str.strip_chars()
        )
        .alias("full_name")
    ).explode("full_name").group_by("full_name").agg(
        pl.len().alias("papers")
    ).sort("papers", descending=True).head(1000)

    max_papers = author_counts["papers"].max()
    result = []
    for r in author_counts.iter_rows(named=True):
        result.append({
            "name": r["full_name"],
            "papers": r["papers"],
            "relative": round(r["papers"] / max_papers * 100) if max_papers else 0,
        })
    return result
```

- [ ] **Step 2: Build export into main**

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
Expected: author_graph.json and author_rankings.json created

---
### Task 4: FTS5 Search Database

**Files:**
- Modify: `scripts/build_data.py`

**Interfaces:**
- Consumes: `df: pl.DataFrame`
- Produces: `static/data/search.db` — sqlite3 DB with FTS5 index on paper titles

- [ ] **Step 1: Write the FTS5 builder**

```python
def build_search_db(df: pl.DataFrame, db_path: Path):
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA cache_size = -8000000")  # 8MB cache

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

    base = df.select(
        "id", "title", "abstract",
        pl.col("authors").fill_null(""),
        "categories", "update_date",
        pl.col("categories").str.split(".").list.first().alias("domain"),
    )

    rows = []
    fts_rows = []
    for r in base.iter_rows(named=True):
        rows.append((
            r["id"], r["title"], r.get("abstract", "") or "",
            r["authors"], r["categories"], r["update_date"], r["domain"],
        ))
        fts_rows.append((r["id"], r["title"], r["authors"]))

    conn.executemany(
        "INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?)", rows
    )
    conn.executemany(
        "INSERT INTO papers_fts VALUES (?, ?, ?)", fts_rows
    )
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
Expected: search.db created and queryable

```bash
python -c "
import sqlite3
conn = sqlite3.connect('static/data/search.db')
cur = conn.execute(\"SELECT COUNT(*) FROM papers_fts WHERE papers_fts MATCH 'learning'\")
print(f'Search results: {cur.fetchone()[0]}')
"
```
Expected: integer count > 0

---
### Task 5: Category Hierarchy + Network Stats + Hierarchy

**Files:**
- Modify: `scripts/build_data.py`

- [ ] **Step 1: Write builders**

```python
def build_category_hierarchy(df: pl.DataFrame) -> dict:
    exploded = df.select(
        pl.col("categories").str.split(" "),
    ).explode("categories").with_columns(
        pl.col("categories").replace_strict(
            list(CATEGORY_ALIASES.keys()),
            list(CATEGORY_ALIASES.values()),
            default=pl.col("categories"),
        ).alias("categories")
    )

    counts = exploded.group_by("categories").agg(
        pl.len().alias("count")
    ).sort("count", descending=True)

    domains: dict[str, dict] = {}
    for row in counts.iter_rows(named=True):
        cat = row["categories"]
        cnt = row["count"]
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
        "total_categories": len(counts),
    }


def build_network_stats(df: pl.DataFrame) -> dict:
    solo = df.filter(
        pl.col("authors_parsed").list.len() == 1
    ).select(pl.len()).item()

    multi_cat = df.filter(
        pl.col("categories").str.split(" ").list.len() > 1
    ).select(pl.len()).item()

    authors_col = pl.col("authors_parsed")
    n_authors = df.select(authors_col.list.len().alias("n_authors"))

    return {
        "total_papers": len(df),
        "single_author_papers": int(solo),
        "multi_author_papers": len(df) - int(solo),
        "multi_category_papers": int(multi_cat),
        "categories": len(df["categories"].str.split(" ").explode().unique()),
        "authors": len(
            df.select(
                pl.col("authors_parsed")
                .list.eval(
                    (pl.element().list.get(1, null_on_oob=True).fill_null("")
                     + " "
                     + pl.element().list.get(0, null_on_oob=True).fill_null(""))
                    .str.strip_chars()
                )
                .alias("full_name")
            ).explode("full_name").unique()
        ),
    }
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
```

---
### Task 6: Timeseries Aggregates (Causal Placeholder Data)

**Files:**
- Modify: `scripts/build_data.py`

- [ ] **Step 1: Write builder**

```python
def build_timeseries(df: pl.DataFrame, ts_dir: Path):
    ts_dir.mkdir(parents=True, exist_ok=True)

    monthly = df.with_columns(
        pl.col("update_date").str.slice(0, 7).alias("year_month"),
        pl.col("categories").str.split(" ").alias("cat_list"),
    ).explode("cat_list").with_columns(
        pl.col("cat_list").replace_strict(
            list(CATEGORY_ALIASES.keys()),
            list(CATEGORY_ALIASES.values()),
            default=pl.col("cat_list"),
        ).alias("cat_list")
    ).group_by(["year_month", "cat_list"]).agg(
        pl.len().alias("count")
    ).sort("year_month")

    by_month: dict[str, dict[str, int]] = {}
    for row in monthly.iter_rows(named=True):
        ym = row["year_month"]
        cat = row["cat_list"]
        cnt = row["count"]
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
print("Building time series…")
ts_dir = DATA_DIR / "timeseries"
build_timeseries(df, ts_dir)
ts_files = list(ts_dir.glob("*.json"))
print(f"  {len(ts_files)} monthly files")

print("Saving deduplicated master…")
df.write_parquet(DATA_DIR / "papers.parquet")
print("Done.")
```

---
### Task 7: Run Full End-to-End Test

- [ ] **Step 1: Run the full pipeline with small sample**

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

- [ ] **Step 2: Verify search.db is queryable**

```bash
python -c "
import sqlite3
conn = sqlite3.connect('static/data/search.db')
cur = conn.execute('SELECT COUNT(*) FROM papers_fts')
print(f'Total indexed: {cur.fetchone()[0]}')
cur = conn.execute(\"SELECT id, title FROM papers_fts WHERE papers_fts MATCH 'machine' LIMIT 3\")
for row in cur:
    print(f'  {row[0]}: {row[1][:60]}...')
"
```

- [ ] **Step 3: Verify JSON files are valid**

```bash
python -c "
import json
files = ['category_graph.json', 'category_hierarchy.json', 'author_rankings.json', 'network_stats.json']
for f in files:
    data = json.load(open(f'static/data/{f}'))
    print(f'{f}: OK ({len(data)} keys)')
author_graph = json.load(open('static/data/author_graph.json'))
print(f'author_graph.json: {author_graph[\"metadata\"][\"total_nodes\"]} nodes, {author_graph[\"metadata\"][\"total_edges\"]} edges')
"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/ static/data/ docs/superpowers/plans/2026-07-04-data-pipeline.md
git commit -m "feat: add data pipeline build script

- downloads open-index/open-arxiv shards from HuggingFace
- exports category co-occurrence graph, author graph, FTS5 search DB
- exports category hierarchy, network stats, time series
- supports incremental builds (new shards only)"
```
