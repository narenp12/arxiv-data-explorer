# Progress: GPU acceleration + README fix

## Status: Complete

## Changes applied

### scripts/build_data.py
- `build_embeddings`: added `use_gpu: bool = False` parameter
- `build_embeddings`: added `if use_gpu: model = model.to("cuda")` after model load
- `build_embeddings`: FAISS try-block wraps index creation: CPU index → optional GPU transfer → save via `faiss.index_gpu_to_cpu`
- `build_ml`: added `use_gpu: bool = False` parameter
- `build_ml`: FAISS IndexFlatIP creation wrapped with same GPU logic
- `parse_args`: updated `--gpu` help string to describe GPU acceleration
- Main block: passes `use_gpu=args.gpu` to both `build_embeddings` and `build_ml` calls

### README.md
- Updated `--sample N` description: "Process a random sample of N papers instead of the full dataset." → "Process a sample of approximately N papers (minimum 1 shard)."

## Validation
- `python3 -c "import ast; ast.parse(open('scripts/build_data.py').read()); print('OK')"` → OK
- git diff shows all 8 changes as expected

## Risks
- GPU code path untested (no GPU in CI). Falls back to CPU when `--gpu` not passed.
- `faiss.StandardGpuResources()` and `faiss.index_cpu_to_gpu` require `faiss-gpu` installed.
