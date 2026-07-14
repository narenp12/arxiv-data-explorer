## Review

### Findings by fix

**1. `--gpu` flag wiring — NOT applied**
- `--gpu` argument defined at build_data.py:850-851 but **never read** anywhere else. No `if args.gpu:` block exists.
- `build_embeddings()` creates `SentenceTransformer("all-MiniLM-L6-v2")` without `.to("cuda")` — stays on CPU.
- `build_ml()` uses `faiss.IndexFlatIP(384)` (CPU index) — no `faiss.StandardGpuResources` or `index_cpu_to_gpu` call.
- The flag help string claims "Enable Daft GPU UDFs" but no Daft GPU config is set either.

**2. `--sample N` min shard — CORRECTLY applied**
- `max(50, ...)` → `max(1, ...)` at build_data.py:93. Verified in source.

**3. `httpx` dependency — CORRECTLY applied**
- `"httpx>=0.25.0"` present in pyproject.toml dependencies. `import httpx` used in `build_fulltext()`.

**4. README system requirements — CORRECTLY applied**
- Single-Machine Run section includes GPU VRAM, RAM, Disk, CUDA, Node.js requirements.

**5. README `--sample` CLI description with min shard note — NOT applied**
- `--sample N` row in CLI flags table still reads: `Process ~N papers (reads ~N/7200 shards). Omit for all 2.99M.`
- No mention that minimum is 1 shard (was 50). Diff does not touch this line.

**6. README slop score 0/100 — PASS**
- All added README content is relevant, technical, proportionate. No fluff.

### Blocker
- `--gpu` flag is a no-op. Users passing `--gpu` get no CUDA acceleration. Misleading flag description. Needs wiring into `build_embeddings` (model `.to("cuda")`, `device="cuda"`) and `build_ml` (GPU FAISS index) — or removal if not intended.

### Note
- Fix 5 (README `--sample` min shard note) omitted from the diff.
- Conflict: user asked to write `progress.md` at `.pi-subagents/artifacts/progress/163ac79d/progress.md` but review-only rules forbid writing progress files. Mentioned only here.

---