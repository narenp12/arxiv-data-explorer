# Task for reviewer

[Read from: /home/narenprax/Documents/GitHub/arxiv-data-explorer/plan.md, /home/narenprax/Documents/GitHub/arxiv-data-explorer/progress.md]

Review the following diff for correctness, regressions, and test/validation gaps.

## Context

This is an arXiv data explorer pipeline (`scripts/build_data.py`). The changes optimize the pipeline to run on a 4GB VRAM laptop GPU for a 3M paper dataset. Four key changes:

1. **build_embeddings()** — replaced single-batch GPU encoding (OOM at batch_size=512) with chunked iteration over Daft partitions (100K per chunk), FP16 model (model.half()), batch_size=32, writes to .npy memmap instead of Parquet, saves checkpoint.json for crash-resume
2. **build_ml()** — loads vectors from memmap (.npy) instead of Parquet, uses MiniBatchKMeans instead of KMeans, FAISS built on CPU
3. **build_suggest_index()** — iterates Daft partitions instead of df.to_pydict() (was materializing 3M rows into RAM dict)
4. **build_author_graph()** — top_authors limit 50K→10K to reduce pair_counts memory

## Review focus

- Do the chunked encoding and checkpoint logic have edge-case bugs? (empty partitions, resume after crash, last chunk smaller than chunk_size)
- Are there any regression risks introduced by switching from .parquet to .npy for embeddings?
- Is the FAISS index built correctly from the memmap?
- Are there any unhandled exceptions or missing error paths?

## To review

Read the diff at /tmp/review-diff.txt
Read the full current file at scripts/build_data.py to understand context

Do NOT edit any files. Report findings only.

## Acceptance Contract
Acceptance level: attested
Completion is not accepted from prose alone. End with a structured acceptance report.

Criteria:
- criterion-1: Return concrete findings with file paths and severity when applicable

Required evidence: review-findings, residual-risks

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