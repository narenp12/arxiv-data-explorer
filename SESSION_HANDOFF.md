# Pipeline Session Handoff — Jul 15, 2026

## Fixed Bug
`load_shards` in `scripts/build_data.py:73` had OOM: reading 417 shards one-by-one into list before `daft.concat`. Fixed with bulk glob `daft.read_parquet(paths)` for non-incremental mode. Incremental mode still uses per-shard approach (needed for date filtering).

## What Ran Successfully
Metadata phase complete (full 2,988,996 papers):
- `static/data/category_graph.json` — 169 nodes, 3,087 edges
- `static/data/author_graph.json` — 10,000 nodes, 200,000 edges
- `static/data/author_rankings.json` — 1,000 ranked authors
- `static/data/search.db` — 6.0 GB FTS5 index (all papers)
- `static/data/category_hierarchy.json` — 31 domains, 169 categories
- `static/data/category_stats.json` — 169 categories
- `static/data/timeseries.json` — 227 months
- `static/data/search/suggest/` — 27 shards, 176 categories (301 MB)

## What's Pending
| Phase | Status | Notes |
|-------|--------|-------|
| Fulltext | 1,211 / 2,988,996 done | arXiv throttles to ~5 PDFs/sec → ~6 days. Checkpoint at `static/data/fulltext/checkpoint.db`. |
| Embeddings | Not started | Falls back to abstracts if no fulltext. GPU (RTX 3050, 4GB VRAM). |
| ML (clustering + recs) | Not started | Needs embeddings. Fulltext needed for TF-IDF topic keywords only. |

## Next Session Decision Required
3 options:
- **A** — Rerun full pipeline. Redoes metadata (~5 min), resumes fulltext from checkpoint. Takes ~6 days.
- **B** — Skip fulltext. Run `--embeddings --ml --gpu` with abstract fallback. Clustering works. Topic keywords skipped. ~2-4 hrs.
- **C** — `--ft-limit 10000` for ~10K PDFs. Good topic keywords sample. Rest uses abstracts.

## Run Commands
```bash
# Option A: full pipeline
uv run python scripts/build_data.py --no-incremental --fulltext --embeddings --ml --gpu

# Option B: skip fulltext
uv run python scripts/build_data.py --no-incremental --embeddings --ml --gpu

# Option C: limited fulltext
uv run python scripts/build_data.py --no-incremental --fulltext --ft-limit 10000 --embeddings --ml --gpu

# Build site (any option)
npm run build
```

## GPU Specs
- NVIDIA GeForce RTX 3050 Laptop (4 GB VRAM)
- CUDA 13.2, Driver 595.80
- 27 GB RAM (17 GB free)
