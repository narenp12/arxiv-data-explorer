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
        print(f"Existing dataset: {existing.count_rows():,} papers, last date {max_date}")
    else:
        existing = None
        max_date = None

    print("Downloading shards from HuggingFace…")
    cache_path = snapshot_download(REMOTE_REPO, repo_type="dataset")
    pattern = str(Path(cache_path) / "**" / "*.parquet")
    full = daft.read_parquet(pattern)

    if "vector" in full.schema().column_names():
        full = full.exclude("vector")

    if max_date is not None and "update_date" in full.schema().column_names():
        full = full.where(c("update_date") > max_date)

    if "authors_parsed" in full.schema().column_names():
        col_type = full.schema()["authors_parsed"]
        if col_type == daft.DataType.string():
            full = full.with_column(c("authors_parsed").apply(
                json.loads,
                return_dtype=daft.DataType.python(),
            ))

    if "versions" in full.schema().column_names():
        col_type = full.schema()["versions"]
        if col_type == daft.DataType.string():
            full = full.with_column(c("versions").apply(
                json.loads,
                return_dtype=daft.DataType.python(),
            ))

    full = full.distinct("id")
    print(f"New papers loaded: {full.count_rows():,}")

    if existing is not None:
        full = daft.concat([existing, full]).distinct("id")

    return full


def build_category_graph(df: daft.DataFrame) -> dict:
    """Build category co-occurrence graph from papers DataFrame."""
    indexed = df._add_monotonically_increasing_id("_row_idx").select("_row_idx", "categories")

    exploded = indexed.with_column(
        "cat_list", c("categories").split(" ")
    ).explode("cat_list").with_column(
        "cat_list", c("cat_list").apply(
            lambda x: CATEGORY_ALIASES.get(x, x),
            return_dtype=daft.DataType.string(),
        )
    ).distinct("_row_idx", "cat_list")

    paper_counts = exploded.groupby("cat_list").agg(
        c("cat_list").count().alias("count")
    ).sort(c("count"), desc=True)

    cooc = exploded.join(
        exploded, on="_row_idx", how="inner", suffix="_b"
    ).where(c("cat_list") < c("cat_list_b"))

    cooc_counts = cooc.groupby(["cat_list", "cat_list_b"]).agg(
        c("cat_list").count().alias("count")
    )

    top_n = 200
    top = paper_counts.limit(top_n)
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
            "last_updated": str(df.select(c("update_date").max()).collect()[0]["update_date"]),
        },
    }


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
        df = df.sample(size=min(args.sample, df.count_rows()))
        print(f"Using sample of {args.sample:,} papers")

    print(f"Total papers: {df.count_rows():,}")
    print(f"Columns: {df.schema().column_names()}")

    print("Building category graph…")
    cat_graph = build_category_graph(df)
    (DATA_DIR / "category_graph.json").write_text(json.dumps(cat_graph, separators=(",", ":")))
    print(f"  {cat_graph['metadata']['total_nodes']} nodes, {cat_graph['metadata']['total_edges']} edges")
