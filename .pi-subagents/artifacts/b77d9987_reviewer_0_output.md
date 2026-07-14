## Review: README.md single-machine run section

### What's correct
- `--no-incremental`, `--fulltext`, `--embeddings`, `--ml` flags all exist in argparser with matching semantics.
- `--sample N` flag exists and behaves as described (subset of papers).
- `uv sync --python 3.12` / `npm install` / `npm run build` commands are correct.
- VRAM range (4-8 GB) and output size estimates (embeddings 4-6 GB, search.db ~3 GB) are order-of-magnitude plausible.

### What's wrong

**1. `--gpu` flag is dead code (misleading claim)**

README says `--gpu` enables GPU acceleration and "NVIDIA GPU + CUDA required for `--gpu` flag".  
But `build_data.py` line 751:  
```python
parser.add_argument("--gpu", action="store_true", default=False, ...)
```
`args.gpu` is **never read** anywhere else in the file. The flag does nothing. Users who install CUDA expecting acceleration will be confused.

**2. `--sample` count is off by ~7x**

README: "`--sample 50000` runs ~50K papers".  
Code (line 60-62):
```python
papers_per_shard = 7200
n_shards = max(50, sample // papers_per_shard)  # for 50000: max(50, 6) = 50
shard_files = shard_files[:n_shards]             # 50 shards × 7200 = 360,000 papers
```
Result: `--sample 50000` loads **~360K papers**, not ~50K. The formula caps at 50 shards regardless of sample size when sample < 360K.

**3. Missing runtime dependency `httpx`**

`build_fulltext()` (line 499) does `import httpx` at runtime.  
`httpx` is **not listed** in `pyproject.toml` dependencies. Fresh `uv sync` will not install it → fulltext step crashes.

### Observational notes (not errors)
- `requires-python = ">=3.11"` in `pyproject.toml` — README specifying `3.12` is more restrictive but still valid.
- "Metadata-only takes ~10 min" is a rough benchmark, plausible but unverifiable.

---