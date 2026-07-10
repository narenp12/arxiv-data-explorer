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
