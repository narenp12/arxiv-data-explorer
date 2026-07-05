import argparse
import json
import sqlite3
from pathlib import Path

import polars as pl
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
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if incremental and (DATA_DIR / "papers.parquet").exists():
        existing = pl.read_parquet(DATA_DIR / "papers.parquet")
        max_date = existing["update_date"].max()
        print(f"Existing dataset: {len(existing):,} papers, last date {max_date}")
    else:
        existing = None
        max_date = None

    print("Downloading shards from HuggingFace\u2026")
    cache_path = snapshot_download(REMOTE_REPO, repo_type="dataset")
    shard_files = sorted(Path(cache_path).rglob("*.parquet"))

    dfs = []
    for f in shard_files:
        print(f"  Loading {f.name}\u2026")
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


def build_search_db(df: pl.DataFrame, db_path: Path):
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

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Building category graph\u2026")
    cat_graph = build_category_graph(df)
    (DATA_DIR / "category_graph.json").write_text(json.dumps(cat_graph, separators=(",", ":")))
    print(f"  {cat_graph['metadata']['total_nodes']} nodes, {cat_graph['metadata']['total_edges']} edges")

    print("Building author graph\u2026")
    author_graph = build_author_graph(df)
    (DATA_DIR / "author_graph.json").write_text(json.dumps(author_graph, separators=(",", ":")))
    print(f"  {author_graph['metadata']['total_nodes']:,} nodes, {author_graph['metadata']['total_edges']:,} edges")

    print("Building author rankings\u2026")
    author_rankings = build_author_rankings(df)
    (DATA_DIR / "author_rankings.json").write_text(json.dumps(author_rankings, separators=(",", ":")))
    print(f"  {len(author_rankings):,} ranked authors")

    print("Building FTS5 search database\u2026")
    db_path = DATA_DIR / "search.db"
    build_search_db(df, db_path)
    size_mb = db_path.stat().st_size / 1024 / 1024
    print(f"  search.db: {size_mb:.1f} MB")

    df.write_parquet(DATA_DIR / "papers.parquet")

    print(f"Total papers: {len(df):,}")
    print(f"Columns: {df.columns}")
