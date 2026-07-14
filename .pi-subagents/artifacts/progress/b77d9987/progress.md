# Review progress: README.md single-machine run section

## Files read
- `README.md` (diff + context around single-machine section)
- `scripts/build_data.py` (full file, 750 lines)
- `pyproject.toml` (dependencies and metadata)

## Checklist
- [x] Verify flag existence against `build_data.py` argument parser
- [x] Check if `--gpu` flag is actually used anywhere in the pipeline
- [x] Validate `--sample` count estimation math
- [x] Confirm prerequisites listed in README exist in `pyproject.toml`
- [x] Check for missing dependencies (runtime imports not declared)
- [x] Check VRAM / output size claims for plausibility

## Findings summary
- **Blocker**: `--gpu` flag parsed but never used in code — README claim is false.
- **Error**: `--sample N` estimate wrong — `--sample 50000` loads ~360K papers, not ~50K.
- **Missing dep**: `httpx` (imported in `build_fulltext`) not in `pyproject.toml` → fulltext step will fail on fresh install.
- Everything else: correct.

## Status
Review complete. Writing final report.
