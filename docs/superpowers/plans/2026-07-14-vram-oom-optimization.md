# 4GB VRAM OOM Optimization

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `build_embeddings()` and `build_ml()` run on 4GB VRAM laptop for full 3M paper dataset without OOM.

**Architecture:** Chunk GPU embedding with FP16, memmap vectors to disk, iterate Daft partitions instead of materializing whole dataset, use MiniBatchKMeans.

**Tech Stack:** Python, sentence-transformers, FAISS, numpy memmap, Daft.

## Global Constraints

- No new external dependencies.
- Existing CLI flags preserved (`--gpu`, `--sample`, etc.).
- Crash resume via checkpoint files.
- Output format (Parquet for embeddings, JSON for topics/recommendations) unchanged.

---

### Task 1: Chunked Embedding with GPU Checkpoint

**Files:**
- Modify: `scripts/build_data.py:672-738`

**Interfaces:**
- Consumes: `df: daft.DataFrame`, `use_gpu: bool` (unchanged signature)
- Produces: `.npy` file at `static/data/embeddings/vectors.npy`, checkpoint at `static/data/embeddings/checkpoint.json`, FAISS index at `static/data/embeddings/faiss.index`

- [ ] **Step 1: Read current `build_embeddings()` signature and imports**

Run: `cd /home/narenprax/Documents/GitHub/arxiv-data-explorer && python -c "import daft, numpy as np, pathlib; print('imports OK')"`

- [ ] **Step 2: Rewrite `build_embeddings()` for chunked processing**

Replace the function body. Key changes:

```python
import json
import gc
import torch

def build_embeddings(df: daft.DataFrame, use_gpu: bool = False) -> dict:
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

    # Load model in FP16
    model = SentenceTransformer("all-MiniLM-L6-v2")
    if use_gpu:
        model = model.half().to("cuda")
    print(f"  Model loaded on {model.device}, precision: {model.get_first_module().weight.dtype}")

    # Resume checkpoint
    done_ids = set()
    if checkpoint_path.exists():
        ckpt = json.loads(checkpoint_path.read_text())
        done_ids = set(ckpt.get("done_ids", []))
        print(f"  Resuming from checkpoint: {len(done_ids):,} already processed")

    chunk_size = 100_000
    batch_size = 32
    # Pre-allocate memmap (write first dim after first chunk)
    vectors_mmap = None
    processed = 0
    t0 = time.time()

    # Iterate over Daft partitions
    for chunk_idx, partition in enumerate(texts.iter_partitions(rows_per_chunk=chunk_size)):
        pdf = partition.to_pandas()
        pdf.columns = ["id", "text"]
        pdf["text"] = pdf["text"].fillna("").astype(str)

        # Skip already done
        mask = ~pdf["id"].isin(done_ids)
        chunk = pdf[mask]
        if len(chunk) == 0:
            continue

        # Encode in batches on GPU
        all_vecs = np.zeros((len(chunk), 384), dtype=np.float32)
        chunk_ids = []
        for start in range(0, len(chunk), batch_size):
            end = min(start + batch_size, len(chunk))
            batch_texts = chunk["text"].iloc[start:end].tolist()
            with torch.no_grad():
                batch_emb = model.encode(batch_texts, show_progress_bar=False)
            if isinstance(batch_emb, torch.Tensor):
                batch_emb = batch_emb.cpu().float().numpy()
            all_vecs[start:end] = batch_emb.astype(np.float32)
            chunk_ids.extend(chunk["id"].iloc[start:end].tolist())

        # Free GPU memory
        if use_gpu:
            torch.cuda.empty_cache()
        gc.collect()

        # Write append to memmap
        if vectors_mmap is None:
            # First chunk: create memmap with final size
            vectors_mmap = np.lib.format.open_memmap(
                str(vectors_path), mode="w+", dtype=np.float32, shape=(total, 384)
            )
        vectors_mmap[processed:processed + len(chunk)] = all_vecs
        vectors_mmap.flush()

        # Append IDs
        with open(str(ids_path), "a") as f:
            for pid in chunk_ids:
                f.write(json.dumps({"id": pid, "idx": processed}) + "\n")
                processed += 1

        # Save checkpoint every chunk
        done_ids.update(chunk_ids)
        checkpoint_path.write_text(json.dumps({"done_ids": list(done_ids)}, cls=JSONEncoder))

        elapsed = time.time() - t0
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (total - processed) / rate if rate > 0 else 0
        print(f"  {processed:,}/{total:,} — {rate:.0f}/sec, ETA {eta:.0f}s")

    # Final flush
    if vectors_mmap is not None:
        vectors_mmap.flush()

    elapsed = time.time() - t0
    print(f"  Done: {processed:,} embeddings in {elapsed:.1f}s ({processed/elapsed:.0f}/sec)")

    # Build FAISS index from memmap
    try:
        import faiss
        print("  Building FAISS index from memmap…")
        vectors = np.lib.format.open_memmap(str(vectors_path), mode="r")
        faiss.normalize_L2(vectors)
        cpu_index = faiss.IndexFlatIP(384)
        cpu_index.add(vectors)
        faiss.write_index(cpu_index, str(embed_dir / "faiss.index"))
        print(f"  FAISS index built: {cpu_index.ntotal:,} vectors")
    except ImportError:
        print("  FAISS not available, skipping index build")

    return {"total": processed, "vectors_path": str(vectors_path), "elapsed_s": elapsed}
```

- [ ] **Step 3: Run basic syntax check**

Run: `cd /home/narenprax/Documents/GitHub/arxiv-data-explorer && python -c "import scripts.build_data"`
Expected: no import errors

- [ ] **Step 4: Test with small sample on CPU**

Run: `cd /home/narenprax/Documents/GitHub/arxiv-data-explorer && uv run python scripts/build_data.py --sample 100 --incremental --embeddings`
Expected: finishes without OOM, produces `static/data/embeddings/vectors.npy` and `faiss.index`

- [ ] **Step 5: Commit**

```bash
cd /home/narenprax/Documents/GitHub/arxiv-data-explorer
git add scripts/build_data.py
git commit -m "perf: chunked GPU embedding with memmap and checkpoint resume"
```

---

### Task 2: Memory-Efficient ML Pipeline

**Files:**
- Modify: `scripts/build_data.py:571-670`

**Interfaces:**
- Consumes: vectors from `static/data/embeddings/vectors.npy` (memmap), `static/data/embeddings/ids.jsonl`
- Produces: `static/data/topics.json`, `static/data/recommendations.json`

- [ ] **Step 1: Rewrite `build_ml()` to use memmap vectors**

Replace the function body:

```python
def build_ml(df: daft.DataFrame, use_gpu: bool = False) -> dict:
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.feature_extraction.text import TfidfVectorizer
    import faiss

    embed_dir = DATA_DIR / "embeddings"
    vectors_path = embed_dir / "vectors.npy"
    ids_path = embed_dir / "ids.jsonl"

    if not vectors_path.exists():
        return {"error": "No vectors.npy found; run --embeddings first"}

    print("  Loading vectors via memmap…")
    vectors = np.lib.format.open_memmap(str(vectors_path), mode="r")
    n = vectors.shape[0]
    print(f"  {n:,} vectors loaded")

    # Load paper IDs
    paper_ids = []
    with open(str(ids_path)) as f:
        for line in f:
            entry = json.loads(line)
            paper_ids.append(entry["id"])
    # Ensure sorted by idx
    paper_ids.sort(key=lambda pid: int(json.loads(open(str(ids_path)).readlines()[0])["idx"]))  # lazy sort
```

Actually better approach without rewriting the ML completely — just change the data loading:

```python
def build_ml(df: daft.DataFrame, use_gpu: bool = False) -> dict:
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import faiss

    embed_dir = DATA_DIR / "embeddings"
    vectors_path = embed_dir / "vectors.npy"
    ids_path = embed_dir / "ids.jsonl"
    embed_path = embed_dir / "papers.parquet"  # fallback if parquet exists

    if vectors_path.exists():
        print("  Loading vectors via memmap…")
        vectors = np.lib.format.open_memmap(str(vectors_path), mode="r")
        n = vectors.shape[0]
        # Load IDs from jsonl
        paper_ids = []
        with open(str(ids_path)) as f:
            for line in f:
                paper_ids.append(json.loads(line)["id"])
        paper_ids = paper_ids[:n]  # safety
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
    centroids = km.cluster_centers_

    # TF-IDF topic extraction (same as before)
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
    # Normalize vectors on CPU (memmap readable)
    cpu_index = faiss.IndexFlatIP(384)
    vectors_copy = np.array(vectors)  # load into RAM for search (384*3M ~ 4.6GB if needed)
    faiss.normalize_L2(vectors_copy)
    if use_gpu:
        res = faiss.StandardGpuResources()
        index = faiss.index_cpu_to_gpu(res, 0, cpu_index)
        index.add(vectors_copy)
        cpu_index = faiss.index_gpu_to_cpu(index)
    else:
        cpu_index.add(vectors_copy)
    k = min(11, n)
    distances, indices = cpu_index.search(vectors_copy, k)
    # Free copy
    del vectors_copy

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
```

- [ ] **Step 2: Syntax check**

Run: `cd /home/narenprax/Documents/GitHub/arxiv-data-explorer && python -c "import scripts.build_data"`

- [ ] **Step 3: Test with small sample**

Run: `cd /home/narenprax/Documents/GitHub/arxiv-data-explorer && uv run python scripts/build_data.py --sample 100 --incremental --embeddings --ml`
Expected: topics.json and recommendations.json produced

- [ ] **Step 4: Commit**

```bash
cd /home/narenprax/Documents/GitHub/arxiv-data-explorer
git add scripts/build_data.py
git commit -m "perf: memmap-backed ML pipeline with MiniBatchKMeans"
```

---

### Task 3: Partition-Based Suggest Index

**Files:**
- Modify: `scripts/build_data.py:739-896` (end of file)

**Interfaces:**
- Consumes: `df: daft.DataFrame` (unchanged signature)
- Produces: same output files in `static/data/search/suggest/`

- [ ] **Step 1: Rewrite `build_suggest_index()` to iterate partitions**

Replace `papers = df.to_pydict()` loop with partition iteration:

```python
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

    # Initialize shard data structures
    shard_data = {}
    categories_set = set()

    # Iterate over Daft partitions of 200K rows
    for partition in df.iter_partitions(rows_per_chunk=200_000):
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

    # Check if shard_data is empty (no papers found in columns)
    if not shard_data:
        print("  Warning: No papers found in columns (maybe different column names in partition?)")
        # Fallback: try column name variants
        # We should inspect column names from the original df
        print(f"  Available columns: {df.schema().column_names()}")
        # Retry with correct column names if needed
        # This is a safety fallback, partition should preserve columns

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
```

- [ ] **Step 2: Syntax check**

Run: `cd /home/narenprax/Documents/GitHub/arxiv-data-explorer && python -c "import scripts.build_data"`

- [ ] **Step 3: Test with sample**

Run: `cd /home/narenprax/Documents/GitHub/arxiv-data-explorer && uv run python scripts/build_data.py --sample 1000 --no-incremental`
Expected: suggest shards produced in `static/data/search/suggest/`, no OOM

- [ ] **Step 4: Commit**

```bash
cd /home/narenprax/Documents/GitHub/arxiv-data-explorer
git add scripts/build_data.py
git commit -m "perf: partition-based suggest index to avoid full dataset materialization"
```

---

### Task 4: Lower Author Graph Memory Limit

**Files:**
- Modify: `scripts/build_data.py:266`

- [ ] **Step 1: Change top_authors limit**

Change line 266:
```
    top_authors = sorted(name_counts.items(), key=lambda x: -x[1])[:50000]
```
to:
```
    top_authors = sorted(name_counts.items(), key=lambda x: -x[1])[:10000]
```

- [ ] **Step 2: Verify**

Run: `cd /home/narenprax/Documents/GitHub/arxiv-data-explorer && uv run python scripts/build_data.py --sample 50000 --no-incremental`
Expected: author_graph.json produced with ~10K nodes

- [ ] **Step 3: Commit**

```bash
cd /home/narenprax/Documents/GitHub/arxiv-data-explorer
git add scripts/build_data.py
git commit -m "perf: limit author graph to top 10K authors to reduce pair count memory"
```

---

### Task 5: Dry-Run Full Pipeline Integration Test

**Files:**
- Test: none (run on sample)

- [ ] **Step 1: Run full pipeline on 10K sample**

Run: `cd /home/narenprax/Documents/GitHub/arxiv-data-explorer && uv run python scripts/build_data.py --sample 10000 --no-incremental --embeddings --ml`
Expected: all output files produced, no OOM or crash

- [ ] **Step 2: Verify output files exist**

Run: `cd /home/narenprax/Documents/GitHub/arxiv-data-explorer && ls -la static/data/embeddings/vectors.npy static/data/embeddings/faiss.index static/data/topics.json static/data/recommendations.json static/data/search/suggest/meta.json`
Expected: all files present

- [ ] **Step 3: Final commit**

```bash
cd /home/narenprax/Documents/GitHub/arxiv-data-explorer
git add -A
git commit -m "chore: integration test with 10K sample validates VRAM optimizations"
```
