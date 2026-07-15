import type { ConceptTag, AuthorProfile, WorkSummary } from "$lib/types";

const API_BASE = "/api/openalex";

const RATE_LIMIT_MS = 110;
let lastRequest = 0;
let requestQueue: Promise<void> = Promise.resolve();
const inFlight = new Map<string, Promise<Response>>();

async function rateLimitedFetch(url: string, retries = 2): Promise<Response> {
	for (let attempt = 0; ; attempt++) {
		const prev = requestQueue;
		let resolveNext: () => void;
		requestQueue = new Promise((r) => { resolveNext = r; });
		await prev;

		const inflight = inFlight.get(url);
		if (inflight) { resolveNext!(); return inflight; }

		const now = Date.now();
		const wait = Math.max(0, RATE_LIMIT_MS - (now - lastRequest));
		if (wait > 0) await new Promise((r) => setTimeout(r, wait));
		lastRequest = Date.now();
		const promise = fetch(url);
		inFlight.set(url, promise);
		let res: Response;
		try {
			res = await promise;
		} finally {
			resolveNext!();
		}
		if (attempt >= retries || res.status !== 429) {
			if (inFlight.get(url) === promise) inFlight.delete(url);
			return res;
		}
		if (inFlight.get(url) === promise) inFlight.delete(url);
		const retryAfter = parseInt(res.headers.get("Retry-After") ?? "1", 10);
		await new Promise((r) => setTimeout(r, Math.min(retryAfter * 1000, 5000)));
	}
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

function normalizeOpenAlexId(id: string): string {
	if (/^(doi|arxiv|pmid|pmcid):/i.test(id)) return id;
	if (id.includes("/")) return `doi:${id}`;
	if (/^\d{4}\.\d{4,5}$/.test(id)) return `arXiv:${id}`;
	return id;
}

function arxivIdFromDoi(doi: string | null): string | null {
	if (!doi) return null;
	const m = doi.match(/^10\.48550\/arXiv\.(.+)$/i);
	return m ? m[1] : null;
}

function parseWork(d: Record<string, unknown>): WorkSummary {
	const authorships = (d as { authorships?: Record<string, unknown>[] }).authorships ?? [];
	const doi = (d as { doi?: string | null }).doi ?? null;
	const id = openalexIdFromUrl((d as { id?: string }).id ?? "");
	return {
		id,
		title: (d as { title?: string }).title ?? "",
		authors: authorships.map((a) => ({
			name: (a as { author?: Record<string, unknown> }).author?.display_name as string ?? "",
			authorId: openalexIdFromUrl((a as { author?: Record<string, unknown> }).author?.id as string ?? ""),
		})),
		publicationYear: (d as { publication_year?: number | null }).publication_year ?? null,
		doi: doi ? doi.replace(/^https?:\/\/doi\.org\//, "") : null,
		citedByCount: (d as { cited_by_count?: number }).cited_by_count ?? 0,
		arxivId: arxivIdFromDoi(doi),
		openalexUrl: `https://openalex.org/${id}`,
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

async function fetchWorks(path: string, id: string, perPage = 25): Promise<WorkSummary[]> {
	const oaid = normalizeOpenAlexId(id);
	const res = await rateLimitedFetch(
		`${API_BASE}/works/${encodeURIComponent(oaid)}/${path}?per_page=${perPage}&select=id,title,authorships,publication_year,doi,cited_by_count`,
	);
	if (!res.ok) return [];
	const data = await res.json();
	return (data.results ?? []).map(parseWork);
}

export const fetchReferences = (id: string, perPage = 25) => fetchWorks("references", id, perPage);
export const fetchCitations = (id: string, perPage = 25) => fetchWorks("citations", id, perPage);
export const fetchRelatedWorks = (id: string, perPage = 25) => fetchWorks("related_works", id, perPage);
