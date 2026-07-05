# Comprehensive arXiv Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the arXiv Explorer into a comprehensive research paper explorer with concept browsing, author profiles, citation graph traversal, related papers, and advanced search filters — all backed by a new OpenAlex supplemental data layer.

**Architecture:** Three data sources — S2 API stays as the primary search/detail provider, OpenAlex is added as a supplemental source for concepts/citations/authors via CF proxy, and precomputed JSON files remain untouched. The bridge between them is the DOI (S2 `externalIds.DOI` → OpenAlex `doi:` lookup).

**Tech Stack:** SvelteKit 5, TypeScript, D3.js, Tailwind CSS 4, Cloudflare Pages Functions. OpenAlex API (free, 10 req/s, no key, CORS-enabled).

## Global Constraints

- All API calls subject to OpenAlex rate limit (10 req/s) — use retry/throttle same as S2 in `db.ts`
- No new npm dependencies — D3 already in package.json
- Precomputed JSON files in `static/data/` are read-only inputs, never modified
- All designs match `DESIGN.md` visual theme (Obsidian & Neon Ink dark theme, Space Mono body, no emojis)
- CF Pages Functions follow the exact pattern of `functions/api/s2/[[path]].js`
- Vite dev proxy mirrors CF Pages Functions — add both together

---
### Task 1: Search filters — filter bar component

**Files:**
- Create: `src/lib/components/SearchFilters.svelte`
- Modify: `src/lib/components/SearchView.svelte`
- Modify: `src/routes/papers/+page.svelte`

**Interfaces:**
- Consumes: `searchPapers()` from `src/lib/utils/db.ts` (already exists)
- Produces: `<SearchFilters>` component with `onChange` event dispatching `{ yearRange, fieldOfStudy, minCites }`

- [ ] **Step 1: Create SearchFilters.svelte**

```svelte
<script lang="ts">
	import { base } from "$app/paths";

	let { yearRange = "", fieldOfStudy = "", minCites = "", onChange }: {
		yearRange?: string;
		fieldOfStudy?: string;
		minCites?: string;
		onChange?: (filters: { yearRange: string; fieldOfStudy: string; minCites: string }) => void;
	} = $props();

	const S2_FIELDS = [
		{ value: "", label: "All fields" },
		{ value: "Computer Science", label: "Computer Science" },
		{ value: "Medicine", label: "Medicine" },
		{ value: "Biology", label: "Biology" },
		{ value: "Physics", label: "Physics" },
		{ value: "Mathematics", label: "Mathematics" },
		{ value: "Engineering", label: "Engineering" },
		{ value: "Psychology", label: "Psychology" },
		{ value: "Chemistry", label: "Chemistry" },
		{ value: "Materials Science", label: "Materials Science" },
		{ value: "Geology", label: "Geology" },
		{ value: "Environmental Science", label: "Environmental Science" },
		{ value: "Agricultural Science", label: "Agricultural Science" },
		{ value: "Economics", label: "Economics" },
		{ value: "Sociology", label: "Sociology" },
		{ value: "Political Science", label: "Political Science" },
		{ value: "Philosophy", label: "Philosophy" },
		{ value: "History", label: "History" },
		{ value: "Art", label: "Art" },
	];

	function dispatch() {
		onChange?.({ yearRange, fieldOfStudy, minCites });
	}
</script>

<div class="flex flex-wrap gap-3 items-end mb-4">
	<div class="flex flex-col gap-1">
		<label class="label-caps text-xs text-secondary" for="year-range">Year range</label>
		<input
			id="year-range"
			type="text"
			bind:value={yearRange}
			placeholder="e.g. 2020-2024"
			oninput={dispatch}
			class="w-36 rounded border border-outline bg-surface-container px-2.5 py-1.5 text-sm text-on-surface placeholder:text-outline focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors"
		/>
	</div>
	<div class="flex flex-col gap-1">
		<label class="label-caps text-xs text-secondary" for="field-of-study">Field of study</label>
		<select
			id="field-of-study"
			bind:value={fieldOfStudy}
			onchange={dispatch}
			class="w-44 rounded border border-outline bg-surface-container px-2.5 py-1.5 text-sm text-on-surface focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors"
		>
			{#each S2_FIELDS as f}
				<option value={f.value}>{f.label}</option>
			{/each}
		</select>
	</div>
	<div class="flex flex-col gap-1">
		<label class="label-caps text-xs text-secondary" for="min-cites">Min citations</label>
		<input
			id="min-cites"
			type="number"
			min="0"
			bind:value={minCites}
			placeholder="0"
			oninput={dispatch}
			class="w-24 rounded border border-outline bg-surface-container px-2.5 py-1.5 text-sm text-on-surface placeholder:text-outline focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors"
		/>
	</div>
</div>
```

- [ ] **Step 2: Modify SearchView.svelte to integrate filters**

Read the current SearchView.svelte first:

```bash
cat src/lib/components/SearchView.svelte
```

Replace the file to add filter integration. The key changes:
- Import SearchFilters
- Add filter state synced to URL search params
- Pass filters to `searchPapers()` as part of the API call

- [ ] **Step 3: Update the searchPapers call to pass filters**

Modify the `searchPapers` call in SearchView.svelte. When filters are active, append them to the S2 API URL:

```ts
// Inside the search handler, when calling searchPapers:
let url = `${API_BASE}/paper/search?query=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}&fields=${SEARCH_FIELDS}`;
if (options?.yearRange) url += `&year=${encodeURIComponent(options.yearRange)}`;
if (options?.fieldOfStudy) url += `&fieldsOfStudy=${encodeURIComponent(options.fieldOfStudy)}`;
if (options?.minCites) url += `&minCitationCount=${encodeURIComponent(options.minCites)}`;
```

- [ ] **Step 4: Verify build**

```bash
npm run build 2>&1 | tail -20
```

Expected: Build succeeds with no errors.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/SearchFilters.svelte src/lib/components/SearchView.svelte src/routes/papers/+page.svelte
git commit -m "feat: add advanced search filters (year, S2 field, min citations)"
```

---
### Task 2: OpenAlex CF proxy + dev proxy

**Files:**
- Create: `functions/api/openalex/[[path]].js`
- Modify: `vite.config.ts`

**Interfaces:**
- Produces: `/api/openalex/*` endpoint available in both dev and prod

- [ ] **Step 1: Create CF Pages Function proxy**

```js
// functions/api/openalex/[[path]].js
export async function onRequest({ request, params, env }) {
	const url = new URL(request.url);
	const path = Array.isArray(params.path) ? params.path.join("/") : (params.path ?? "");
	const upstream = new URL(`https://api.openalex.org/${path}`);
	upstream.search = url.search;

	const res = await fetch(upstream.toString(), {
		headers: {
			"User-Agent": "arxiv-data-explorer (Cloudflare Pages proxy)",
			Accept: "application/json",
		},
	});

	return new Response(res.body, {
		status: res.status,
		headers: {
			"Content-Type": res.headers.get("Content-Type") ?? "application/json",
			"Retry-After": res.headers.get("Retry-After") ?? "",
			"Cache-Control": res.ok ? "public, max-age=3600" : "no-store",
		},
	});
}
```

- [ ] **Step 2: Add dev proxy to vite.config.ts**

```ts
// Add this entry to the proxy map in vite.config.ts:
"/api/openalex": {
  target: "https://api.openalex.org",
  changeOrigin: true,
  rewrite: (path) => path.replace(/^\/api\/openalex/, ""),
},
```

After edit, the full `server.proxy` section should look like:

```ts
proxy: {
  "/api/arxiv": {
    target: "https://export.arxiv.org",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api\/arxiv/, "/api/query"),
  },
  "/api/s2": {
    target: "https://api.semanticscholar.org",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api\/s2/, ""),
  },
  "/api/openalex": {
    target: "https://api.openalex.org",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api\/openalex/, ""),
  },
},
```

- [ ] **Step 3: Verify proxy works in dev**

```bash
# Start dev server in background, then test the proxy
curl -s "http://localhost:5173/api/openalex/works/doi:10.48550/arXiv.2401.00001" | head -c 200
```

Expected: Returns JSON from OpenAlex (200 response with work data).

- [ ] **Step 4: Commit**

```bash
git add functions/api/openalex/[[path]].js vite.config.ts
git commit -m "feat: add OpenAlex API proxy (CF Functions + Vite dev)"
```

---
### Task 3: OpenAlex types + utility functions

**Files:**
- Create: `src/lib/utils/openalex.ts`
- Modify: `src/lib/types.ts`

**Interfaces:**
- Consumes: `/api/openalex/*` proxy (Task 2)
- Produces: `fetchConcepts`, `fetchAuthorProfile`, `fetchReferences`, `fetchCitations`, `fetchRelatedWorks` functions + `ConceptTag`, `AuthorProfile`, `WorkSummary` types

- [ ] **Step 1: Add types to src/lib/types.ts**

```ts
// Add after existing types:

export interface ConceptTag {
	id: string;
	name: string;
	score: number;
	level: number;
	wikidata: string;
	imageUrl: string | null;
	imageThumbnailUrl: string | null;
}

export interface AuthorProfile {
	id: string;
	name: string;
	orcid: string | null;
	worksCount: number;
	citedByCount: number;
	hIndex: number;
	i10Index: number;
	affiliations: { name: string; startYear: number | null; endYear: number | null }[];
	works: WorkSummary[];
	topCoAuthors: { name: string; authorId: string; count: number }[];
}

export interface WorkSummary {
	id: string;
	title: string;
	authors: { name: string; authorId: string }[];
	publicationYear: number | null;
	doi: string | null;
	citedByCount: number;
	arxivId: string | null;
	openalexUrl: string;
}
```

- [ ] **Step 2: Create src/lib/utils/openalex.ts**

```ts
const API_BASE = "/api/openalex";

const RATE_LIMIT_MS = 110; // ~9 req/s, under the 10 req/s free limit
let lastRequest = 0;
let requestQueue: Promise<void> = Promise.resolve();

async function rateLimitedFetch(url: string): Promise<Response> {
	const prev = requestQueue;
	let resolveNext: () => void;
	requestQueue = new Promise((r) => { resolveNext = r; });
	await prev;
	const now = Date.now();
	const wait = Math.max(0, RATE_LIMIT_MS - (now - lastRequest));
	if (wait > 0) await new Promise((r) => setTimeout(r, wait));
	lastRequest = Date.now();
	const res = fetch(url);
	res.finally(() => resolveNext!());
	return res;
}

function openalexIdFromUrl(url: string): string {
	return url.replace(/^https?:\/\/openalex\.org\//, "");
}

export async function fetchConcepts(doi: string | null, arxivId: string | null): Promise<ConceptTag[]> {
	const id = doi
		? `doi:${doi.replace(/^https?:\/\/doi\.org\//, "")}`
		: `arxiv:${arxivId}`;
	if (!id) return [];

	const res = await rateLimitedFetch(`${API_BASE}/works/${encodeURIComponent(id)}`);
	if (!res.ok) return [];
	const data = await res.json();
	return (data.concepts ?? []).map((c: Record<string, unknown>) => ({
		id: openalexIdFromUrl((c as { id?: string }).id ?? ""),
		name: (c as { display_name?: string }).display_name ?? "",
		score: (c as { score?: number }).score ?? 0,
		level: (c as { level?: number }).level ?? 0,
		wikidata: (c as { wikidata?: string }).wikidata ?? "",
		imageUrl: (c as { image_url?: string }).image_url ?? null,
		imageThumbnailUrl: (c as { image_thumbnail_url?: string }).image_thumbnail_url ?? null,
	}));
}

export interface OpenAlexWork {
	id: string;
	title: string;
	authors: { name: string; authorId: string }[];
	publicationYear: number | null;
	doi: string | null;
	citedByCount: number;
}

function parseWork(d: Record<string, unknown>): OpenAlexWork {
	const authorships = (d as { authorships?: Record<string, unknown>[] }).authorships ?? [];
	const doi = (d as { doi?: string | null }).doi ?? null;
	return {
		id: openalexIdFromUrl((d as { id?: string }).id ?? ""),
		title: (d as { title?: string }).title ?? "",
		authors: authorships.map((a) => ({
			name: (a as { author?: Record<string, unknown> }).author?.display_name as string ?? "",
			authorId: openalexIdFromUrl((a as { author?: Record<string, unknown> }).author?.id as string ?? ""),
		})),
		publicationYear: (d as { publication_year?: number | null }).publication_year ?? null,
		doi: doi ? doi.replace(/^https?:\/\/doi\.org\//, "") : null,
		citedByCount: (d as { cited_by_count?: number }).cited_by_count ?? 0,
	};
}

export async function fetchAuthorProfile(id: string): Promise<AuthorProfile | null> {
	const res = await rateLimitedFetch(`${API_BASE}/authors/${encodeURIComponent(id)}`);
	if (!res.ok) return null;
	const d = await res.json();
	const affs = (d as { last_known_institutions?: Record<string, unknown>[] }).last_known_institutions ?? [];
	const summary = (d as { summary_stats?: Record<string, unknown> }).summary_stats ?? {};
	const worksRes = await rateLimitedFetch(
		`${API_BASE}/works?filter=authorships.author.id:${encodeURIComponent(id)}&per_page=50&sort=cited_by_count:desc&select=id,title,authorships,publication_year,doi,cited_by_count`,
	);
	const works = worksRes.ok ? (await worksRes.json()).results?.map(parseWork) ?? [] : [];

	const coAuthorMap = new Map<string, { name: string; count: number }>();
	for (const w of works) {
		for (const a of w.authors) {
			if (a.authorId === id) continue;
			const entry = coAuthorMap.get(a.authorId) ?? { name: a.name, count: 0 };
			entry.count++;
			coAuthorMap.set(a.authorId, entry);
		}
	}
	const topCoAuthors = Array.from(coAuthorMap.entries())
		.map(([authorId, v]) => ({ authorId, name: v.name, count: v.count }))
		.sort((a, b) => b.count - a.count)
		.slice(0, 10);

	return {
		id,
		name: (d as { display_name?: string }).display_name ?? "",
		orcid: (d as { orcid?: string | null }).orcid ?? null,
		worksCount: (d as { works_count?: number }).works_count ?? 0,
		citedByCount: (d as { cited_by_count?: number }).cited_by_count ?? 0,
		hIndex: (summary as { h_index?: number }).h_index ?? 0,
		i10Index: (summary as { i10_index?: number }).i10_index ?? 0,
		affiliations: affs.map((inst) => ({
			name: (inst as { display_name?: string }).display_name ?? "",
			startYear: (inst as { start_year?: number | null }).start_year ?? null,
			endYear: (inst as { end_year?: number | null }).end_year ?? null,
		})),
		works,
		topCoAuthors,
	};
}

export async function fetchReferences(id: string, perPage = 25): Promise<WorkSummary[]> {
	const res = await rateLimitedFetch(
		`${API_BASE}/works/${encodeURIComponent(id)}/references?per_page=${perPage}&select=id,title,authorships,publication_year,doi,cited_by_count`,
	);
	if (!res.ok) return [];
	const data = await res.json();
	return (data.results ?? []).map(parseWork);
}

export async function fetchCitations(id: string, perPage = 25): Promise<WorkSummary[]> {
	const res = await rateLimitedFetch(
		`${API_BASE}/works/${encodeURIComponent(id)}/citations?per_page=${perPage}&select=id,title,authorships,publication_year,doi,cited_by_count`,
	);
	if (!res.ok) return [];
	const data = await res.json();
	return (data.results ?? []).map(parseWork);
}

export async function fetchRelatedWorks(id: string, perPage = 25): Promise<WorkSummary[]> {
	const res = await rateLimitedFetch(
		`${API_BASE}/works/${encodeURIComponent(id)}/related_works?per_page=${perPage}&select=id,title,authorships,publication_year,doi,cited_by_count`,
	);
	if (!res.ok) return [];
	const data = await res.json();
	return (data.results ?? []).map(parseWork);
}
```

- [ ] **Step 3: Verify build**

```bash
npm run build 2>&1 | tail -20
```

Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add src/lib/types.ts src/lib/utils/openalex.ts
git commit -m "feat: add OpenAlex utility functions and types"
```

---
### Task 4: Pre-warm concepts on paper detail page

**Files:**
- Modify: `src/routes/papers/[...id]/+page.svelte`

**Interfaces:**
- Consumes: `fetchConcepts()` from `openalex.ts`

- [ ] **Step 1: Read current detail page**

```bash
cat src/routes/papers/[...id]/+page.svelte
```

- [ ] **Step 2: Add concept pre-warming**

After the existing `getPaperDetail` call, add an `$effect` that fetches concepts when the detail loads:

```ts
// Add to the <script> section, after the existing $effect block:
let concepts = $state<ConceptTag[]>([]);

$effect(() => {
	if (!detail) return;
	// Pre-warm concept data — will be displayed in Phase 3
	const doi = detail.doi;
	const arxivId = detail.id;
	if (doi || arxivId) {
		import("$lib/utils/openalex").then(({ fetchConcepts }) =>
			fetchConcepts(doi, arxivId).then((c) => { concepts = c; })
		);
	}
});
```

- [ ] **Step 3: Verify build**

```bash
npm run build 2>&1 | tail -20
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add src/routes/papers/[...id]/+page.svelte
git commit -m "feat: pre-warm concept data on paper detail page"
```

---
### Task 5: Concept browsing pages

**Files:**
- Create: `src/routes/concepts/+page.svelte`
- Create: `src/routes/concepts/concept.css`
- Create: `src/routes/concepts/[id]/+page.svelte`

**Interfaces:**
- Consumes: `fetchConcepts()` (indirectly — fetches works filtered by concept)
- Consumes: `WorkSummary` type

- [ ] **Step 1: Create concept browse page**

```svelte
<!-- src/routes/concepts/+page.svelte -->
<script lang="ts">
	import { base } from "$app/paths";

	let topConcepts = $state<{ id: string; name: string; worksCount: number }[]>([]);
	let loading = $state(true);

	$effect(() => {
		fetch("/api/openalex/concepts?per_page=25&sort=works_count:desc&filter=level:0&select=id,display_name,works_count")
			.then((r) => r.ok ? r.json() : { results: [] })
			.then((d) => {
				topConcepts = (d.results ?? []).map((c: Record<string, unknown>) => ({
					id: (c.id as string).replace(/^https?:\/\/openalex\.org\/concepts\//, ""),
					name: (c as { display_name?: string }).display_name ?? "",
					worksCount: (c as { works_count?: number }).works_count ?? 0,
				}));
			})
			.finally(() => { loading = false; });
	});
</script>

<svelte:head>
	<title>Concepts — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	<header class="mb-10 border-l-4 border-primary pl-8">
		<p class="label-caps mb-3 text-secondary">OpenAlex concept hierarchy</p>
		<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface">
			Browse by concept
		</h1>
	</header>

	{#if loading}
		<div class="flex items-center gap-2 text-secondary py-8">
			<span class="inline-block w-2 h-2 rounded-full bg-primary animate-pulse" />
			<span class="text-sm">Loading concepts…</span>
		</div>
	{:else if topConcepts.length === 0}
		<p class="text-secondary text-sm">No concepts loaded. OpenAlex might be unavailable.</p>
	{:else}
		<p class="text-xs text-secondary mb-6 uppercase tracking-wider">
			Top-level research fields — click to explore sub-concepts
		</p>
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
			{#each topConcepts as concept}
				<a
					href={`${base}/concepts/${concept.id}`}
					class="block rounded border border-outline bg-surface-container px-4 py-3 hover:bg-surface-container-low transition-colors"
				>
					<span class="text-sm font-bold text-on-surface">{concept.name}</span>
					<span class="block text-xs text-secondary mt-1">
						{concept.worksCount.toLocaleString()} works
					</span>
				</a>
			{/each}
		</div>
	{/if}
</div>
```

- [ ] **Step 2: Create concept detail page**

```svelte
<!-- src/routes/concepts/[id]/+page.svelte -->
<script lang="ts">
	import { page } from "$app/stores";
	import { base } from "$app/paths";

	let concept = $state<{ id: string; name: string; description: string | null; worksCount: number } | null>(null);
	let subConcepts = $state<{ id: string; name: string; worksCount: number }[]>([]);
	let works = $state<{ id: string; title: string; authors: string; year: number | null }[]>([]);
	let loading = $state(true);
	let worksPage = $state(1);
	let loadingMore = $state(false);

	async function loadConcept() {
		const id = $page.params.id;
		if (!id) return;

		loading = true;
		try {
			const [conceptRes, subRes, worksRes] = await Promise.all([
				fetch(`/api/openalex/concepts/${encodeURIComponent(id)}?select=id,display_name,description,works_count`),
				fetch(`/api/openalex/concepts?filter=parent_ids:${encodeURIComponent(id)}&per_page=50&select=id,display_name,works_count,sort=works_count:desc`),
				fetch(`/api/openalex/works?filter=concept.id:${encodeURIComponent(id)}&per_page=25&sort=cited_by_count:desc&select=id,title,authorships,publication_year`),
			]);

			if (conceptRes.ok) {
				const d = await conceptRes.json();
				concept = {
					id,
					name: d.display_name ?? "",
					description: d.description ?? null,
					worksCount: d.works_count ?? 0,
				};
			}

			if (subRes.ok) {
				const d = await subRes.json();
				subConcepts = (d.results ?? []).map((c: Record<string, unknown>) => ({
					id: (c.id as string).replace(/^https?:\/\/openalex\.org\/concepts\//, ""),
					name: (c as { display_name?: string }).display_name ?? "",
					worksCount: (c as { works_count?: number }).works_count ?? 0,
				}));
			}

			if (worksRes.ok) {
				const d = await worksRes.json();
				works = (d.results ?? []).map((w: Record<string, unknown>) => {
					const authorships = (w as { authorships?: Record<string, unknown>[] }).authorships ?? [];
					return {
						id: (w.id as string).replace(/^https?:\/\/openalex\.org\/works\//, ""),
						title: (w as { title?: string }).title ?? "",
						authors: authorships.map((a) => (a.author as { display_name?: string })?.display_name ?? "").join(", "),
						year: (w as { publication_year?: number | null }).publication_year ?? null,
					};
				});
			}
		} finally {
			loading = false;
		}
	}

	$effect(loadConcept);
</script>

<svelte:head>
	<title>{concept?.name ?? "Concept"} — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	<nav class="mb-6 text-xs text-secondary">
		<a href="{base}/concepts" class="hover:text-primary transition-colors">Concepts</a>
		<span class="mx-2">/</span>
		<span class="text-on-surface">{concept?.name ?? "…"}</span>
	</nav>

	{#if loading}
		<div class="flex items-center gap-2 text-secondary py-8">
			<span class="inline-block w-2 h-2 rounded-full bg-primary animate-pulse" />
			<span class="text-sm">Loading…</span>
		</div>
	{:else if !concept}
		<p class="text-secondary text-sm">Concept not found.</p>
	{:else}
		<header class="mb-8 border-l-4 border-primary pl-8">
			<p class="label-caps mb-3 text-secondary">Concept</p>
			<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface">
				{concept.name}
			</h1>
			{#if concept.description}
				<p class="text-sm text-secondary mt-3 max-w-2xl">{concept.description}</p>
			{/if}
			<p class="text-xs text-secondary mt-2">{concept.worksCount.toLocaleString()} works</p>
		</header>

		{#if subConcepts.length > 0}
			<section class="mb-10">
				<h2 class="font-display text-xl font-bold text-on-surface mb-4">Sub-concepts</h2>
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
					{#each subConcepts as sc}
						<a
							href="{base}/concepts/{sc.id}"
							class="block rounded border border-outline bg-surface-container px-3 py-2 hover:bg-surface-container-low transition-colors"
						>
							<span class="text-sm text-on-surface">{sc.name}</span>
							<span class="text-xs text-secondary ml-2">({sc.worksCount.toLocaleString()})</span>
						</a>
					{/each}
				</div>
			</section>
		{/if}

		<section>
			<h2 class="font-display text-xl font-bold text-on-surface mb-4">Top papers</h2>
			{#if works.length === 0}
				<p class="text-sm text-secondary">No papers found for this concept.</p>
			{:else}
				<div class="divide-y divide-outline-dim">
					{#each works as w}
						<div class="py-3">
							<a href="{base}/papers/{w.id}" class="text-sm font-bold text-on-surface hover:text-primary transition-colors">
								{w.title}
							</a>
							<p class="text-xs text-secondary mt-1">
								{w.authors}{#if w.year} · {w.year}{/if}
							</p>
						</div>
					{/each}
				</div>
			{/if}
		</section>
	{/if}
</div>
```

- [ ] **Step 3: Verify build**

```bash
npm run build 2>&1 | tail -20
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add src/routes/concepts/
git commit -m "feat: add concept browsing pages (browse + concept detail)"
```

---
### Task 6: Concept pills on detail page + search results

**Files:**
- Create: `src/lib/components/ConceptPill.svelte`
- Modify: `src/routes/papers/[...id]/+page.svelte`

**Interfaces:**
- Consumes: `ConceptTag[]` (pre-warmed in Task 4)

- [ ] **Step 1: Create ConceptPill component**

```svelte
<!-- src/lib/components/ConceptPill.svelte -->
<script lang="ts">
	import type { ConceptTag } from "$lib/types";
	import { base } from "$app/paths";

	let { concepts }: { concepts: ConceptTag[] } = $props();

	const LEVEL_COLORS: Record<number, string> = {
		0: "bg-phantom-violet/15 text-phantom-violet border-phantom-violet/30",
		1: "bg-phantom-violet/10 text-phantom-violet/90 border-phantom-violet/25",
		2: "bg-phantom-violet/8 text-phantom-violet/80 border-phantom-violet/20",
		3: "bg-phantom-violet/6 text-phantom-violet/70 border-phantom-violet/15",
		4: "bg-phantom-violet/5 text-phantom-violet/60 border-phantom-violet/10",
		5: "bg-phantom-violet/4 text-phantom-violet/50 border-phantom-violet/8",
	};
</script>

{#if concepts.length > 0}
	<div class="flex flex-wrap gap-1.5">
		{#each concepts as c}
			<a
				href="{base}/concepts/{c.id}"
				class="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] leading-tight transition-colors hover:opacity-80 {LEVEL_COLORS[c.level] ?? LEVEL_COLORS[5]}"
			>
				{c.name}
			</a>
		{/each}
	</div>
{/if}
```

- [ ] **Step 2: Add concept pills to detail page**

In `src/routes/papers/[...id]/+page.svelte`, after the abstract section, add:

```svelte
{#if concepts.length > 0}
	<div class="mt-6">
		<ConceptPill {concepts} />
	</div>
{/if}
```

And add the import at the top of the script section:

```ts
import ConceptPill from "$lib/components/ConceptPill.svelte";
```

- [ ] **Step 3: Verify build**

```bash
npm run build 2>&1 | tail -20
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/ConceptPill.svelte src/routes/papers/[...id]/+page.svelte
git commit -m "feat: display concept pills on paper detail page"
```

---
### Task 7: Author profile pages

**Files:**
- Create: `src/routes/authors/[id]/+page.svelte`
- Modify: `src/routes/authors/+page.svelte`
- Modify: `src/lib/utils/openalex.ts` (add `fetchAuthorPapers` helper)
- Modify: `src/lib/utils/db.ts` (store author IDs in PaperResult)

**Interfaces:**
- Consumes: `AuthorProfile`, `WorkSummary` types
- Produces: Author profile page at `/authors/[id]`

- [ ] **Step 1: Add author ID storage to PaperResult**

In `src/lib/utils/db.ts`, modify `PaperResult` interface:

```ts
export interface PaperResult {
	id: string;
	title: string;
	authors: string;
	authorsWithIds: { name: string; authorId: string }[];
	year: number | null;
	citationCount: number;
	isArxiv: boolean;
	s2Url: string;
}
```

Update `searchPapers` to populate `authorsWithIds`:

```ts
// Inside the map callback, change:
const authors = (d as { authors?: { name: string; authorId?: string }[] }).authors ?? [];
return {
	// ... existing fields ...
	authorsWithIds: authors.map((a) => ({
		name: a.name,
		authorId: a.authorId ?? "",
	})),
};
```

- [ ] **Step 2: Create author profile page**

```svelte
<!-- src/routes/authors/[id]/+page.svelte -->
<script lang="ts">
	import { page } from "$app/stores";
	import { base } from "$app/paths";
	import type { AuthorProfile } from "$lib/types";
	import { fetchAuthorProfile } from "$lib/utils/openalex";

	let profile = $state<AuthorProfile | null>(null);
	let loading = $state(true);

	$effect(() => {
		const id = $page.params.id;
		if (!id) return;
		loading = true;
		fetchAuthorProfile(id)
			.then((p) => { profile = p; })
			.finally(() => { loading = false; });
	});
</script>

<svelte:head>
	<title>{profile?.name ?? "Author"} — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	{#if loading}
		<div class="flex items-center gap-2 text-secondary py-8">
			<span class="inline-block w-2 h-2 rounded-full bg-primary animate-pulse" />
			<span class="text-sm">Loading…</span>
		</div>
	{:else if !profile}
		<p class="text-secondary text-sm">Author not found.</p>
	{:else}
		<header class="mb-8 border-l-4 border-primary pl-8">
			<p class="label-caps mb-3 text-secondary">Author profile</p>
			<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface">
				{profile.name}
			</h1>
			{#if profile.orcid}
				<a
					href="https://orcid.org/{profile.orcid}"
					target="_blank"
					rel="noopener noreferrer"
					class="text-xs text-primary hover:underline mt-1 inline-block"
				>
					ORCID: {profile.orcid}
				</a>
			{/if}
		</header>

		<div class="flex flex-wrap gap-4 mb-8">
			<div class="rounded border border-outline bg-surface-container px-4 py-3 text-center min-w-[100px]">
				<div class="text-2xl font-bold text-on-surface">{profile.worksCount}</div>
				<div class="text-xs text-secondary">Papers</div>
			</div>
			<div class="rounded border border-outline bg-surface-container px-4 py-3 text-center min-w-[100px]">
				<div class="text-2xl font-bold text-on-surface">{profile.citedByCount}</div>
				<div class="text-xs text-secondary">Citations</div>
			</div>
			<div class="rounded border border-outline bg-surface-container px-4 py-3 text-center min-w-[100px]">
				<div class="text-2xl font-bold text-on-surface">{profile.hIndex}</div>
				<div class="text-xs text-secondary">h-index</div>
			</div>
			<div class="rounded border border-outline bg-surface-container px-4 py-3 text-center min-w-[100px]">
				<div class="text-2xl font-bold text-on-surface">{profile.i10Index}</div>
				<div class="text-xs text-secondary">i10-index</div>
			</div>
		</div>

		{#if profile.affiliations.length > 0}
			<section class="mb-8">
				<h2 class="font-display text-xl font-bold text-on-surface mb-3">Affiliations</h2>
				<ul class="space-y-1">
					{#each profile.affiliations as aff}
						<li class="text-sm text-secondary">
							{aff.name}
							{#if aff.startYear || aff.endYear}
								<span class="text-xs text-outline">
									({aff.startYear ?? "?"}–{aff.endYear ?? "present"})
								</span>
							{/if}
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if profile.topCoAuthors.length > 0}
			<section class="mb-8">
				<h2 class="font-display text-xl font-bold text-on-surface mb-3">Top co-authors</h2>
				<div class="flex flex-wrap gap-2">
					{#each profile.topCoAuthors as co}
						<a
							href="{base}/authors/{co.authorId}"
							class="text-xs rounded border border-outline bg-surface-container px-2.5 py-1 hover:bg-surface-container-low transition-colors"
						>
							{co.name}
							<span class="text-outline ml-1">({co.count})</span>
						</a>
					{/each}
				</div>
			</section>
		{/if}

		<section>
			<h2 class="font-display text-xl font-bold text-on-surface mb-4">Top papers</h2>
			{#if profile.works.length === 0}
				<p class="text-sm text-secondary">No papers found.</p>
			{:else}
				<div class="divide-y divide-outline-dim">
					{#each profile.works as w}
						<div class="py-3">
							<a
								href="{base}/papers/{w.id}"
								class="text-sm font-bold text-on-surface hover:text-primary transition-colors"
							>
								{w.title}
							</a>
							<p class="text-xs text-secondary mt-1">
								{w.citedByCount} citations
								{#if w.publicationYear} · {w.publicationYear}{/if}
							</p>
						</div>
					{/each}
				</div>
			{/if}
		</section>
	{/if}
</div>
```

- [ ] **Step 3: Link author names to profile pages in search results**

Modify `SearchView.svelte` (or `PaperCard.svelte`) to render author names as links with the shape:

```svelte
{#each authorsWithIds as a}
	{#if a.authorId}
		<a href="{base}/authors/{a.authorId}" class="hover:text-primary transition-colors">
			{a.name}
		</a>
	{:else}
		<span>{a.name}</span>
	{/if}
	{#if !#last}, {/if}
{/each}
```

- [ ] **Step 4: Verify build**

```bash
npm run build 2>&1 | tail -20
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add src/routes/authors/[id]/+page.svelte src/routes/authors/+page.svelte src/lib/utils/db.ts
git commit -m "feat: add author profile pages with OpenAlex data"
```

---
### Task 8: Related papers tabs

**Files:**
- Create: `src/lib/components/RelatedPapersTabs.svelte`
- Modify: `src/routes/papers/[...id]/+page.svelte`

**Interfaces:**
- Consumes: `fetchReferences`, `fetchCitations`, `fetchRelatedWorks` from `openalex.ts`

- [ ] **Step 1: Create RelatedPapersTabs component**

```svelte
<!-- src/lib/components/RelatedPapersTabs.svelte -->
<script lang="ts">
	import { base } from "$app/paths";
	import { fetchReferences, fetchCitations, fetchRelatedWorks } from "$lib/utils/openalex";
	import type { WorkSummary } from "$lib/types";

	let { openalexWorkId, arxivId }: { openalexWorkId: string | null; arxivId: string } = $props();

	type TabId = "references" | "citations" | "similar";
	let activeTab = $state<TabId | null>(null);
	let references = $state<WorkSummary[]>([]);
	let citations = $state<WorkSummary[]>([]);
	let similar = $state<WorkSummary[]>([]);
	let loading = $state(false);

	const TABS: { id: TabId; label: string; count: number; data: WorkSummary[] } = $derived([
		{ id: "references", label: "References", count: references.length, data: references },
		{ id: "citations", label: "Citations", count: citations.length, data: citations },
		{ id: "similar", label: "Similar", count: similar.length, data: similar },
	]);

	async function switchTab(tab: TabId) {
		if (activeTab === tab) return;
		activeTab = tab;
		loading = true;
		try {
			let results: WorkSummary[] = [];
			const id = openalexWorkId ?? arxivId;
			if (!id) return;
			if (tab === "references") results = await fetchReferences(id);
			else if (tab === "citations") results = await fetchCitations(id);
			else if (tab === "similar") results = await fetchRelatedWorks(id);
			if (tab === "references") references = results;
			else if (tab === "citations") citations = results;
			else if (tab === "similar") similar = results;
		} finally {
			loading = false;
		}
	}
</script>

<div class="mt-8">
	<div class="flex gap-0 border-b border-outline-dim" role="tablist">
		{#each TABS as tab}
			<button
				role="tab"
				aria-selected={activeTab === tab.id}
				onclick={() => switchTab(tab.id)}
				class="px-4 py-2 text-sm transition-colors
					{activeTab === tab.id
						? 'text-primary border-b-2 border-primary font-bold'
						: 'text-secondary hover:text-on-surface hover:bg-surface-container'}"
			>
				{tab.label}
			</button>
		{/each}
	</div>

	<div role="tabpanel" class="pt-4">
		{#if !activeTab}
			<p class="text-xs text-secondary py-4">Select a tab to load related papers.</p>
		{:else if loading}
			<div class="flex items-center gap-2 text-secondary py-4">
				<span class="inline-block w-2 h-2 rounded-full bg-primary animate-pulse" />
				<span class="text-sm">Loading…</span>
			</div>
		{:else}
			{@const currentData = TABS.find((t) => t.id === activeTab)?.data ?? []}
			{#if currentData.length === 0}
				<p class="text-sm text-secondary py-4">No results found.</p>
			{:else}
				<div class="divide-y divide-outline-dim">
					{#each currentData as item}
						<div class="py-3">
							<a
								href="{base}/papers/{item.id}"
								class="text-sm font-bold text-on-surface hover:text-primary transition-colors"
							>
								{item.title}
							</a>
							<p class="text-xs text-secondary mt-1">
								{item.authors.slice(0, 3).map((a) => a.name).join(", ")}
								{#if item.publicationYear} · {item.publicationYear}{/if}
								· {item.citedByCount} citations
							</p>
						</div>
					{/each}
				</div>
			{/if}
		{/if}
	</div>
</div>
```

- [ ] **Step 2: Integrate into detail page**

In `src/routes/papers/[...id]/+page.svelte`, add below the detail content:

```svelte
{#if detail}
	<RelatedPapersTabs openalexWorkId={detail.doi} arxivId={detail.id} />
{/if}
```

```ts
import RelatedPapersTabs from "$lib/components/RelatedPapersTabs.svelte";
```

- [ ] **Step 3: Verify build**

```bash
npm run build 2>&1 | tail -20
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/RelatedPapersTabs.svelte src/routes/papers/[...id]/+page.svelte
git commit -m "feat: add related papers tabs (references, citations, similar)"
```

---
### Task 9: Citation graph visualization

**Files:**
- Create: `src/lib/components/CitationGraph.svelte`
- Modify: `src/routes/papers/[...id]/+page.svelte`

**Interfaces:**
- Consumes: `fetchReferences`, `fetchCitations` from `openalex.ts`
- Uses: D3.js (already in `package.json`)

- [ ] **Step 1: Create CitationGraph component**

```svelte
<!-- src/lib/components/CitationGraph.svelte -->
<script lang="ts">
	import { onMount } from "svelte";
	import * as d3 from "d3";
	import { base } from "$app/paths";
	import { fetchReferences, fetchCitations } from "$lib/utils/openalex";
	import type { WorkSummary } from "$lib/types";

	let { openalexWorkId, currentTitle, arxivId }: {
		openalexWorkId: string | null;
		currentTitle: string;
		arxivId: string;
	} = $props();

	let svgEl: SVGSVGElement;
	let containerEl: HTMLDivElement;
	let loading = $state(true);
	let timedOut = $state(false);

	interface GraphNode extends d3.SimulationNodeDatum {
		id: string;
		label: string;
		citationCount: number;
		isCenter: boolean;
	}

	interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
		source: string;
		target: string;
	}

	onMount(async () => {
		const TIMEOUT_MS = 3000;
		const controller = new AbortController();
		const timer = setTimeout(() => {
			controller.abort();
			timedOut = true;
			loading = false;
		}, TIMEOUT_MS);

		try {
			const id = openalexWorkId ?? arxivId;
			if (!id) { loading = false; return; }

			const [refs, cites] = await Promise.all([
				fetchReferences(id, 15),
				fetchCitations(id, 15),
			]);

			clearTimeout(timer);

			if (refs.length === 0 && cites.length === 0) {
				loading = false;
				return;
			}

			const nodeMap = new Map<string, GraphNode>();
			const links: GraphLink[] = [];

			nodeMap.set("center", {
				id: "center",
				label: currentTitle.slice(0, 50) + (currentTitle.length > 50 ? "…" : ""),
				citationCount: 100,
				isCenter: true,
			});

			for (const r of refs) {
				nodeMap.set(r.id, {
					id: r.id,
					label: r.title.slice(0, 50) + (r.title.length > 50 ? "…" : ""),
					citationCount: r.citedByCount,
					isCenter: false,
				});
				links.push({ source: "center", target: r.id });
			}

			for (const c of cites) {
				if (!nodeMap.has(c.id)) {
					nodeMap.set(c.id, {
						id: c.id,
						label: c.title.slice(0, 50) + (c.title.length > 50 ? "…" : ""),
						citationCount: c.citedByCount,
						isCenter: false,
					});
				}
				links.push({ source: c.id, target: "center" });
			}

			const nodes = Array.from(nodeMap.values());
			const width = containerEl.clientWidth;
			const height = 350;

			const svg = d3.select(svgEl)
				.attr("viewBox", [0, 0, width, height]);

			const simulation = d3.forceSimulation<GraphNode>(nodes)
				.force("link", d3.forceLink<GraphNode, GraphLink>(links).id((d) => d.id).distance(100))
				.force("charge", d3.forceManyBody().strength(-200))
				.force("center", d3.forceCenter(width / 2, height / 2));

			const link = svg.append("g")
				.selectAll("line")
				.data(links)
				.join("line")
				.attr("stroke", "var(--color-outline-dim, #3a494b)")
				.attr("stroke-width", 1)
				.attr("stroke-opacity", 0.5);

			const node = svg.append("g")
				.selectAll("g")
				.data(nodes)
				.join("g")
				.style("cursor", "pointer")
				.on("click", (_event, d) => {
					if (!d.isCenter) {
						window.location.href = `${base}/papers/${d.id}`;
					}
				});

			node.append("circle")
				.attr("r", (d) => d.isCenter ? 10 : Math.max(3, Math.sqrt(d.citationCount) * 0.8))
				.attr("fill", (d) => d.isCenter ? "var(--color-primary, #00dbe7)" : "var(--color-phantom-violet, #d0bcff)")
				.attr("stroke", "var(--color-surface-container, #181818)")
				.attr("stroke-width", 1.5);

			node.append("title")
				.text((d) => d.label);

			node.append("text")
				.text((d) => d.label.slice(0, 25) + (d.label.length > 25 ? "…" : ""))
				.attr("x", 12)
				.attr("y", 4)
				.attr("font-size", "10px")
				.attr("fill", "var(--color-secondary, #b9cacb)");

			simulation.on("tick", () => {
				link
					.attr("x1", (d) => (d.source as GraphNode).x!)
					.attr("y1", (d) => (d.source as GraphNode).y!)
					.attr("x2", (d) => (d.target as GraphNode).x!)
					.attr("y2", (d) => (d.target as GraphNode).y!);
				node.attr("transform", (d) => `translate(${d.x},${d.y})`);
			});

		} catch {
			clearTimeout(timer);
			if (!controller.signal.aborted) timedOut = true;
		} finally {
			loading = false;
		}
	});
</script>

<div bind:this={containerEl} class="mt-4">
	{#if loading}
		<div class="flex items-center gap-2 text-secondary py-4">
			<span class="inline-block w-2 h-2 rounded-full bg-primary animate-pulse" />
			<span class="text-sm">Loading citation graph…</span>
		</div>
	{:else if timedOut}
		<p class="text-xs text-secondary py-4">Citation graph timed out. Data is available in the tabular views above.</p>
	{:else}
		<svg bind:this={svgEl} class="w-full rounded border border-outline-dim bg-surface-container"></svg>
	{/if}
</div>
```

- [ ] **Step 2: Integrate into detail page**

In `src/routes/papers/[...id]/+page.svelte`, after `RelatedPapersTabs`:

```svelte
{#if detail}
	<CitationGraph openalexWorkId={detail.doi} currentTitle={detail.title} arxivId={detail.id} />
{/if}
```

```ts
import CitationGraph from "$lib/components/CitationGraph.svelte";
```

- [ ] **Step 3: Verify build**

```bash
npm run build 2>&1 | tail -20
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/CitationGraph.svelte src/routes/papers/[...id]/+page.svelte
git commit -m "feat: add citation graph visualization with D3.js"
```
