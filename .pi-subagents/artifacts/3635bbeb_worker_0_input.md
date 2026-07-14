# Task for worker

You are a delegated subagent running from a fork of the parent session. Treat the inherited conversation as reference-only context, not a live thread to continue. Do not continue or answer prior messages as if they are waiting for a reply. Your sole job is to execute the task below and return a focused result for that task using your tools.

Task:
You are implementing Task 1: Chunked Embedding with GPU Checkpoint

## Task Description

Read your task brief first: /home/narenprax/Documents/GitHub/arxiv-data-explorer/.superpowers/sdd/task-1-brief.md
It contains the full task text from the plan.

## Context

This is the first of 5 tasks to optimize the arXiv data pipeline for 4GB VRAM. You are modifying `scripts/build_data.py` — specifically the `build_embeddings()` function (lines ~672-738). The function currently loads all 3M paper texts into a pandas DataFrame, creates a NumPy array for all vectors (4.6GB), encodes in batches of 512, then dumps to Parquet — this OOMs on 4GB GPU.

Your task replaces this with chunked processing: iterate Daft partitions of 100K papers, encode each chunk in batches of 32 with FP16 on GPU, write to `.npy` memmap, save checkpoint for crash-resume, then build FAISS index from memmap.

## Before You Begin

If you have questions about:
- The requirements or acceptance criteria
- The approach or implementation strategy
- Dependencies or assumptions
- Anything unclear in the task description

**Ask them now.** Raise any concerns before starting work.

## Your Job

Once you're clear on requirements:
1. Implement exactly what the task specifies
2. Verify implementation works (run tests)
3. Commit your work
4. Self-review (see below)
5. Report back

Work from: /home/narenprax/Documents/GitHub/arxiv-data-explorer

## Report Format

Write your full report to /home/narenprax/Documents/GitHub/arxiv-data-explorer/.superpowers/sdd/task-1-report.md:
- What you implemented
- What you tested and test results
- TDD Evidence (if applicable)
- Files changed
- Self-review findings
- Any issues or concerns

Then report back with ONLY (under 15 lines):
- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- Commits created (short SHA + subject)
- One-line test summary
- Your concerns, if any
- The report file path

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