// Both APIs are reached through same-origin proxies (Cloudflare Pages
// Functions in production, Vite dev-server proxy locally): the arXiv export
// API sends no CORS headers at all, and Semantic Scholar error responses
// (429s) lack them, which browsers surface as an opaque "Failed to fetch".

// Dev-mode validation: arxcheck WASM contract checker (optional)
type WasmAPI = { default: () => Promise<void>; validate_paper_result_json: (json: string) => string[]; validate_paper_detail_json: (json: string) => string[]; validate_profile_json: (json: string) => string[] };

let _check: WasmAPI | null = null;
let _checkReady = false;

function ensureChecker(): WasmAPI | null {
  if (!_checkReady) return null;
  return _check;
}

if (import.meta.env.DEV) {
  import("../../../static/wasm/arxcheck/arxcheck.js")
    .then((m) => m.default().then(() => { _check = m as unknown as WasmAPI; _checkReady = true; }))
    .catch(() => {});
}

const API_BASE = "/api/s2/graph/v1";
const ARXIV_API_BASE = "/api/arxiv";

export function sanitiseYearRange(v: string): string {
	return /^\d{4}(-\d{4})?$/.test(v) ? v : "";
}
export function sanitiseFieldOfStudy(v: string): string {
	// S2 field names can contain spaces ("Computer Science", "Materials Science"),
	// so allow internal spaces/hyphens — not just single lowercase words.
	return /^[a-z][a-z -]*(,[a-z][a-z -]*)*$/i.test(v) ? v : "";
}
export function sanitiseMinCites(v: string): string {
	return /^\d{1,6}$/.test(v) ? v : "";
}

export interface PaperResult {
	id: string;
	title: string;
	authors: string;
	authorsWithIds: { name: string; authorId?: string }[];
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
const inFlight = new Map<string, Promise<Response>>();

export function clearSearchCache() { searchCache.clear(); detailCache.clear(); inFlight.clear(); lastRequest = 0; requestQueue = Promise.resolve(); }

function getCached<K, V>(cache: Map<K, V>, key: K): V | undefined {
	const val = cache.get(key);
	if (val !== undefined) {
		cache.delete(key);
		cache.set(key, val);
	}
	return val;
}

function setCached<K, V>(cache: Map<K, V>, key: K, value: V) {
	cache.delete(key);
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

	// Each caller gets an independent clone: a Response body can only be read
	// once, so handing the shared in-flight Response to two racing callers would
	// make the second .json()/.text() throw "body stream already read". The
	// stored promise's original Response is never consumed — only cloned from.
	const inflight = inFlight.get(url);
	if (inflight) { resolveNext!(); return inflight.then((r) => r.clone()); }

	const now = Date.now();
	const wait = Math.max(0, RATE_LIMIT_MS - (now - lastRequest));
	if (wait > 0) await new Promise((r) => setTimeout(r, wait));
	lastRequest = Date.now();
	const promise = fetch(url);
	inFlight.set(url, promise);
	promise.finally(() => {
		resolveNext!();
		queueMicrotask(() => inFlight.delete(url));
	});
	return promise.then((r) => r.clone());
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

export function arxivId(d: Record<string, unknown>): string {
	const ext = (d as { externalIds?: Record<string, string> }).externalIds;
	if (ext?.ArXiv) return ext.ArXiv.replace(/v\d+$/, "");
	return "";
}

export function authorList(d: Record<string, unknown>): string {
	const authors = (d as { authors?: { name: string }[] }).authors ?? [];
	return authors.map((a) => a.name).join(", ");
}

export function getProp<T>(obj: Record<string, unknown>, key: string, fallback: T): T {
	const val = obj[key];
	return (val as T) ?? fallback;
}

function buildSearchUrl(
	query: string,
	limit: number,
	offset: number,
	options?: { yearRange?: string; fieldOfStudy?: string; minCites?: string },
): string {
	let url = `${API_BASE}/paper/search?query=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}&fields=${SEARCH_FIELDS}`;
	const yr = options?.yearRange ? sanitiseYearRange(options.yearRange) : "";
	const fo = options?.fieldOfStudy ? sanitiseFieldOfStudy(options.fieldOfStudy) : "";
	const mc = options?.minCites ? sanitiseMinCites(options.minCites) : "";
	if (yr) url += `&year=${encodeURIComponent(yr)}`;
	if (fo) url += `&fieldsOfStudy=${encodeURIComponent(fo)}`;
	if (mc) url += `&minCitationCount=${encodeURIComponent(mc)}`;
	return url;
}

function parseSearchResponse(data: Record<string, unknown>): PaperResult[] {
	const items = getProp<unknown[]>(data, "data", []) as Record<string, unknown>[];
	return items.map((d) => {
		const ext = getProp<Record<string, string> | null>(d, "externalIds", null);
		const paperId = getProp(d, "paperId", "");
		const authors = getProp<{ name: string; authorId?: string }[]>(d, "authors", []);
		return {
			id: arxivId(d) || paperId,
			title: getProp(d, "title", ""),
			authors: authors.map((a) => a.name).join(", "),
			authorsWithIds: authors,
			year: getProp<number | null>(d, "year", null),
			citationCount: getProp(d, "citationCount", 0),
			isArxiv: Boolean(ext?.ArXiv),
			s2Url: `https://www.semanticscholar.org/paper/${paperId}`,
		};
	});
}

function parseArxivResponse(doc: Document): PaperResult[] {
	return Array.from(doc.getElementsByTagName("entry")).map((entry) => {
		const idText = entry.getElementsByTagName("id")[0]?.textContent ?? "";
		const id = idText.replace(/^https?:\/\/arxiv\.org\/abs\//, "").replace(/v\d+$/, "");
		const titleText = entry.getElementsByTagName("title")[0]?.textContent ?? "";
		const title = titleText.replace(/\s+/g, " ").trim();
		const authorNames = Array.from(entry.getElementsByTagName("author"))
			.map((a) => a.getElementsByTagName("name")[0]?.textContent ?? "")
			.filter(Boolean);
		const published = entry.getElementsByTagName("published")[0]?.textContent ?? "";
		const year = published ? parseInt(published.slice(0, 4), 10) : null;

		return {
			id,
			title,
			authors: authorNames.join(", "),
			authorsWithIds: authorNames.map((name) => ({ name })),
			year: year && !Number.isNaN(year) ? year : null,
			citationCount: 0,
			isArxiv: true,
			s2Url: "",
		};
	});
}

function parseArxivTotal(doc: Document): number {
	const totalResultsEl = doc.getElementsByTagNameNS(
		"http://a9.com/-/spec/opensearch/1.1/",
		"totalResults",
	)[0];
	if (totalResultsEl?.textContent) return parseInt(totalResultsEl.textContent, 10) || 0;
	return 0;
}

export async function searchPapers(
	query: string,
	options?: { yearRange?: string; fieldOfStudy?: string; minCites?: string; limit?: number; offset?: number },
): Promise<{ results: PaperResult[]; total: number }> {
	const q = query.trim();
	if (!q || q.length < 2) return { results: [], total: 0 };

	const limit = options?.limit ?? 30;
	const offset = options?.offset ?? 0;
	const yearRange = options?.yearRange;

	const cacheKey = JSON.stringify({ kind: "s2", q, limit, offset, yearRange: yearRange ?? null, fieldOfStudy: options?.fieldOfStudy ?? null, minCites: options?.minCites ?? null });
	const cached = getCached(searchCache, cacheKey);
	if (cached) return cached;

	const url = buildSearchUrl(q, limit, offset, { yearRange, fieldOfStudy: options?.fieldOfStudy, minCites: options?.minCites });
	const res = await rateLimitedFetch(url);
	if (!res.ok) throw new Error(`Semantic Scholar error: ${res.status}`);

	const data = await res.json();
	const results = parseSearchResponse(data);
	const total = getProp<number>(data, "total", 0);

  if (import.meta.env.DEV) {
    const wasm = ensureChecker();
    if (wasm) {
      const errs = wasm.validate_paper_result_json(JSON.stringify({results}));
      if (errs.length) console.warn("[arxcheck] PaperResult violations:", errs);
    }
  }

	const result = { results, total };
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
	const cached = getCached(searchCache, cacheKey);
	if (cached) return cached;

	const url = `${ARXIV_API_BASE}?search_query=${encodeURIComponent(`cat:${cat}`)}&start=${offset}&max_results=${limit}&sortBy=submittedDate&sortOrder=descending`;

	// rateLimitedFetch throws the S2-flavoured "SEARCH_BUSY" on persistent 429;
	// remap it so the UI attributes the rate-limit to arXiv, not Semantic Scholar.
	let res: Response;
	try {
		res = await rateLimitedFetch(url);
	} catch (e) {
		if (e instanceof Error && e.message === "SEARCH_BUSY") throw new Error("ARXIV_BUSY");
		throw e;
	}
	if (!res.ok) throw new Error(`arXiv error: ${res.status}`);

	const text = await res.text();
	const doc = new DOMParser().parseFromString(text, "application/xml");

	const results = parseArxivResponse(doc);
	const total = parseArxivTotal(doc);

	const result = { results, total };
	setCached(searchCache, cacheKey, result);
	return result;
}

export async function getPaperDetail(id: string): Promise<PaperDetail | null> {
	const cleanId = id.replace(/v\d+$/, "");

	const cachedDetail = getCached(detailCache, cleanId);
	if (cachedDetail !== undefined) return cachedDetail;

	const res = await rateLimitedFetch(
		`${API_BASE}/paper/arXiv:${encodeURIComponent(cleanId)}?fields=${DETAIL_FIELDS}`,
	);
	if (res.status === 404) {
		setCached(detailCache, cleanId, null);
		return null;
	}
	if (!res.ok) throw new Error(`Semantic Scholar error: ${res.status}`);

	const data = await res.json();
	const ext = getProp<Record<string, string>>(data, "externalIds", {});
	const pdf = getProp<{ license?: string } | null>(data, "openAccessPdf", null);

	const detail: PaperDetail = {
		id: cleanId,
		title: getProp(data, "title", ""),
		authors: authorList(data),
		abstract: getProp(data, "abstract", ""),
		venue: getProp(data, "venue", ""),
		doi: (ext.DOI ?? "").replace("https://doi.org/", "") || null,
		license: pdf?.license ?? null,
		update_date: getProp<string | null>(data, "publicationDate", null),
		arxivUrl: `https://arxiv.org/abs/${cleanId}`,
		s2Url: `https://www.semanticscholar.org/paper/${getProp(data, "paperId", "")}`,
		citationCount: getProp(data, "citationCount", 0),
	};

  if (import.meta.env.DEV) {
    const wasm = ensureChecker();
    if (wasm) {
      const errs = wasm.validate_paper_detail_json(JSON.stringify(detail));
      if (errs.length) console.warn("[arxcheck] PaperDetail violations:", errs);
    }
  }

	setCached(detailCache, cleanId, detail);
	return detail;
}
