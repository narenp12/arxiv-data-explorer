# FAISS Memmap RAM Fix — Design Spec

## Problem

`build_ml()` copies the full 4.6GB memmap into system RAM via `np.array(vectors)` before building or searching the FAISS index. This defeats the purpose of memmap-backed vectors and causes OOM on 16GB system.

## Solution: Chunked FAISS from Memmap

Always rebuild FAISS index from memmap in batches (option C per brainstorming). Never materialize the full vector array.

### Build phase
- Create `faiss.IndexFlatIP(384)`
- Iterate memmap in batches of 100K rows
- Each batch: `np.array(vectors[start:end], dtype=np.float32, copy=False)` — lightweight view, not a copy
- `faiss.normalize_L2(chunk)` then `cpu_index.add(chunk)`
- Peak RAM per batch: ~150MB (100K × 384 × 4 bytes)

### Search phase
- Pre-allocate `distances(n, k)` and `indices(n, k)` as float32/int64 zeros
- Same batch loop: query `cpu_index.search(chunk, k)`, store to pre-allocated arrays
- Total RAM: ~8MB for k=11 × 3M + batch buffer ~150MB

### Build `faiss.index` for reuse?
No — option C (always rebuild from memmap). Keeps code simple, avoids stale-index bugs. Rebuild takes <30s for 3M vectors.

## Cleanup
- Remove unused `chunk_size = 100_000` from `build_embeddings()`

## GPU Validation
- Run `uv run python scripts/build_data.py --sample 100 --no-incremental --embeddings --gpu`
- Verify FP16 model loads, encodes without OOM, FAISS builds and searches correctly
- Check `build_ml` output (topics.json, recs.json) for correct k=11 recommendations

## Files Changed
- `scripts/build_data.py` — `build_ml()` FAISS section, `build_embeddings()` dead var

## Acceptance Criteria
1. `build_ml()` peak RAM <500MB (vs 4.6GB before)
2. `build_embeddings()` no unused variables
3. `--gpu --sample 100` pipeline completes without error
4. FAISS search returns k=11 results per paper
5. `topics.json` and `recs.json` output files correct
