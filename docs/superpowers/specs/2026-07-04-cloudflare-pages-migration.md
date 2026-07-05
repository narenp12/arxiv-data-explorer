# Cloudflare Pages Migration

**Date**: 2026-07-04
**Status**: Draft
**Reason**: Vercel Hobby's 250MB per-file limit blocks the 447MB `search_2020-2026.db`; CF Pages free tier removes this constraint at $0.

---

## 1. Platform Comparison

| Constraint | Vercel Hobby | Cloudflare Pages |
|-----------|-------------|-----------------|
| Per-file size | 250MB | 500MB (soft) |
| Bandwidth | 100GB/mo | Unlimited |
| Builds | 100/day | 500/month |
| Custom domain + SSL | Yes | Yes |
| Static site adapter | `adapter-static` | `adapter-cloudflare-pages` |

Our largest asset is `search_2020-2026.db` at 447MB — fits CF Pages, exceeds Vercel.

---

## 2. Changes Required

### 2.1 Adapter swap

`svelte.config.js`:
- Replace `@sveltejs/adapter-static` with `@sveltejs/adapter-cloudflare-pages`
- No config change needed — both produce a flat `build/` directory

### 2.2 Remove Vercel-specific files

- Delete `vercel.json` if exists (not currently checked in)
- No project-level CF Pages config needed for basic static hosting

### 2.3 Frontend (no changes)

- `db.ts` loads from `{base}/data/search_{range}.db` — same URL pattern works on CF Pages
- `static/data/` contents deployed as-is
- sql.js-httpvfs Range requests work identically

### 2.4 Build pipeline (no changes)

- `scripts/build_data.py` already outputs to `static/data/` — no relocation needed
- `build_search_db` already splits by 5-year ranges — stays the same

---

## 3. Deployment

### 3.1 Git integration (recommended)

1. Push repo to GitHub
2. Cloudflare Dashboard → Pages → Connect Git → select repo
3. Build command: `npm run build`
4. Output directory: `build/`
5. Deploy: every push to `main` auto-deploys

### 3.2 Wrangler CLI (alternative)

```bash
npm install -g wrangler
wrangler pages deploy build/ --project-name=arxiv-explorer
```

---

## 4. Future Scaling

| When | What happens | Fix (free) |
|------|-------------|------------|
| ~2028 | `search_2020-2026.db` exceeds 500MB | Split into `2020-2022` + `2023-2026` (~230MB each) |
| Total site > ~1GB (soft limit) | Pages deployment may flag | Move DBs to R2 (10GB free, zero egress) |
| More than 500 builds/month | Over free tier | Reduce deploy frequency (unlikely with ~10 deploys/mo) |

---

## 5. Cost Summary

Everything $0, nothing needs a credit card:

- Cloudflare Pages free tier
- GitHub public repo
- OpenAlex API (no key)
- sql.js MIT license
- D3.js BSD-3 license
