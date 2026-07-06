// Cloudflare Pages Function: same-origin proxy for the arXiv export API.
// The export API stopped sending CORS headers, so browsers can't call it
// directly — this makes it same-origin instead.
const FORWARD_HEADERS = new Set([
	"content-type", "cache-control", "expires", "last-modified",
]);

export async function onRequest({ request }) {
	const url = new URL(request.url);
	const upstream = new URL("https://export.arxiv.org/api/query");
	upstream.search = url.search;

	const res = await fetch(upstream.toString(), {
		headers: { "User-Agent": "arxiv-data-explorer (Cloudflare Pages proxy)" },
		cf: { cacheTtl: 300, cacheEverything: true },
	});

	const responseHeaders = {};
	for (const [key, val] of res.headers) {
		if (FORWARD_HEADERS.has(key.toLowerCase())) {
			responseHeaders[key] = val;
		}
	}
	responseHeaders["Content-Type"] = res.headers.get("content-type") ?? "application/atom+xml";
	responseHeaders["Cache-Control"] = "public, max-age=300";

	return new Response(res.body, {
		status: res.status,
		headers: responseHeaders,
	});
}
