// Cloudflare Pages Function: same-origin proxy for the arXiv export API.
// The export API stopped sending CORS headers, so browsers can't call it
// directly — this makes it same-origin instead.
export async function onRequest({ request }) {
	const url = new URL(request.url);
	const upstream = new URL("https://export.arxiv.org/api/query");
	upstream.search = url.search;

	const res = await fetch(upstream.toString(), {
		headers: { "User-Agent": "arxiv-data-explorer (Cloudflare Pages proxy)" },
		cf: { cacheTtl: 300, cacheEverything: true },
	});

	return new Response(res.body, {
		status: res.status,
		headers: {
			"Content-Type": res.headers.get("Content-Type") ?? "application/atom+xml",
			"Cache-Control": "public, max-age=300",
		},
	});
}
