# Daft Pipeline Merge & Cleanup Design

## Purpose

Merge the 8-commit `daft-pipeline` branch into `main`, preserving all existing frontend components, and cleaning up old scripts and data-file tracking now that the unified Daft pipeline supersedes previous bespoke build scripts.

## Merge Strategy

`git checkout main && git merge daft-pipeline`. Both branches diverged at `683b6ab` (the common ancestor); `main` has zero additional commits. The only file conflicts are regenerated static data JSONs that exist on both branches — take the pipeline branch versions.

No squash, no rebase. The 8 pipeline commits remain in the history as a first-class merge commit.

## Cleanup

Delete these scripts (superseded by `scripts/build_data.py` — the single pipeline replaces all of them):

- `scripts/build_trends.py`
- `scripts/build_author_shards.mjs`
- `scripts/postbuild.mjs`
- `scripts/requirements.txt`

Keep `scripts/utils.py` (still used by build_data.py).

## Data File Tracking

### Tracked in git
- `static/data/category_hierarchy.json` — defines the category taxonomy, changes rarely

### Gitignored (regeneratable by pipeline)
- `static/data/category_graph.json`
- `static/data/category_stats.json`
- `static/data/timeseries.json`
- `static/data/topics.json`
- `static/data/author_rankings.json`

### Already gitignored (or to be added)
- `static/data/*.db`
- `static/data/*.parquet`
- `static/data/author_graph.json`
- `static/data/recommendations.json`
- `static/data/embeddings/`
- `static/data/fulltext/`

### Old data preserved (frontend depends on these paths)
- `static/data/authors/shard-*.json` and `top80.json`
- `static/data/timeseries/<yyyy-mm>.json` (per-month files)
- `static/data/category_dynamics.json`
- `static/data/causal_edges.json`
- `static/data/network_stats.json`
- `data-src/author_graph.json`

## Backward Compatibility

No frontend breakage. All existing data paths continue to exist. The pipeline adds new outputs alongside them (e.g. `static/data/timeseries.json` coexists with the per-month `static/data/timeseries/` directory). Frontend components continue loading from their original paths unchanged.

## `.gitignore` Updates

Add patterns for the newly-regeneratable JSON files listed above. Combined with the existing patterns from the pipeline branch.
