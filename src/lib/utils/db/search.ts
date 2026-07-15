import { getCached, setCached, searchCache } from './cache';
import { rateLimitedFetch } from './rate-limit';
import { arxivId, getProp, API_BASE, ARXIV_API_BASE } from './helpers';
import { ensureChecker } from './checker';
import { warn } from '$lib/utils/logger';

export const SEARCH_FIELDS = "title,year,citationCount,authors,externalIds";

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

export function sanitiseYearRange(v: string): string {
	return /^\d{4}(-\d{4})?$/.test(v) ? v : "";
}

export function sanitiseFieldOfStudy(v: string): string {
	return /^[a-z][a-z -]*(,[a-z][a-z -]*)*$/i.test(v) ? v : "";
}

export function sanitiseMinCites(v: string): string {
	return /^\d{1,6}$/.test(v) ? v : "";
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

export function parseArxivTotal(doc: Document): number {
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
	const cached = getCached(searchCache, cacheKey) as { results: PaperResult[]; total: number } | undefined;
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
      if (errs.length) warn("[arxcheck] PaperResult violations:", errs);
    }
  }

	const result = { results, total };
	setCached(searchCache, cacheKey, result);
	return result;
}

export async function searchArxiv(
	query: string,
	opts?: {
		limit?: number;
		offset?: number;
		sortBy?: "relevance" | "submittedDate";
		sortOrder?: "ascending" | "descending";
	},
): Promise<{ results: PaperResult[]; total: number }> {
	const q = query.trim();
	if (!q || q.length < 2) return { results: [], total: 0 };

	const limit = opts?.limit ?? 30;
	const offset = opts?.offset ?? 0;
	const sortBy = opts?.sortBy ?? "relevance";
	const sortOrder = opts?.sortOrder ?? "descending";

	const cacheKey = JSON.stringify({ kind: "arxiv-search", q, limit, offset, sortBy, sortOrder });
	const cached = getCached(searchCache, cacheKey) as { results: PaperResult[]; total: number } | undefined;
	if (cached) return cached;

	const url = `${ARXIV_API_BASE}?search_query=${encodeURIComponent(`all:${q}`)}&start=${offset}&max_results=${limit}&sortBy=${sortBy}&sortOrder=${sortOrder}`;

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

export async function searchArxivCategory(
	cat: string,
	opts?: { offset?: number; limit?: number },
): Promise<{ results: PaperResult[]; total: number }> {
	const limit = opts?.limit ?? 30;
	const offset = opts?.offset ?? 0;

	const cacheKey = JSON.stringify({ kind: "arxiv", cat, limit, offset });
	const cached = getCached(searchCache, cacheKey) as { results: PaperResult[]; total: number } | undefined;
	if (cached) return cached;

	const url = `${ARXIV_API_BASE}?search_query=${encodeURIComponent(`cat:${cat}`)}&start=${offset}&max_results=${limit}&sortBy=submittedDate&sortOrder=descending`;

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

