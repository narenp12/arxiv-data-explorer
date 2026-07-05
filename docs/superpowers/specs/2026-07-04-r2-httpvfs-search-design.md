# R2 + HTTP Range-Request Search Architecture

**Date**: 2026-07-04
**Status**: Implemented and verified locally. R2 upload + Cloudflare Pages deploy pending (requires Cloudflare account access).

## Problem

The previous plan (see `2026-07-04-cloudflare-pages-migration.md`) assumed Cloudflare Pages allows files up to 500MB. That is wrong: **CF Pages static assets are capped at 25 MiB per file**. None of the four search DBs (45–447MB) can be deployed as Pages assets. Separately, the old design forced users to download 45–447MB of SQLite before searching at all.

## Decision

Keep the site fully static ($0 constraint). Host the SQLite files in a **Cloudflare R2** bucket (10GB storage free, zero egress) and replace whole-file `sql.js` loading with **`sql.js-httpvfs`**: a WASM SQLite that reads individual 4KB database pages over HTTP Range requests, on demand, from a Web Worker.

Measured result (real 447MB `search_2020-2026.db`): one search query fetches **~10.75MB in ~2,700 range requests** instead of downloading 447MB. First search is usable in seconds.

## Alternatives rejected

- **Full-download sql.js from R2/HuggingFace** — minimal change, but 45–447MB downloads; mobile-hostile.
- **Worker + D1** — D1 free tier caps DBs at 500MB and writes at 100K rows/day, making 3M-row imports and refreshes painful; abandons the static principle.

## Components

- `scripts/build_data.py` — builds `search_{range}.db` (FTS5) and new `detail_{range}.db` (plain table: id, abstract, categories, doi, license, update_date) with explicit `PRAGMA page_size = 4096` + VACUUM. `year_from_id` now parses old-style IDs (`hep-th/9901001`), fixing silent exclusion of all pre-2007 papers.
- `src/lib/utils/db.ts` — httpvfs worker per year range, cached; `searchPapers()` merges results across ranges by FTS5 rank (fixes the old pagination bug); `getPaperDetail(id)` routes to the right detail DB by ID.
- `src/lib/components/SearchView.svelte` — async search; tolerates individual range DBs failing to load.
- `scripts/upload_r2.sh` + `infra/r2-cors.json` — upload via rclone (wrangler caps single PUTs ~300MB) and CORS rules (GET/HEAD, Range headers).
- `VITE_DATA_BASE_URL` — base URL for `.db` files; R2 public URL in production, `http://localhost:8082` (range-capable `http-server`) in dev via `.env.local`.

## Constraints & invariants

- `requestChunkSize` in db.ts **must equal** `SQLITE_PAGE_SIZE` in build_data.py (4096).
- The `.db` host must support HTTP Range requests and CORS (`Range` allowed, `Content-Range` exposed). Vite's own static serving is not guaranteed to — hence the separate data server in dev.
- `sql.js-httpvfs` is UMD: import it via default import (named imports break Vite SSR interop), and call `db.exec(sql, [params])` — the Comlink-proxied `query(sql, ...params)` drops variadic params.
- Detail DBs measure ~2.9KB/paper → ~8.5GB for the full corpus. Do NOT upload them to R2 as-is (search DBs 818MB + detail 8.5GB ≈ the entire 10GB free tier). Resolve before shipping Task 5: compress abstracts (deflate BLOB + DecompressionStream) or fetch abstracts from the OpenAlex API on demand.

## Free-tier budget

| Resource | Limit | Usage |
|---|---|---|
| R2 storage | 10GB | 818MB (search DBs only) |
| R2 Class B reads | 10M/month | ~2,700/query → ~3,700 queries/month; tune page size upward if this binds |
| Pages deploy | 25 MiB/file | DBs are gitignored, never enter the deploy |
