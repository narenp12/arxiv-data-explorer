// Both APIs are reached through same-origin proxies (Cloudflare Pages
// Functions in production, Vite dev-server proxy locally): the arXiv export
// API sends no CORS headers at all, and Semantic Scholar error responses
// (429s) lack them, which browsers surface as an opaque "Failed to fetch".
const API_BASE = "/api/s2/graph/v1";
const ARXIV_API_BASE = "/api/arxiv";

export interface PaperResult {
	id: string;
	title: string;
	authors: string;
	year: number | null;
	citationCount: number;
	isArxiv: boolean;
	s2Url: string;
}

export interface PaperDetail {
	id: string;
	title: string;
	authors: string;
	abstract: string;
	venue: string;
	doi: string | null;
	license: string | null;
	update_date: string | null;
	arxivUrl: string;
	s2Url: string;
	citationCount: number;
}

const SEARCH_FIELDS = "title,year,citationCount,authors,externalIds";
const DETAIL_FIELDS = "title,abstract,year,citationCount,authors,externalIds,publicationDate,venue,openAccessPdf";

const RATE_LIMIT_MS = 1100;
let lastRequest = 0;
let requestQueue: Promise<void> = Promise.resolve();

const CACHE_LIMIT = 100;
const searchCache = new Map<string, { results: PaperResult[]; total: number }>();
const detailCache = new Map<string, PaperDetail | null>();

function setCached<K, V>(cache: Map<K, V>, key: K, value: V) {
	cache.set(key, value);
	if (cache.size > CACHE_LIMIT) {
		const oldestKey = cache.keys().next().value as K;
		cache.delete(oldestKey);
	}
}

async function rateLimitedFetchOnce(url: string): Promise<Response> {
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

async function rateLimitedFetch(url: string): Promise<Response> {
	const retryDelaysMs = [2000, 5000];
	let res = await rateLimitedFetchOnce(url);
	for (const fallbackDelay of retryDelaysMs) {
		if (res.status !== 429) return res;
		const retryAfter = res.headers.get("Retry-After");
		const retrySeconds = retryAfter ? parseFloat(retryAfter) : NaN;
		const delayMs = Number.isFinite(retrySeconds) ? retrySeconds * 1000 : fallbackDelay;
		await new Promise((r) => setTimeout(r, delayMs));
		res = await rateLimitedFetchOnce(url);
	}
	if (res.status === 429) throw new Error("SEARCH_BUSY");
	return res;
}

function arxivId(d: Record<string, unknown>): string {
	const ext = (d as { externalIds?: Record<string, string> }).externalIds;
	if (ext?.ArXiv) return ext.ArXiv.replace(/v\d+$/, "");
	return "";
}

function authorList(d: Record<string, unknown>): string {
	const authors = (d as { authors?: { name: string }[] }).authors ?? [];
	return authors.map((a) => a.name).join(", ");
}

export async function searchPapers(
	query: string,
	options?: { yearRange?: string; limit?: number; offset?: number },
): Promise<{ results: PaperResult[]; total: number }> {
	const q = query.trim();
	if (!q || q.length < 2) return { results: [], total: 0 };

	const limit = options?.limit ?? 30;
	const offset = options?.offset ?? 0;

	const cacheKey = JSON.stringify({ kind: "s2", q, limit, offset, yearRange: options?.yearRange ?? null });
	const cached = searchCache.get(cacheKey);
	if (cached) return cached;

	let url = `${API_BASE}/paper/search?query=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}&fields=${SEARCH_FIELDS}`;
	if (options?.yearRange) url += `&year=${encodeURIComponent(options.yearRange)}`;

	const res = await rateLimitedFetch(url);
	if (!res.ok) throw new Error(`Semantic Scholar error: ${res.status}`);

	const data = await res.json();
	const results: PaperResult[] = (data.data ?? []).map((d: Record<string, unknown>) => {
		const ext = (d as { externalIds?: Record<string, string> }).externalIds;
		const paperId = (d as { paperId?: string }).paperId ?? "";
		return {
			id: arxivId(d) || paperId,
			title: (d as { title?: string }).title ?? "",
			authors: authorList(d),
			year: (d as { year?: number | null }).year ?? null,
			citationCount: (d as { citationCount?: number }).citationCount ?? 0,
			isArxiv: Boolean(ext?.ArXiv),
			s2Url: `https://www.semanticscholar.org/paper/${paperId}`,
		};
	});

	const result = { results, total: (data as { total?: number }).total ?? 0 };
	setCached(searchCache, cacheKey, result);
	return result;
}

export async function searchArxivCategory(
	cat: string,
	opts?: { offset?: number; limit?: number },
): Promise<{ results: PaperResult[]; total: number }> {
	const limit = opts?.limit ?? 30;
	const offset = opts?.offset ?? 0;

	const cacheKey = JSON.stringify({ kind: "arxiv", cat, limit, offset });
	const cached = searchCache.get(cacheKey);
	if (cached) return cached;

	const url = `${ARXIV_API_BASE}?search_query=${encodeURIComponent(`cat:${cat}`)}&start=${offset}&max_results=${limit}&sortBy=submittedDate&sortOrder=descending`;

	const res = await fetch(url);
	if (!res.ok) throw new Error(`arXiv error: ${res.status}`);

	const text = await res.text();
	const doc = new DOMParser().parseFromString(text, "application/xml");

	const entries = Array.from(doc.getElementsByTagName("entry"));
	const results: PaperResult[] = entries.map((entry) => {
		const idText = entry.getElementsByTagName("id")[0]?.textContent ?? "";
		const id = idText.replace(/^https?:\/\/arxiv\.org\/abs\//, "").replace(/v\d+$/, "");
		const titleText = entry.getElementsByTagName("title")[0]?.textContent ?? "";
		const title = titleText.replace(/\s+/g, " ").trim();
		const authors = Array.from(entry.getElementsByTagName("author"))
			.map((a) => a.getElementsByTagName("name")[0]?.textContent ?? "")
			.filter(Boolean)
			.join(", ");
		const published = entry.getElementsByTagName("published")[0]?.textContent ?? "";
		const year = published ? parseInt(published.slice(0, 4), 10) : null;

		return {
			id,
			title,
			authors,
			year: year && !Number.isNaN(year) ? year : null,
			citationCount: 0,
			isArxiv: true,
			s2Url: "",
		};
	});

	let total = 0;
	const totalResultsEl = Array.from(doc.getElementsByTagName("*")).find(
		(el) => el.localName === "totalResults",
	);
	if (totalResultsEl?.textContent) total = parseInt(totalResultsEl.textContent, 10) || 0;

	const result = { results, total };
	setCached(searchCache, cacheKey, result);
	return result;
}

export async function getPaperDetail(id: string): Promise<PaperDetail | null> {
	const cleanId = id.replace(/v\d+$/, "");

	if (detailCache.has(cleanId)) return detailCache.get(cleanId)!;

	const res = await rateLimitedFetch(
		`${API_BASE}/paper/arXiv:${encodeURIComponent(cleanId)}?fields=${DETAIL_FIELDS}`,
	);
	if (res.status === 404) {
		setCached(detailCache, cleanId, null);
		return null;
	}
	if (!res.ok) throw new Error(`Semantic Scholar error: ${res.status}`);

	const d = await res.json();
	const ext = (d as { externalIds?: Record<string, string> }).externalIds ?? {};
	const pdf = (d as { openAccessPdf?: { license?: string } }).openAccessPdf;

	const detail: PaperDetail = {
		id: cleanId,
		title: (d as { title?: string }).title ?? "",
		authors: authorList(d),
		abstract: (d as { abstract?: string }).abstract ?? "",
		venue: (d as { venue?: string }).venue ?? "",
		doi: (ext.DOI ?? "").replace("https://doi.org/", "") || null,
		license: pdf?.license ?? null,
		update_date: (d as { publicationDate?: string }).publicationDate ?? null,
		arxivUrl: `https://arxiv.org/abs/${cleanId}`,
		s2Url: `https://www.semanticscholar.org/paper/${(d as { paperId?: string }).paperId ?? ""}`,
		citationCount: (d as { citationCount?: number }).citationCount ?? 0,
	};

	setCached(detailCache, cleanId, detail);
	return detail;
}
