# 4GB VRAM Optimization for arXiv Explorer Data Pipeline

## Problem
The data pipeline (`scripts/build_data.py`) processes 3M arXiv papers and OOMs on a laptop with 4GB VRAM when `--embeddings` and `--ml` flags are used. System RAM is 16GB.

## Approach
Chunked GPU embedding with CPU accumulation, checkpointing, and memory-efficient data structures.

## Changes

### 1. Chunked Embedding Generation (`build_embeddings`)
- Load Daft DataFrame without materializing all papers at once.
- Iterate over Daft partitions via `iter_partitions(rows_per_chunk=100_000)`.
- Process each chunk:
  - `model.half()` (FP16) to reduce VRAM.
  - `batch_size=32`.
  - Encode texts.
  - Detach from GPU, `torch.cuda.empty_cache()`.
  - Append vectors to a `.npy` memory-mapped file on disk.
  - Save `checkpoint.json` recording processed paper IDs.
- Resume from checkpoint if interrupted.

### 2. Memory-Mapped Vector Loading (`build_ml`)
- Embeddings stored as `.npy` file instead of Parquet (Parquet requires full deserialization into RAM).
- Load vectors via `np.memmap` to avoid loading 4.6GB into RAM.
- Use `MiniBatchKMeans` instead of standard `KMeans`.
- Build FAISS index on CPU (already supported via `use_gpu=False`).

### 3. Partition-Based Suggest Index (`build_suggest_index`)
- Replace `df.to_pydict()` (materializes entire dataset) with `df.iter_partitions(200_000)`.
- Process one partition at a time, accumulating into shard structures.
- Reduces peak RAM usage from ~6GB to ~200MB.

### 4. Author Graph Memory Limit (`build_author_graph`)
- Lower `top_authors` limit from 50,000 to 10,000.
- Prevents `pair_counts` dictionary from growing to 10M+ keys.

### 5. CLI Flags
- Existing `--gpu` flag correctly enables chunked GPU encoding.
- No new flags needed; pipeline detects interruption and resumes from checkpoint.

## Trade-offs
- GPU embedding slower (~3-4 hours vs 1 hour with 24GB VRAM).
- Author graph limited to top 10K authors (was 50K, still covers most edges).
- Suggest index built partitionally (same output, less peak memory).
- No new external dependencies.
