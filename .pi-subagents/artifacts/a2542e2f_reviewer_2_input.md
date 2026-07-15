# Task for reviewer

[Read from: /home/narenprax/Documents/GitHub/arxiv-data-explorer/plan.md, /home/narenprax/Documents/GitHub/arxiv-data-explorer/progress.md]

Review the following diff for performance and memory safety.

## Context

This is an arXiv data explorer pipeline (`scripts/build_data.py`). The changes optimize the pipeline to run on a 4GB VRAM laptop GPU for a 3M paper dataset. Four key changes:

1. **build_embeddings()** — replaced single-batch GPU encoding with chunked iteration over Daft partitions, FP16 model, batch_size=32, writes to .npy memmap, saves checkpoint.json for crash-resume
2. **build_ml()** — loads vectors from memmap, uses MiniBatchKMeans instead of KMeans
3. **build_suggest_index()** — iterates Daft partitions instead of df.to_pydict()
4. **build_author_graph()** — top_authors limit 50K→10K

## Review focus

- Does the chunking strategy actually limit GPU VRAM to <4GB? (FP16 model ~400MB, batch_size=32 == 32*384*4 bytes ~50KB per batch, chunk 100K papers)
- Is the .npy memmap correctly sized and freed between chunks?
- Could there be GPU memory leaks? (torch.cuda.empty_cache() called correctly?)
- Is the checkpoint crash-resume mechanism robust for multi-hour runs? (atomic writes, partial checkpoint recovery)
- Does the partition-based suggest index actually reduce peak RAM vs to_pydict()?
- Any performance regressions from the changes to build_ml() (MiniBatchKMeans vs KMeans, vectors_copy allocation)?

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