const API_BASE = "https://api.semanticscholar.org/graph/v1";

export interface PaperResult {
	id: string;
	title: string;
	authors: string;
	year: number | null;
	citationCount: number;
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

	const res = await rateLimitedFetch(
		`${API_BASE}/paper/search?query=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}&fields=${SEARCH_FIELDS}`,
	);
	if (!res.ok) throw new Error(`Semantic Scholar error: ${res.status}`);

	const data = await res.json();
	const results: PaperResult[] = (data.data ?? []).map((d: Record<string, unknown>) => ({
		id: arxivId(d) || ((d as { paperId?: string }).paperId ?? ""),
		title: (d as { title?: string }).title ?? "",
		authors: authorList(d),
		year: (d as { year?: number | null }).year ?? null,
		citationCount: (d as { citationCount?: number }).citationCount ?? 0,
	}));

	return { results, total: (data as { total?: number }).total ?? 0 };
}

export async function getPaperDetail(id: string): Promise<PaperDetail | null> {
	const cleanId = id.replace(/v\d+$/, "");
	const res = await rateLimitedFetch(
		`${API_BASE}/paper/arXiv:${encodeURIComponent(cleanId)}?fields=${DETAIL_FIELDS}`,
	);
	if (res.status === 404) return null;
	if (!res.ok) throw new Error(`Semantic Scholar error: ${res.status}`);

	const d = await res.json();
	const ext = (d as { externalIds?: Record<string, string> }).externalIds ?? {};
	const pdf = (d as { openAccessPdf?: { license?: string } }).openAccessPdf;

	return {
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
}
