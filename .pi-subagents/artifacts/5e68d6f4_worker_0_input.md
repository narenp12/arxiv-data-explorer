# Task for worker

[Read from: /home/narenprax/Documents/GitHub/arxiv-data-explorer/context.md, /home/narenprax/Documents/GitHub/arxiv-data-explorer/plan.md]

In /home/narenprax/Documents/GitHub/arxiv-data-explorer, apply these 4 fixes to scripts/build_data.py:

1. Add `use_gpu: bool = False` parameter to `build_embeddings` function signature
2. Inside `build_embeddings`, after `model = SentenceTransformer("all-MiniLM-L6-v2")`, add `if use_gpu: model = model.to("cuda")`
3. In the FAISS try-block inside `build_embeddings`, wrap the index creation: if GPU, build CPU index then use `faiss.StandardGpuResources()` + `faiss.index_cpu_to_gpu(res, 0, cpu_index)`, save via `faiss.index_gpu_to_cpu(index)`
4. Add `use_gpu: bool = False` parameter to `build_ml` function signature
5. In `build_ml`, wrap the FAISS IndexFlatIP creation with GPU logic same as above
6. In `parse_args`, update `--gpu` help string to describe GPU acceleration accurately
7. In the main block, pass `use_gpu=args.gpu` to `build_embeddings(df, ...)` and `build_ml(df, ...)` calls
8. In README.md, update `--sample N` CLI flag description to mention min 1 shard

Read the current file, apply changes, verify with `python3 -c"import ast; ast.parse(open('scripts/build_data.py').read()); print('OK')"` and git diff. Do NOT run the pipeline.

---
Update progress at: /home/narenprax/Documents/GitHub/arxiv-data-explorer/.pi-subagents/artifacts/progress/5e68d6f4/progress.md

## Acceptance Contract
Acceptance level: checked
Completion is not accepted from prose alone. End with a structured acceptance report.

Criteria:
- criterion-1: Implement the requested change without widening scope

Required evidence: changed-files, tests-added, commands-run, residual-risks, no-staged-files

Finish with a fenced JSON block tagged `acceptance-report` in this shape:
Use empty arrays when no items apply; array fields contain strings unless object entries are shown.
```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "specific proof"
    }
  ],
  "changedFiles": [
    "src/file.ts"
  ],
  "testsAddedOrUpdated": [
    "test/file.test.ts"
  ],
  "commandsRun": [
    {
      "command": "command",
      "result": "passed",
      "summary": "short result"
    }
  ],
  "validationOutput": [
    "validation output or concise summary"
  ],
  "residualRisks": [
    "none"
  ],
  "noStagedFiles": true,
  "diffSummary": "short description of the diff",
  "reviewFindings": [
    "blocker: file.ts:12 - issue found, or no blockers"
  ],
  "manualNotes": "anything else the parent should know"
}
```