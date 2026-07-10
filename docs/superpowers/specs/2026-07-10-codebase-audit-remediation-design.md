# Codebase Audit Remediation

**Date:** 2026-07-10
**Source:** Polymath codebase audit findings
**Strategy:** Parallel workstreams (Approach C)

## Scope

Remediate all 7 action items from the codebase audit. Items span config cleanup,
dead-code deletion, architectural decisions, test coverage, and refactoring.

## Workstream 1: Housekeeping

Fully parallelizable — no decisions to wait on.

### 1A. Delete Confirmed Dead Scripts

| File | Reason |
|---|---|
| `scripts/build_trends.py` | Replaced by `scripts/build_data.py` |
| `scripts/utils.py` | `strip_latex()` not called by any remaining script |
| `scripts/postbuild.mjs` | Already removed from `package.json` build step |
| `scripts/requirements.txt` | Superseded by `uv.lock` / `pyproject.toml` |

### 1B. Right-size ~/.claude/CLAUDE.md

- Remove 38 stale jCodemunch tool references (e.g. `Read`, `Write`, `Edit`,
  `search_symbols`, `get_blast_radius`, etc.) that no longer correspond to the
  installed tool set.
- Inline a one-liner: `"Call jcodemunch_guide and strictly follow its instructions."`
  plus any user-specific preferences.
- Saves ~2,500 tokens per agent turn.

The global file (~/.claude/CLAUDE.md) will be edited. No repo-local override added
(keeps the source of truth in one place).

### 1C. Add Layer Rules to .jcodemunch.jsonc

Define architectural boundaries for the three main layers:

```jsonc
"architecture": {
  "layers": [
    {
      "name": "utils",
      "paths": ["src/lib/utils", "src/lib/stores", "src/lib/authors"],
      "may_not_import": ["src/routes"]
    },
    {
      "name": "scripts",
      "paths": ["scripts"],
      "may_not_import": ["src", "crates"]
    },
    {
      "name": "crates",
      "paths": ["crates"],
      "may_not_import": ["src", "scripts"]
    }
  ]
}
```

This enforces the correct dependency direction: utility code never imports
route code; build scripts never import application code; Rust crates never
import Python/TS code.

### 1D. Re-index

Running `index_folder` to catch up from indexed SHA `683b6ab` to `c917e9c`.

## Workstream 2: Rust Crate Audit

Decision gate — output drives whether `wasm-search.ts` needs testing.

### 2A. Analysis (I will dump per-crate findings)

- `crates/arxcheck/` — validation CLI for data-file integrity (API contract, edges,
  graph, shards, cross-references). WASM bindings exist but no TS consumer detected.
- `crates/arxwasm/` — author search engine (trie + trigram + ranker). Wrapper at
  `src/lib/authors/wasm-search.ts` exists but no route currently calls it.

### 2B. Decision Options

| Option | Action |
|---|---|
| Keep both | Add tests for wasm-search.ts; fix WASM build wiring if broken |
| Kill both | Delete `crates/`, delete `wasm-search.ts`; simplify build |
| Keep arxwasm, delete arxcheck | Keep author search (planned feature), drop unused validation CLI |

## Workstream 3: Quality

Depends on WS2 outcome (Rust keep/kill affects test scope).

### 3A. Tests for `openalex.ts`

Currently 0 test coverage. Key functions to test:
- `rateLimitedFetch` — rate limiting, queueing, in-flight de-duplication
- `openalexIdFromUrl` / `normalizeOpenAlexId` / `arxivIdFromDoi` — URL parsing
- `fetchConcepts` / `fetchAuthorProfile` — response parsing
- `parseWork` — OpenAlex → internal format mapping
- `fetchReferences` / `fetchCitations` / `fetchRelatedWorks` — network call + parse

### 3B. Tests for `db.ts` Internals

Current tests cover search flows but skip internals:
- `ensureChecker` — WASM checker init
- `sanitiseYearRange` / `sanitiseMinCites` — input sanitisation
- `getCached` / `setCached` / `clearSearchCache` — LRU cache behaviour
- `rateLimitedFetchOnce` / `rateLimitedFetch` — rate limiting
- `arxivId` / `authorList` / `getProp` — XML parsing helpers
- `buildSearchUrl` — URL construction
- `parseSearchResponse` / `parseArxivResponse` / `parseArxivTotal` — XML parsing
- `searchPapers` / `searchArxivCategory` — integration-level search (already covered)

### 3C. (Conditional) Tests for `wasm-search.ts`

Only if WS2 decides to keep `crates/arxwasm`. Tests for:
- `loadAuthorSearch` / `getInitError` — WASM init
- `searchAuthors` / `getStats` — search + stats

### 3D. Refactor `db.ts`

Last step (tests must exist first for regression safety).

`db.ts` is the riskiest file in the codebase: 5 of the top 10 hotspots,
34 symbols, 25 cyclomatic in `searchPapers`, 14 commits / 90 days churn.

Proposed modularisation:
| Module | Responsibility |
|---|---|
| `db/cache.ts` | LRU cache (`getCached`, `setCached`, `clearSearchCache`) |
| `db/rate-limit.ts` | Rate-limited fetch queue (`rateLimitedFetch`, `rateLimitedFetchOnce`) |
| `db/search.ts` | Search URL building + response parsing (`buildSearchUrl`, `parseSearchResponse`, `parseArxivResponse`, `parseArxivTotal`, `searchPapers`, `searchArxivCategory`) |
| `db/detail.ts` | Paper detail fetching (`getPaperDetail`, `arxivId`, `authorList`, `getProp`) |
| `db/index.ts` | Re-exports public API |

Each module is independently testable. No behavioural changes during extraction.

## Sequencing

```
Day 1 ─┬─ WS1 (housekeeping) ─── runs in parallel
        └─ WS2 (Rust analysis) ── I dump findings, user decides
Day 2 ── WS3 tests ── blocked on WS2 decision for wasm-search scope
Day 3 ── WS3 db.ts refactor ── blocked on WS3 tests passing
```

WS1 takes ~15 min. WS2 is async (user decision). WS3 is the heavy lift.

## Success Criteria

- [ ] Dead scripts deleted; build still passes
- [ ] CLAUDE.md under 100 tokens; no stale refs
- [ ] `jcodemunch_get_layer_violations` returns rules
- [ ] Index matches HEAD
- [ ] Rust crates: decision documented, actions taken
- [ ] `openalex.ts`: 90%+ statement coverage
- [ ] `db.ts` internals: 90%+ statement coverage
- [ ] `db.ts` refactored into scoped modules
- [ ] All 51 existing tests + new tests pass
- [ ] `npm run check` passes (0 errors, 0 warnings)
