export const API_BASE = "/api/s2/graph/v1";
export const ARXIV_API_BASE = "/api/arxiv";

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
