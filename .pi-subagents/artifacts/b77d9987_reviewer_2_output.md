## Review

**Correct:**
- GPU guidance correctly warns VRAM limits (4–8 GB laptop GPUs), suggests `--sample N` to avoid OOM, and notes metadata-only doesn't need GPU.
- Python version pinned via `uv sync --python 3.12` — explicit and clear.
- Split workflow (metadata on MacBook, compute on GPU box) is well-documented earlier in README; single-machine section is a concise alternative.
- CUDA requirement stated: "NVIDIA GPU + CUDA required."

**Missing / Gaps:**

| Gap | Location | Risk |
|-----|----------|------|
| **Total disk space** | Estimated output lists shards/embeddings/search.db but no sum. A user following the single-machine flow may not realize they need ~10 GB free (200 MB + 4–6 GB + 3 GB = 7–9 GB plus OS overhead). | Performance – mid-run disk-full failure. |
| **RAM requirement** | No mention. Metadata-only on 3M papers easily needs 4+ GB RAM; full pipeline on large sample could exceed 8 GB. | Performance – OOM or swap thrashing. |
| **Node.js version** | No minimum specified. SvelteKit 5 / Tailwind 4 / TypeScript typically require Node 18+ or 20+. | Platform – cryptic build failures. |
| **CUDA version** | No specific version (e.g., CUDA 11.8+ / 12.x). `sentence-transformers` and FAISS GPU wheels may need matching CUDA runtime. | Platform – `--gpu` flag silently falls back to CPU or errors. |
| **`scripts/sync_data.sh` dependency** | Single-machine section doesn't reference it, but earlier "Two-Machine Workflow" assumes it exists. Sync script is not listed in repo yet (may be added later) — not a blocker, just a consistency note. | N/A |

**No security concerns** found in the diff (no credentials, no injection paths).

---

### Conflict Note
Task asks to update `progress.md` at `.pi-subagents/artifacts/progress/b77d9987/progress.md`. Subagent rules say review-only/no-edit wins over progress-writing when they conflict. I have **not written** that file. If the parent wants progress tracking, it must either override the no-edit rule or write the file itself.

---