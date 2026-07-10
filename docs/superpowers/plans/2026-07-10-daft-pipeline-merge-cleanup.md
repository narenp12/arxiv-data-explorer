# Daft Pipeline Merge & Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the 8-commit `daft-pipeline` branch into `main`, delete superseded scripts, and clean up `.gitignore` for data file tracking.

**Architecture:** Git merge of the feature branch, then a cleanup commit that removes old scripts and updates `.gitignore` to track only `category_hierarchy.json` while ignoring all other regeneratable JSON outputs.

**Tech Stack:** git, Python

## Global Constraints

- Preserve all existing frontend components and data paths on `main`
- Old scripts to delete: `build_trends.py`, `build_author_shards.mjs`, `postbuild.mjs`, `requirements.txt`
- Keep `scripts/utils.py`
- Track only `static/data/category_hierarchy.json` in git; ignore all other regeneratable JSONs
- Preserve old data: `static/data/authors/shard-*.json`, `static/data/timeseries/*.json`, `static/data/category_dynamics.json`, `static/data/causal_edges.json`, `static/data/network_stats.json`, `data-src/author_graph.json`
- README.md already updated on `daft-pipeline` branch

---
### Task 1: Merge daft-pipeline into main

**Files:**
- Modify: `pyproject.toml` — keep pipeline branch version (Daft deps)
- Modify: `.gitignore` — keep pipeline branch version (already has *.db, *.parquet, etc.)
- Modify: `static/data/category_graph.json`, `category_hierarchy.json`, `author_rankings.json` — take pipeline branch version

- [ ] **Step 1: Checkout main and verify state**

Run:
```bash
git checkout main
git status  # should be clean
git log --oneline -3
```
Expected: at commit `683b6ab`, no uncommitted changes.

- [ ] **Step 2: Merge daft-pipeline**

Run:
```bash
git merge daft-pipeline
```

Expected: merge succeeds. There will be conflicts on `static/data/category_graph.json`, `static/data/category_hierarchy.json`, `static/data/author_rankings.json` (same file paths on both branches). Resolve each by taking the pipeline branch version (theirs):
```bash
git checkout --theirs static/data/category_graph.json
git checkout --theirs static/data/category_hierarchy.json
git checkout --theirs static/data/author_rankings.json
git add static/data/category_graph.json static/data/category_hierarchy.json static/data/author_rankings.json
git merge --continue
git commit  # accept default merge message
```

- [ ] **Step 3: Verify merge**

Run:
```bash
git log --oneline -5
```
Expected: merge commit at HEAD. All 8 pipeline commits + old main commits in history. Files:
```bash
ls scripts/build_data.py scripts/sync_data.sh pyproject.toml  # pipeline files present
ls src/ crates/ functions/ svelte.config.js                    # frontend files present
```

---
### Task 2: Cleanup old scripts and update .gitignore

**Files:**
- Delete: `scripts/build_trends.py`
- Delete: `scripts/build_author_shards.mjs`
- Delete: `scripts/postbuild.mjs`
- Delete: `scripts/requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Delete old scripts**

```bash
git rm scripts/build_trends.py scripts/build_author_shards.mjs scripts/postbuild.mjs scripts/requirements.txt
```

- [ ] **Step 2: Update .gitignore**

Read the current `.gitignore` and ensure it contains all patterns below:

```
__pycache__/
node_modules/
build/
.env
static/data/*.db
static/data/*.parquet
static/data/author_graph.json
static/data/recommendations.json
static/data/embeddings/
static/data/fulltext/
static/data/category_graph.json
static/data/category_stats.json
static/data/timeseries.json
static/data/topics.json
static/data/author_rankings.json
```

Patterns added (the regeneratable JSONs):
```
static/data/category_graph.json
static/data/category_stats.json
static/data/timeseries.json
static/data/topics.json
static/data/author_rankings.json
```

- [ ] **Step 3: Remove stale tracked data files from git tracking**

Run:
```bash
git rm --cached static/data/category_graph.json static/data/author_rankings.json static/data/topics.json
```
(Only those currently tracked. `category_stats.json` and `timeseries.json` may not be tracked yet.)

Verify:
```bash
git status
```
Expected: staged deletions of old JSONs, modified .gitignore.

- [ ] **Step 4: Verify frontend integrity**

Run:
```bash
ls static/data/category_graph.json static/data/category_hierarchy.json  # still on disk
ls static/data/authors/shard-0.json static/data/timeseries/2007-05.json  # old data still on disk
ls src/ crates/ functions/ svelte.config.js  # frontend intact
```

- [ ] **Step 5: Commit cleanup**

```bash
git add -A
git commit -m "chore: remove old build scripts, update .gitignore for regeneratable data files"
```

---
### Task 3: Verify the merge

- [ ] **Step 1: Check git log**

Run:
```bash
git log --oneline -10
```
Expected: merge commit + cleanup commit at HEAD. All pipeline commits reachable in history.

- [ ] **Step 2: Run frontend typecheck**

```bash
npm run check 2>&1 | tail -10
```
Expected: typecheck passes (0 errors).
