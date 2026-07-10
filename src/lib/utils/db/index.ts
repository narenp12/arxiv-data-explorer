type WasmAPI = { default: () => Promise<void>; validate_paper_result_json: (json: string) => string[]; validate_paper_detail_json: (json: string) => string[]; validate_profile_json: (json: string) => string[] };

let _check: WasmAPI | null = null;
let _checkReady = false;

export function ensureChecker(): WasmAPI | null {
	if (!_checkReady) return null;
	return _check;
}

if (import.meta.env.DEV) {
	import("../../../../static/wasm/arxcheck/arxcheck.js")
		.then((m) => m.default().then(() => { _check = m as unknown as WasmAPI; _checkReady = true; }))
		.catch(() => {});
}

export type { WasmAPI };

export { getCached, setCached, clearSearchCache, CACHE_LIMIT } from './cache';
export { rateLimitedFetch, RATE_LIMIT_MS } from './rate-limit';
export { arxivId, authorList, getProp, API_BASE, ARXIV_API_BASE } from './helpers';
export { searchPapers, searchArxivCategory, parseArxivTotal, sanitiseYearRange, sanitiseFieldOfStudy, sanitiseMinCites, SEARCH_FIELDS } from './search';
export { getPaperDetail, DETAIL_FIELDS } from './detail';
export type { PaperResult } from './search';
export type { PaperDetail } from './detail';
