# Comprehensive arXiv Research Paper Explorer — Design

**Date**: 2026-07-05
**Status**: Draft

## 1. Vision

Transform the arXiv Explorer from a search + trends dashboard into a comprehensive research paper explorer. Add concept-based browsing, author profiles, citation graph traversal, related papers, and advanced search filters — all built on a new OpenAlex supplemental data layer while keeping S2 as the primary search provider and precomputed analytics untouched.

## 2. Architecture

```
Browser ──→ /api/s2/* ──→ CF Proxy ──→ api.semanticscholar.org  (search + detail)
         │
         └─→ /api/openalex/* ──→ CF Proxy ──→ api.openalex.org    (concepts, citations, authors)
         │
         └─→ static/data/* ──→ static deploy ──→ precomputed JSON (trends, categories, author graph)
```

### 2.1 Data source roles

| Source | Role | Rationale |
|--------|------|-----------|
| S2 API | Search, primary paper detail | Only free option with full-text search API |
| OpenAlex API | Concepts, citation graph, author profiles, related works | CORS-enabled, 10 req/s free, updated weekly |
| Precomputed JSON | Trends, categories, author rankings | Already deployed, no changes needed |

### 2.2 Cross-source joining

The bridge between S2 and OpenAlex is the DOI:

```
arXiv ID → S2 paper detail → externalIds.DOI → GET /works/doi:{doi} on OpenAlex
```

For paper detail pages, call both APIs and merge results. S2 provides title, authors, venue, PDF link. OpenAlex provides concepts, citation counts, references, related works.

## 3. Phase 1: Advanced search filters (no new data source)

### 3.1 Changes

- Add filter bar to `SearchView.svelte` with year range, category, and min citation count controls
- All filters serialize to URL search params (`/papers?q=transformer&year=2020-2024&cat=cs&minCites=10`)
- S2 API already supports `year=`, `fieldsOfStudy=`, `minCitationCount=` query params
- Filters are debounced together with the search query — a single API call per search
- No backend changes

### 3.2 Components

- `SearchFilters.svelte` — filter bar component with year picker, category dropdown, citation count input
- Category dropdown populated from existing `static/data/category_hierarchy.json`

### 3.3 S2 API param mapping

| UI filter | S2 API param | Type |
|-----------|-------------|------|
| Year range | `year=2019-2024` | string |
| S2 field of study | `fieldsOfStudy=Computer Science` | string (single) |
| Min citations | `minCitationCount=10` | integer |

**Note:** S2's `fieldsOfStudy` is a broad classification (Computer Science, Medicine, Biology, Psychology, etc.) — this is NOT the arXiv taxonomy. We use arXiv categories for the category hierarchy page; for search filtering, S2's fields are what the API supports.

## 4. Phase 2: OpenAlex integration

### 4.1 CF proxy

New file: `functions/api/openalex/[[path]].js`

Identical pattern to `functions/api/s2/[[path]].js`:
- Forwards requests to `api.openalex.org/{path}`
- Adds `Cache-Control: public, max-age=3600` (OpenAlex data changes rarely)
- Proxies response headers, handles errors

### 4.2 Utility functions

New file: `src/lib/utils/openalex.ts`

| Function | OpenAlex endpoint | Use |
|----------|------------------|-----|
| `fetchConcepts(doi)` | `GET /works/doi:{doi}` → `concepts` | Concept tags on detail page, concept browsing |
| `fetchAuthorProfile(id)` | `GET /authors/{id}` | Author profile pages |
| `fetchReferences(id)` | `GET /works/{id}/references` | Related papers tab |
| `fetchCitations(id)` | `GET /works/{id}/citations` | Citation graph, related papers tab |
| `fetchRelatedWorks(id)` | `GET /works/{id}/related_works` | Similar papers tab |

All use a shared `rateLimitedFetch` adapted from `db.ts` but configured for OpenAlex's 10 req/s limit.

### 4.3 Types

Add to `src/lib/types.ts`:

```ts
interface ConceptTag {
  id: string;       // OpenAlex concept ID
  name: string;     // e.g. "Transformer (machine learning model)"
  score: number;    // relevance 0-1
  level: number;    // 0 (broad) to 5 (specific)
  wikidata: string;
  image_url: string | null;
  image_thumbnail_url: string | null;
}

interface AuthorProfile {
  id: string;
  name: string;
  orcid: string | null;
  works_count: number;
  cited_by_count: number;
  h_index: number;
  i10_index: number;
  affiliations: { name: string; years: [number, number] }[];
  // Top co-authors computed client-side from works list
}

interface WorkSummary {
  id: string;       // OpenAlex work ID
  title: string;
  authors: { name: string; author_id: string }[];
  publication_year: number | null;
  doi: string | null;
  cited_by_count: number;
}
```

### 4.4 Integration into existing detail page

In Phase 2, the only behavioral change to the existing `/papers/[id]` page is: after loading from S2, also call `fetchConcepts()` from OpenAlex and store the result (not yet displayed). This "pre-warms" the concept data so Phase 3's concept tagging has zero perceived latency.

## 5. Phase 3: Concept browsing + Author profiles

### 5.1 Concept browsing

Route: `/concepts` (overview) and `/concepts/[id]` (single concept)

**Browse page (`/concepts`):**
- Expandable tree of OpenAlex concept hierarchy, grouped by level
- Top-level concepts (level 0) shown as cards with paper count
- Click to drill into sub-concepts (level 1-5)
- Each concept node shows paper count, associated categories

**Concept detail (`/concepts/[id]`):**
- Concept name, description, associated fields
- Paginated list of arXiv papers tagged with this concept
  - `GET /works?filter=concept.id:{id}&per_page=25`
- Filter by sub-concept or year

**Per-paper concept tags:**
- Show as small pills under abstract on `/papers/[id]`
- Colored by level, clickable → navigates to `/concepts/{id}`
- "Explore more like this" button → concept detail page

### 5.2 Author profiles

Route: `/authors/[id]`

**Data sources:**
- OpenAlex `/authors/{id}` for profile info
- OpenAlex `/works?filter=authorships.author.id:{id}` for paper list
- Existing `static/data/authors/top80.json` for co-author network snippet

**Profile page:**
- Name, ORCID link, institutional affiliations with duration
- Stats bar: papers count, cited by count, h-index, i10-index
- Paginated paper list (title, year, citation count, venue)
- Top co-authors (computed from paper list)
- Link to existing author ranking page (name-based, for top authors)

**Cross-references:**
- Author names in search results link to `/authors/{id}` (resolved via S2 `authorId` from paper detail data)
- **Note:** Current `PaperResult.authors` is a flat string. Phase 3 must add `S2Author[]` (with `authorId`) to `PaperResult` and store author IDs during search/detail fetches so profile links can be generated.
- Author ranking page gets profile links for top authors (name → OpenAlex search → first match)

## 6. Phase 4: Related papers + Citation graph

### 6.1 Related papers tabs

On `/papers/[id]`, add three tabs below the detail:

| Tab | API call | Display |
|-----|----------|---------|
| References | `GET /works/{id}/references` | Compact list (title, authors, year, citations) |
| Citations | `GET /works/{id}/citations` | Same list format |
| Similar | `GET /works/{id}/related_works` | Same list format |

Each tab loads on first click only (lazy). Results are paginated via OpenAlex's `per_page` + `page` params. Each result links to `/papers/{id}` if it's an arXiv paper, or to OpenAlex otherwise.

### 6.2 Citation graph

Small D3 force-directed graph below the related papers tabs:
- Center: current paper
- Ring 1: direct references and citations (up to 20 nodes)
- Ring 2: references of references (up to 10 additional nodes, if data resolves fast)
- Node size: citation count
- Edge direction: arrow from citing to cited
- Hover: tooltip with title + year
- Click: navigate to that paper's page
- Degrade gracefully to list view if API calls time out (>3s total)

Reuses existing D3 dependency in `package.json`. The graph is a visual companion to the tabular data, not a replacement — users who prefer lists can ignore it.

## 7. Implementation order

| Phase | Dependencies | Rationale |
|-------|-------------|-----------|
| 1. Search filters | None | Ship something visible immediately, zero infra cost |
| 2. OpenAlex integration | None | Foundation for everything else, but doesn't change UI yet |
| 3. Concept browsing + Author profiles | Phase 2 | Both use the data layer from Phase 2 |
| 4. Related papers + Citation graph | Phase 2 | Also uses Phase 2 data layer; heaviest UI work last |

## 8. Error handling

- All OpenAlex calls wrapped in try/catch; failures never block the S2 data from rendering
- Phase 2 integration is invisible to users — OpenAlex failures only affect future feature pages
- Feature pages (concepts, author profiles) show empty state + "OpenAlex unavailable" message on failure
- Citation graph has a 3s timeout; falls back to tabular list view
- Rate limits: OpenAlex 10 req/s with automatic retry on 429 (same pattern as S2 in db.ts)

## 9. Non-goals

- Replacing S2 as the search provider — OpenAlex has no full-text search endpoint
- Storing OpenAlex data permanently — fetched on demand, cached by CF proxy
- Author disambiguation for the author ranking page — name-based ranking stays as-is; profiles are opt-in via OpenAlex IDs
- Offline support — all OpenAlex features require network

## 10. Open questions

- h-index on author profiles: compute from fetched paper list, or read from OpenAlex's `summary_stats` field?
- Author profile resolution: name search from ranking page → pick first match, or show disambiguation UI?
- Should concept browsing prefetch the full concept hierarchy on load, or lazy-load per drill-down?
