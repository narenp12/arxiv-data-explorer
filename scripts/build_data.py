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
    cache_path = snapshot_download(REMOTE_REPO, repo_type="dataset")
    shard_files = sorted(Path(cache_path).rglob("*.parquet"))
    print(f"Found {len(shard_files)} shard files")

    if sample:
        papers_per_shard = 7200
        n_shards = max(50, sample // papers_per_shard)
        shard_files = shard_files[:n_shards]
        print(f"Using {len(shard_files)} shards for sample of ~{sample:,}")

    dfs = []
    for i, f in enumerate(shard_files):
        if i % 100 == 0:
            print(f"  Reading shard {i}/{len(shard_files)}…")
        df = daft.read_parquet(str(f))

        if max_date is not None and "update_date" in df.schema().column_names():
            df = df.where(c("update_date") > max_date)

        dfs.append(df)

    if not dfs:
        print("No new shards to process.")
        return existing

    full = daft.concat(dfs)
    print(f"Concatenated {len(dfs)} shards")

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

    top_authors = sorted(name_counts.items(), key=lambda x: -x[1])[:50000]
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
            {"id": cat, "count": len(papers)}
            for cat, papers in cat_papers.items()
            if (cat.split(".")[0] if "." in cat else cat) == dom
        ]
        domain_counts[dom]["children"].sort(key=lambda x: -x["count"])

    nodes = sorted(domain_counts.values(), key=lambda x: -x["count"])

    return {
        "nodes": nodes,
        "total_categories": len(cat_papers),
        "total_domains": len(nodes),
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
        db_path.unlink()

    fields = ["id", "title", "abstract", "authors", "categories", "update_date"]
    pdf = df.select(*[c(f) for f in fields]).to_pandas()

    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("PRAGMA cache_size=-80000")

    con.execute("""CREATE VIRTUAL TABLE papers_fts USING fts5(
        id, title, abstract, authors, categories,
        tokenize='porter unicode61',
        content=''
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


def build_ml(df: daft.DataFrame) -> dict:
    """Run topic clustering and build paper recommendations."""
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import faiss

    embed_dir = DATA_DIR / "embeddings"
    embed_path = embed_dir / "papers.parquet"
    if not embed_path.exists():
        return {"error": "No embeddings found; run --embeddings first"}

    print("  Loading embeddings…")
    emb_df = daft.read_parquet(str(embed_path))
    emb_pdf = emb_df.select(c("id"), c("embedding")).to_pandas()
    vectors = np.array(emb_pdf["embedding"].tolist(), dtype=np.float32)
    paper_ids = emb_pdf["id"].tolist()
    n = len(vectors)
    print(f"  {n:,} vectors loaded")

    n_clusters = min(10, max(2, n // 100))
    print(f"  Running KMeans with k={n_clusters}…")
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    labels = km.fit_predict(vectors)
    centroids = km.cluster_centers_

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

    print("  Building recommendations via FAISS…")
    index = faiss.IndexFlatIP(384)
    faiss.normalize_L2(vectors)
    index.add(vectors)
    k = min(11, n)
    distances, indices = index.search(vectors, k)

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


def build_embeddings(df: daft.DataFrame) -> dict:
    """Generate and store embeddings for all papers (fulltext → abstract fallback)."""
    from sentence_transformers import SentenceTransformer

    embed_dir = DATA_DIR / "embeddings"
    embed_dir.mkdir(parents=True, exist_ok=True)
    out_path = embed_dir / "papers.parquet"

    fulltext_path = DATA_DIR / "fulltext" / "papers.parquet"
    if fulltext_path.exists():
        print("  Using fulltext as text source")
        texts = daft.read_parquet(str(fulltext_path)).select(c("id"), c("fulltext"))
    else:
        print("  Using abstracts as text source (no fulltext available)")
        texts = df.select(c("id"), c("abstract"))

    pdf = texts.to_pandas()
    pdf.columns = ["id", "text"]
    pdf["text"] = pdf["text"].fillna("").astype(str)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"  Model loaded on {model.device}")

    batch_size = 512
    total = len(pdf)
    all_embeddings = np.zeros((total, 384), dtype=np.float32)

    t0 = time.time()
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_texts = pdf["text"].iloc[start:end].tolist()
        batch_emb = model.encode(batch_texts, show_progress_bar=False)
        all_embeddings[start:end] = batch_emb.astype(np.float32)

        if (start + batch_size) % 5000 == 0 or end == total:
            elapsed = time.time() - t0
            rate = end / elapsed if elapsed > 0 else 0
            print(f"  {end:,}/{total:,} — {rate:.0f} papers/sec")

    out_df = daft.from_pydict({
        "id": pdf["id"].tolist(),
        "embedding": [v.tolist() for v in all_embeddings],
    })
    out_df.write_parquet(str(out_path))
    elapsed = time.time() - t0
    print(f"  Done: {total:,} embeddings in {elapsed:.1f}s ({total/elapsed:.0f}/sec)")

    try:
        import faiss
        index = faiss.IndexFlatIP(384)
        index.add(all_embeddings)
        faiss.write_index(index, str(embed_dir / "faiss.index"))
        print(f"  FAISS index built: {index.ntotal:,} vectors")
    except ImportError:
        print("  FAISS not available, skipping index build")

    return {"total": total, "path": str(out_path), "elapsed_s": elapsed}


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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
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
    print(f"  {hierarchy['total_domains']} domains, {hierarchy['total_categories']} categories")

    print("Building category stats…")
    cat_stats = build_category_stats(df)
    (DATA_DIR / "category_stats.json").write_text(json.dumps(cat_stats, separators=(",", ":")))
    print(f"  {len(cat_stats['categories']):,} categories across {cat_stats['total_papers']:,} papers")

    print("Building publication timeseries…")
    ts = build_timeseries(df)
    (DATA_DIR / "timeseries.json").write_text(json.dumps(ts, separators=(",", ":")))
    print(f"  {len(ts):,} months of data")

    if args.fulltext:
        print("Building full-text index…")
        ft_stats = build_fulltext(df, limit=args.ft_limit)
        print(f"  Processed {ft_stats['processed']:,} papers")

    if args.embeddings:
        print("Generating paper embeddings…")
        emb_stats = build_embeddings(df)
        print(f"  {emb_stats['total']:,} embeddings in {emb_stats['elapsed_s']:.1f}s")

    if args.ml:
        print("Running ML pipeline…")
        ml_stats = build_ml(df)
        if "error" in ml_stats:
            print(f"  Error: {ml_stats['error']}")
        else:
            print(f"  {ml_stats['topics']} topics, {ml_stats['recommendations']:,} recommendations")
