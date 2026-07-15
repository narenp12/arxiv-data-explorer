import { getCached, setCached, detailCache } from './cache';
import { rateLimitedFetch } from './rate-limit';
import { authorList, getProp, API_BASE } from './helpers';
import { ensureChecker } from './checker';

export const DETAIL_FIELDS = "title,abstract,year,citationCount,authors,externalIds,publicationDate,venue,openAccessPdf";

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

export async function getPaperDetail(id: string): Promise<PaperDetail | null> {
	const cleanId = id.replace(/v\d+$/, "");

	const cachedDetail = getCached(detailCache, cleanId) as PaperDetail | null | undefined;
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
