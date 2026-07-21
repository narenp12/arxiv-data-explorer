import argparse
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from collections import defaultdict

import daft
import numpy as np
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


def load_shards(incremental: bool = True, sample: int = 0) -> daft.DataFrame:
    """Load all Parquet shards from HuggingFace, deduplicate, strip vectors."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if incremental and (DATA_DIR / "papers.parquet").exists():
        existing = daft.read_parquet(str(DATA_DIR / "papers.parquet"))
        existing = existing.distinct("id")
        print(f"Existing dataset: {existing.count_rows():,} papers")
        max_date = existing.select(c("update_date").max()).collect()[0]["update_date"]
    else:
        existing = None
        max_date = None

    print("Downloading shards from HuggingFace…")
    cache_path = Path(snapshot_download(REMOTE_REPO, repo_type="dataset"))
    shard_files = sorted(cache_path.rglob("*.parquet"))
    print(f"Found {len(shard_files)} shard files")

    if sample:
        papers_per_shard = 7200
        n_shards = max(1, sample // papers_per_shard)
        shard_files = shard_files[:n_shards]
        print(f"Using {len(shard_files)} shards for sample of ~{sample:,}")

    if max_date is not None:
        dfs = []
        for i, f in enumerate(shard_files):
            if i % 100 == 0:
                print(f"  Reading shard {i}/{len(shard_files)}…")
            df = daft.read_parquet(str(f))
            if "update_date" in df.schema().column_names():
                df = df.where(c("update_date") > max_date)
            dfs.append(df)

        if not dfs:
            print("No new shards to process.")
            return existing

        full = daft.concat(dfs)
        print(f"Concatenated {len(dfs)} shards")
    else:
        paths = [str(f) for f in shard_files]
        full = daft.read_parquet(paths)
        print(f"Read {len(paths)} shards via bulk glob")

    if "vector" in full.schema().column_names():
        full = full.exclude("vector")

    for col_name in ["authors_parsed", "versions"]:
        if col_name in full.schema().column_names():
            dtype = full.schema()[col_name].dtype
            if dtype == daft.DataType.string():
                full = full.with_column(
                    col_name,
                    c(col_name).apply(json.loads, return_dtype=daft.DataType.python()),
                )

    full = full.distinct("id")
    n = full.count_rows()
    print(f"New papers loaded: {n:,}")

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


def build_author_graph(df: daft.DataFrame) -> dict:
    """Build author co-authorship graph from papers DataFrame."""
    def format_author_list(names):
        if not names or not isinstance(names, list):
            return []
        result = []
        for n in names:
            if n and len(n) >= 2:
                last = n[1] or ""
                first = n[0] or ""
                name = f"{last} {first}".strip()
                if name:
                    result.append(name)
        return result

    authors = df.with_column(
        "author_list",
        c("authors_parsed").apply(
            format_author_list,
            return_dtype=daft.DataType.python(),
        ),
    )

    pdf = authors.select(c("author_list")).to_pandas()
    name_counts: dict[str, int] = {}
    pair_counts: dict[tuple[str, str], int] = {}

    for row in pdf["author_list"]:
        if not row:
            continue
        for name in row:
            name_counts[name] = name_counts.get(name, 0) + 1
        for i in range(len(row)):
            for j in range(i + 1, len(row)):
                a, b = (row[i], row[j]) if row[i] < row[j] else (row[j], row[i])
                pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1

    top_authors = sorted(name_counts.items(), key=lambda x: -x[1])[:10000]
    author_set = {a for a, _ in top_authors}

    filtered_pairs = [(a, b, c) for (a, b), c in pair_counts.items()
                      if a in author_set and b in author_set]
    filtered_pairs.sort(key=lambda x: -x[2])

    nodes = [{"id": name, "label": name, "weight": cnt} for name, cnt in top_authors]
    edges = [{"source": a, "target": b, "weight": cnt} for a, b, cnt in filtered_pairs[:200000]]

    return {"nodes": nodes, "edges": edges, "metadata": {"total_nodes": len(nodes), "total_edges": len(edges)}}


def build_author_rankings(df: daft.DataFrame) -> list[dict]:
    """Build top author rankings by paper count."""
    def format_author_list(names):
        if not names or not isinstance(names, list):
            return []
        result = []
        for n in names:
            if n and len(n) >= 2:
                last = n[1] or ""
                first = n[0] or ""
                name = f"{last} {first}".strip()
                if name:
                    result.append(name)
        return result

    authors = df.with_column(
        "author_list",
        c("authors_parsed").apply(
            format_author_list,
            return_dtype=daft.DataType.python(),
        ),
    )

    pdf = authors.select(c("author_list")).to_pandas()
    name_counts: dict[str, int] = {}
    for row in pdf["author_list"]:
        if not row:
            continue
        for name in row:
            name_counts[name] = name_counts.get(name, 0) + 1

    top = sorted(name_counts.items(), key=lambda x: -x[1])[:1000]
    max_count = top[0][1] if top else 1

    return [
        {"name": name, "papers": cnt, "relative": round(cnt / max_count * 100)}
        for name, cnt in top
    ]


def build_category_hierarchy(df: daft.DataFrame) -> dict:
    """Build category hierarchy tree with per-category and per-domain counts."""
    pdf = df.select(c("id"), c("categories")).to_pandas()

    domain_counts: dict[str, dict] = {}
    cat_papers: dict[str, set] = {}

    for _, row in pdf.iterrows():
        cats = str(row["categories"]).split()
        doc_id = row["id"]
        for cat in cats:
            cat = CATEGORY_ALIASES.get(cat, cat)
            if "." in cat:
                dom = cat.split(".")[0]
            else:
                dom = cat

            domain_counts.setdefault(dom, {"id": dom, "count": 0, "children": {}})
            domain_counts[dom]["count"] += 1

            cat_papers.setdefault(cat, set()).add(doc_id)

    for dom in domain_counts:
        domain_counts[dom]["children"] = [
            {"id": cat, "label": cat, "papers": len(papers)}
            for cat, papers in cat_papers.items()
            if (cat.split(".")[0] if "." in cat else cat) == dom
        ]
        domain_counts[dom]["children"].sort(key=lambda x: -x["papers"])

    nodes = sorted(domain_counts.values(), key=lambda x: -x["count"])

    domains = [
        {
            "id": d["id"],
            "label": DOMAIN_NAMES.get(d["id"], d["id"]),
            "color": DOMAIN_COLORS.get(d["id"], "#999999"),
            "papers": d["count"],
            "subcategories": d["children"],
        }
        for d in nodes
    ]

    return {
        "domains": domains,
        "total_papers": sum(d["count"] for d in nodes),
        "total_categories": len(cat_papers),
    }


def build_category_stats(df: daft.DataFrame) -> dict:
    """Build category paper counts and yearly time series per category."""
    indexed = df._add_monotonically_increasing_id("_row_idx") \
        .select("_row_idx", "categories", "update_date")

    exploded = indexed.with_column(
        "cat_list", c("categories").split(" ")
    ).explode("cat_list").with_column(
        "cat_list", c("cat_list").apply(
            lambda x: CATEGORY_ALIASES.get(x, x),
            return_dtype=daft.DataType.string(),
        )
    ).with_column(
        "year", c("update_date").apply(
            lambda x: str(x)[:4] if x else None,
            return_dtype=daft.DataType.string(),
        )
    ).distinct("_row_idx", "cat_list", "year")

    year_counts = exploded.groupby(["cat_list", "year"]).agg(
        c("cat_list").count().alias("count")
    ).sort(c("year"))

    total_counts = exploded.groupby("cat_list").agg(
        c("cat_list").count().alias("total")
    ).sort(c("total"), desc=True)

    total_pdf = total_counts.to_pandas()
    years_pdf = year_counts.to_pandas()

    category_data = {}
    for _, r in total_pdf.iterrows():
        cat = r["cat_list"]
        category_data[cat] = {"id": cat, "total": int(r["total"]), "by_year": {}}

    for _, r in years_pdf.iterrows():
        cat = r["cat_list"]
        if cat in category_data:
            category_data[cat]["by_year"][str(r["year"])] = int(r["count"])

    return {
        "categories": sorted(category_data.values(), key=lambda x: -x["total"]),
        "total_papers": exploded.distinct("_row_idx").count_rows(),
    }


def build_timeseries(df: daft.DataFrame) -> list[dict]:
    """Build monthly paper publication counts."""
    pdf = df.select(c("update_date")).to_pandas()
    pdf["update_date"] = pdf["update_date"].astype(str)

    pdf = pdf[pdf["update_date"].str.match(r"^\d{4}-\d{2}-\d{2}$")]
    pdf["year_month"] = pdf["update_date"].str[:7]

    monthly = pdf.groupby("year_month").size().reset_index()
    monthly.columns = ["month", "count"]
    monthly = monthly.sort_values("month")

    return [{"month": r["month"], "count": int(r["count"])} for _, r in monthly.iterrows()]


def build_search_db(df: daft.DataFrame) -> dict:
    """Build SQLite FTS5 search index over id, title, abstract, authors, categories."""
    db_path = DATA_DIR / "search.db"
    if db_path.exists():
        db_path.unlink(missing_ok=True)

    fields = ["id", "title", "abstract", "authors", "categories", "update_date"]
    pdf = df.select(*[c(f) for f in fields]).to_pandas()

    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("PRAGMA cache_size=-80000")

    con.execute("""CREATE VIRTUAL TABLE papers_fts USING fts5(
        id, title, abstract, authors, categories,
        tokenize='porter unicode61'
    )""")

    batch_size = 5000
    total = len(pdf)
    for start in range(0, total, batch_size):
        batch = pdf.iloc[start:start + batch_size]
        rows = []
        for _, r in batch.iterrows():
            authors_str = r.get("authors", "") or ""
            abstract_str = r.get("abstract", "") or ""
            title_str = r.get("title", "") or ""
            cat_str = r.get("categories", "") or ""
            doc_id = r.get("id", "") or ""
            rows.append((doc_id, title_str, abstract_str, authors_str, cat_str))
        con.executemany(
            "INSERT INTO papers_fts (id, title, abstract, authors, categories) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        con.commit()
        print(f"  Indexed {start + len(batch):,}/{total:,}")

    con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta (key, value) VALUES (?, ?)",
                ("last_updated", str(pdf["update_date"].max())))
    con.execute("INSERT INTO meta (key, value) VALUES (?, ?)",
                ("total_papers", str(total)))
    con.commit()
    con.close()

    return {"total_papers": total, "db_path": str(db_path), "columns": fields}


def setup_fulltext_checkpoint() -> tuple[Path, set[str]]:
    """Return (db_path, set_of_processed_ids) for incremental fulltext."""
    fulltext_dir = DATA_DIR / "fulltext"
    fulltext_dir.mkdir(parents=True, exist_ok=True)
    db_path = fulltext_dir / "checkpoint.db"
    if db_path.exists():
        con = sqlite3.connect(str(db_path))
        done = {r[0] for r in con.execute("SELECT paper_id FROM done").fetchall()}
        con.close()
    else:
        con = sqlite3.connect(str(db_path))
        con.execute("CREATE TABLE done (paper_id TEXT PRIMARY KEY, extracted_at TEXT)")
        con.commit()
        con.close()
        done = set()
    return db_path, done


def build_fulltext(df: daft.DataFrame, limit: int = 0) -> dict:
    """Download PDFs and extract full text for papers lacking it."""
    import httpx
    import fitz
    from concurrent.futures import ThreadPoolExecutor, as_completed

    fulltext_dir = DATA_DIR / "fulltext"
    out_path = fulltext_dir / "papers.parquet"
    db_path, done_ids = setup_fulltext_checkpoint()

    pdf = df.select(c("id")).to_pandas()
    pdf = pdf[~pdf["id"].isin(done_ids)]

    if limit > 0:
        pdf = pdf.head(limit)

    total = len(pdf)
    if total == 0:
        print("  All papers already have fulltext.")
        return {"processed": 0, "total": total, "path": str(out_path)}

    def extract_one(paper_id: str) -> dict:
        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                resp = client.get(pdf_url)
                resp.raise_for_status()
                doc = fitz.open(stream=resp.content, filetype="pdf")
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
                return {"id": paper_id, "fulltext": text[:50000]}
        except Exception:
            return {"id": paper_id, "fulltext": ""}

    records = []
    con = sqlite3.connect(str(db_path), check_same_thread=False)
    t0 = time.time()
    n_workers = 8
    paper_ids = pdf["id"].tolist()
    insert_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = {pool.submit(extract_one, pid): pid for pid in paper_ids}
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            records.append(result)

            with insert_lock:
                con.execute("INSERT OR IGNORE INTO done (paper_id, extracted_at) VALUES (?, ?)",
                            (result["id"], time.strftime("%Y-%m-%dT%H:%M:%S")))
                con.commit()

            if i % 100 == 0 or i == total:
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed > 0 else 0
                remaining = (total - i) / rate if rate > 0 else 0
                print(f"  {i:,}/{total:,} — {rate:.1f} PDFs/sec, ~{remaining/60:.0f}m remaining")

                out_df = daft.from_pydict({k: [r[k] for r in records] for k in records[0]})
                out_df.write_parquet(str(out_path))
                records = []

    if records:
        out_df = daft.from_pydict({k: [r[k] for r in records] for k in records[0]})
        out_df.write_parquet(str(out_path))

    con.close()
    total_processed = len(pdf)
    elapsed = time.time() - t0
    print(f"  Done: {total_processed:,} papers in {elapsed/60:.1f}m ({total_processed/elapsed:.1f}/sec)")

    return {"processed": total_processed, "total": total, "path": str(out_path), "elapsed_s": elapsed}


def build_ml(df: daft.DataFrame, use_gpu: bool = False) -> dict:
    """Run topic clustering and build paper recommendations.
    Uses memmap-backed vectors from Task 1, MiniBatchKMeans for memory efficiency.
    """
    import faiss
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.feature_extraction.text import TfidfVectorizer

    embed_dir = DATA_DIR / "embeddings"
    vectors_path = embed_dir / "vectors.npy"
    ids_path = embed_dir / "ids.jsonl"
    embed_path = embed_dir / "papers.parquet"  # fallback

    if vectors_path.exists():
        print("  Loading vectors via memmap…")
        vectors = np.lib.format.open_memmap(str(vectors_path), mode="r")
        n = vectors.shape[0]
        paper_ids = []
        with open(str(ids_path)) as f:
            for line in f:
                paper_ids.append(json.loads(line)["id"])
        paper_ids = paper_ids[:n]
    elif embed_path.exists():
        print("  Loading embeddings from Parquet (fallback)…")
        emb_df = daft.read_parquet(str(embed_path))
        emb_pdf = emb_df.select(c("id"), c("embedding")).to_pandas()
        vectors = np.array(emb_pdf["embedding"].tolist(), dtype=np.float32)
        paper_ids = emb_pdf["id"].tolist()
        n = len(vectors)
    else:
        return {"error": "No embeddings found; run --embeddings first"}

    print(f"  {n:,} vectors loaded")

    n_clusters = min(10, max(2, n // 100))
    print(f"  Running MiniBatchKMeans with k={n_clusters}…")
    km = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, batch_size=10000, n_init=3)
    labels = km.fit_predict(vectors)

    fulltext_path = DATA_DIR / "fulltext" / "papers.parquet"
    if fulltext_path.exists() and n_clusters <= len(vectors):
        print("  Extracting topic keywords via TF-IDF…")
        text_df = daft.read_parquet(str(fulltext_path)).to_pandas()
        text_map = dict(zip(text_df["id"], text_df["fulltext"]))
        cluster_texts: dict[int, list[str]] = {}
        for pid, label in zip(paper_ids, labels):
            t = text_map.get(pid, "")
            if t:
                cluster_texts.setdefault(int(label), []).append(t[:2000])

        vectorizer = TfidfVectorizer(max_features=1000, stop_words="english",
                                      max_df=0.85, min_df=2)
        topic_keywords = {}
        for label, txts in cluster_texts.items():
            if len(txts) < 2:
                topic_keywords[label] = []
                continue
            try:
                tfidf = vectorizer.fit_transform(txts)
                avg = tfidf.mean(axis=0).A1
                top_idx = avg.argsort()[-10:][::-1]
                keywords = [vectorizer.get_feature_names_out()[i] for i in top_idx if avg[i] > 0]
                topic_keywords[label] = keywords
            except Exception:
                topic_keywords[label] = []
    else:
        topic_keywords = {i: [] for i in range(n_clusters)}

    # Build FAISS index from memmap in batches (no full RAM copy)
    # Build FAISS index from memmap in batches (no full RAM copy)
    cpu_index = faiss.IndexFlatIP(384)
    bs = 100_000
    for start in range(0, n, bs):
        end = min(start + bs, n)
        chunk = vectors[start:end].copy()
        faiss.normalize_L2(chunk)
        cpu_index.add(chunk)
    k = min(11, n)
    distances = np.zeros((n, k), dtype=np.float32)
    indices = np.zeros((n, k), dtype=np.int64)
    for start in range(0, n, bs):
        end = min(start + bs, n)
        chunk = vectors[start:end]
        d, i = cpu_index.search(chunk, k)
        distances[start:end] = d
        indices[start:end] = i

    recs = {}
    for i, pid in enumerate(paper_ids):
        similar = []
        for j in range(1, k):
            if indices[i][j] < n:
                similar.append({"id": paper_ids[int(indices[i][j])],
                                "score": float(distances[i][j])})
        recs[pid] = similar

    topics_out = []
    for label in range(n_clusters):
        member_ids = [paper_ids[i] for i in range(n) if labels[i] == label]
        topics_out.append({
            "id": int(label),
            "size": int((labels == label).sum()),
            "keywords": topic_keywords.get(label, []),
            "papers": member_ids[:20],
        })

    topics_out.sort(key=lambda x: -x["size"])
    print(f"  {len(topics_out)} topics")

    out = {"topics": topics_out, "total_papers": n}
    (DATA_DIR / "topics.json").write_text(json.dumps(out, separators=(",", ":")))

    recs_out = {"recommendations": recs, "total_papers": n}
    (DATA_DIR / "recommendations.json").write_text(json.dumps(recs_out, separators=(",", ":")))
    print(f"  recommendations for {len(recs):,} papers")

    return {"topics": len(topics_out), "recommendations": len(recs), "total_papers": n}


def build_embeddings(df: daft.DataFrame, use_gpu: bool = False) -> dict:
    """Generate and store embeddings for all papers (fulltext -> abstract fallback).
    Chunked processing: iterates Daft partitions, encodes with FP16 GPU,
    writes to .npy memmap, saves checkpoint for crash-resume.
    """
    import gc
    import json
    import torch

    from sentence_transformers import SentenceTransformer

    embed_dir = DATA_DIR / "embeddings"
    embed_dir.mkdir(parents=True, exist_ok=True)
    vectors_path = embed_dir / "vectors.npy"
    ids_path = embed_dir / "ids.jsonl"
    checkpoint_path = embed_dir / "checkpoint.json"

    fulltext_path = DATA_DIR / "fulltext" / "papers.parquet"
    if fulltext_path.exists():
        print("  Using fulltext as text source")
        texts = daft.read_parquet(str(fulltext_path)).select(c("id"), c("fulltext"))
    else:
        print("  Using abstracts as text source (no fulltext available)")
        texts = df.select(c("id"), c("abstract"))

    total = texts.count_rows()
    print(f"  Total papers: {total:,}")

    # Load model - FP16 on GPU to halve memory
    if use_gpu:
        model = SentenceTransformer("all-MiniLM-L6-v2").half().to("cuda")
    else:
        model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"  Model loaded on {model.device}")

    # Resume from checkpoint if exists
    done_ids = set()
    if checkpoint_path.exists():
        try:
            ckpt = json.loads(checkpoint_path.read_text())
            done_ids = set(ckpt.get("done_ids", []))
            print(f"  Resuming from checkpoint: {len(done_ids):,} already processed")
        except (json.JSONDecodeError, KeyError):
            print("  Checkpoint corrupt, starting fresh")

    batch_size = 32
    vectors_mmap = None
    processed = 0
    last_ckpt = 0
    t0 = time.time()

    for chunk_idx, partition in enumerate(texts.iter_partitions()):
        pdf = partition.to_pandas()
        pdf.columns = ["id", "text"]
        pdf["text"] = pdf["text"].fillna("").astype(str)

        # Filter out already-done IDs
        mask = ~pdf["id"].isin(done_ids)
        chunk = pdf[mask]
        if len(chunk) == 0:
            continue

        n = len(chunk)
        chunk_ids = chunk["id"].tolist()

        with torch.no_grad():
            chunk_vecs = model.encode(chunk["text"].tolist(), batch_size=batch_size, show_progress_bar=False)
        if hasattr(chunk_vecs, 'cpu'):
            chunk_vecs = chunk_vecs.cpu().float().numpy()
        chunk_vecs = chunk_vecs.astype(np.float32)

        # Free GPU memory for next chunk
        if use_gpu:
            torch.cuda.empty_cache()
        gc.collect()

        # Lazily create memmap with final total size on first write
        if vectors_mmap is None:
            vectors_mmap = np.lib.format.open_memmap(
                str(vectors_path), mode="w+", dtype=np.float32, shape=(total, 384)
            )

        vectors_mmap[processed:processed + n] = chunk_vecs
        vectors_mmap.flush()

        # Append IDs as JSONL (stream-friendly)
        with open(str(ids_path), "a") as f:
            for pid in chunk_ids:
                f.write(json.dumps({"id": pid}) + "\n")

        processed += n
        done_ids.update(chunk_ids)

        # Checkpoint every 100K new papers (avoid serializing huge set each chunk)
        if processed - last_ckpt >= 100_000:
            checkpoint_path.write_text(json.dumps({"done_ids": list(done_ids)}))
            last_ckpt = processed

        elapsed = time.time() - t0
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (total - processed) / rate if rate > 0 else 0
        print(f"  {processed:,}/{total:,} - {rate:.0f}/sec, ETA {eta:.0f}s")

    if vectors_mmap is not None:
        vectors_mmap.flush()

    elapsed = time.time() - t0
    print(f"  Done: {processed:,} embeddings in {elapsed:.1f}s ({processed/elapsed:.0f}/sec)")

    return {"total": processed, "vectors_path": str(vectors_path), "elapsed_s": elapsed}


def build_suggest_index(df, output_dir=None, author_ranking_path=None):
    import gzip
    import brotli
    import unicodedata
    import re

    if output_dir is None:
        output_dir = DATA_DIR / "search" / "suggest"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if author_ranking_path is None:
        author_ranking_path = DATA_DIR / "author_rankings.json"
    author_rankings = {}
    if author_ranking_path.exists():
        rankings = json.loads(author_ranking_path.read_text())
        for idx, entry in enumerate(rankings):
            if isinstance(entry, dict):
                author_rankings[entry.get("name", entry.get("author", ""))] = idx
            else:
                author_rankings[str(entry)] = idx

    shard_data = {}
    categories_set = set()

    # Iterate over Daft partitions instead of to_pydict() to avoid OOM
    for partition in df.iter_partitions():
        pdf = partition.to_pandas()
        for _, row in pdf.iterrows():
            raw = str(row.get("title", "") or "")
            normalized = unicodedata.normalize("NFD", raw)
            normalized = re.sub(r"[\u0300-\u036f]", "", normalized)
            first_char = normalized[0].lower() if normalized else "other"
            if not re.match(r"^[a-z]$", first_char):
                first_char = "other"

            if first_char not in shard_data:
                shard_data[first_char] = {"t": [], "a": [], "a_seen": set()}

            paper_id = str(row.get("id", ""))
            shard_data[first_char]["t"].append([raw, paper_id])

            authors_field = row.get("authors", "")
            if isinstance(authors_field, str):
                author_names = [a.strip() for a in authors_field.split(",") if a.strip()]
            elif isinstance(authors_field, list):
                author_names = authors_field
            else:
                author_names = []
            for author_name in author_names:
                if author_name not in shard_data[first_char]["a_seen"]:
                    shard_data[first_char]["a_seen"].add(author_name)
                    rank_idx = author_rankings.get(author_name, -1)
                    shard_data[first_char]["a"].append([author_name, rank_idx])

            cat_str = str(row.get("categories", "") or "")
            for cat in cat_str.split():
                if cat:
                    categories_set.add(cat)

    categories_list = sorted(categories_set)
    cat_data = {"c": [[c, ""] for c in categories_list]}

    import time
    now = time.strftime("%Y-%m-%d")

    shard_meta = {}
    total_papers = 0

    for letter in sorted(shard_data.keys()):
        sd = shard_data[letter]
        entry = {"t": sd["t"], "a": sd["a"]}
        payload = json.dumps(entry, separators=(",", ":"), ensure_ascii=False)

        with gzip.open(output_dir / f"{letter}.json.gz", "wt", encoding="utf-8") as f:
            f.write(payload)

        compressed = brotli.compress(payload.encode("utf-8"))
        (output_dir / f"{letter}.json.br").write_bytes(compressed)

        paper_count = len(sd["t"])
        author_count = len(sd["a"])
        shard_meta[letter] = {
            "papers": paper_count,
            "authors": author_count,
            "size_bytes": len(payload.encode("utf-8")),
        }
        total_papers += paper_count

    cat_payload = json.dumps(cat_data, separators=(",", ":"), ensure_ascii=False)
    with gzip.open(output_dir / "categories.json.gz", "wt", encoding="utf-8") as f:
        f.write(cat_payload)
    cat_br = brotli.compress(cat_payload.encode("utf-8"))
    (output_dir / "categories.json.br").write_bytes(cat_br)

    meta = {
        "version": 1,
        "updated": now,
        "total_papers": total_papers,
        "shards": shard_meta,
    }
    (output_dir / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))

    for letter in shard_data:
        shard_data[letter].pop("a_seen", None)

    return {
        "total_papers": total_papers,
        "shards": list(shard_data.keys()),
        "categories": len(categories_list),
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Build arXiv explorer static data")
    parser.add_argument("--incremental", action="store_true", default=True,
                        help="Only process new shards (default: True)")
    parser.add_argument("--no-incremental", action="store_false", dest="incremental",
                        help="Full rebuild from all shards")
    parser.add_argument("--sample", type=int, default=0,
                        help="Use a random sample of N papers (for testing)")
    parser.add_argument("--fulltext", action="store_true", default=False,
                        help="Run full-text extraction (PDF download + text extraction)")
    parser.add_argument("--ft-limit", type=int, default=0,
                        help="Limit full-text extraction to N papers (for testing)")
    parser.add_argument("--embeddings", action="store_true", default=False,
                        help="Generate paper embeddings")
    parser.add_argument("--ml", action="store_true", default=False,
                        help="Run ML pipeline (topic clustering + recommendations)")
    parser.add_argument("--gpu", action="store_true", default=False,
                        help="Enable GPU acceleration for embeddings and FAISS indexing (requires CUDA-capable GPU)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    os.environ["DAFT_RUNNER"] = "native"
    df = load_shards(incremental=args.incremental, sample=args.sample)

    if df is None:
        print("No data to process.")
        exit(0)

    print(f"Total papers: {df.count_rows():,}")
    print(f"Columns: {df.schema().column_names()}")

    print("Building category graph…")
    cat_graph = build_category_graph(df)
    (DATA_DIR / "category_graph.json").write_text(json.dumps(cat_graph, separators=(",", ":")))
    print(f"  {cat_graph['metadata']['total_nodes']} nodes, {cat_graph['metadata']['total_edges']} edges")

    print("Building author graph…")
    author_graph = build_author_graph(df)
    (DATA_DIR / "author_graph.json").write_text(json.dumps(author_graph, separators=(",", ":")))
    print(f"  {author_graph['metadata']['total_nodes']:,} nodes, {author_graph['metadata']['total_edges']:,} edges")

    print("Building author rankings…")
    author_rankings = build_author_rankings(df)
    (DATA_DIR / "author_rankings.json").write_text(json.dumps(author_rankings, separators=(",", ":")))
    print(f"  {len(author_rankings):,} ranked authors")

    print("Building FTS5 search database…")
    search_stats = build_search_db(df)
    print(f"  Indexed {search_stats['total_papers']:,} papers in search.db")

    print("Building category hierarchy…")
    hierarchy = build_category_hierarchy(df)
    (DATA_DIR / "category_hierarchy.json").write_text(json.dumps(hierarchy, separators=(",", ":")))
    print(f"  {len(hierarchy['domains'])} domains, {hierarchy['total_categories']} categories")

    print("Building category stats…")
    cat_stats = build_category_stats(df)
    (DATA_DIR / "category_stats.json").write_text(json.dumps(cat_stats, separators=(",", ":")))
    print(f"  {len(cat_stats['categories']):,} categories across {cat_stats['total_papers']:,} papers")

    print("Building publication timeseries…")
    ts = build_timeseries(df)
    (DATA_DIR / "timeseries.json").write_text(json.dumps(ts, separators=(",", ":")))
    print(f"  {len(ts):,} months of data")

    print("Building suggest shards…")
    suggest_stats = build_suggest_index(df)
    print(f"  {suggest_stats['total_papers']:,} papers in {len(suggest_stats['shards'])} shards")
    print(f"  {suggest_stats['categories']:,} categories")

    if args.fulltext:
        print("Building full-text index…")
        ft_stats = build_fulltext(df, limit=args.ft_limit)
        print(f"  Processed {ft_stats['processed']:,} papers")

    if args.embeddings:
        print("Generating paper embeddings…")
        emb_stats = build_embeddings(df, use_gpu=args.gpu)
        print(f"  {emb_stats['total']:,} embeddings in {emb_stats['elapsed_s']:.1f}s")

    if args.ml:
        print("Running ML pipeline…")
        ml_stats = build_ml(df, use_gpu=args.gpu)
        if "error" in ml_stats:
            print(f"  Error: {ml_stats['error']}")
        else:
            print(f"  {ml_stats['topics']} topics, {ml_stats['recommendations']:,} recommendations")
