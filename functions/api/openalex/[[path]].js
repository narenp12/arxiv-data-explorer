// Cloudflare Pages Function: same-origin proxy for the OpenAlex API.
// OpenAlex is a fully open scholarly index; it doesn't require an API key
// but appreciates a User-Agent header for fair-use prioritisation.
const FORWARD_HEADERS = new Set([
	"content-type", "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining",
	"x-ratelimit-reset", "cache-control", "expires",
]);

export async function onRequest({ request, params, env }) {
	const url = new URL(request.url);
	const path = Array.isArray(params.path) ? params.path.join("/") : (params.path ?? "");
	const upstream = new URL(`https://api.openalex.org/${path}`);
	upstream.search = url.search;

	const res = await fetch(upstream.toString(), {
		headers: {
			"User-Agent": "arxiv-data-explorer (Cloudflare Pages proxy)",
			Accept: "application/json",
		},
	});

	const responseHeaders = {};
	for (const [key, val] of res.headers) {
		if (FORWARD_HEADERS.has(key.toLowerCase())) {
			responseHeaders[key] = val;
		}
	}
	responseHeaders["Content-Type"] = res.headers.get("content-type") ?? "application/json";
	responseHeaders["Cache-Control"] = res.ok ? "public, max-age=3600" : "no-store";

	return new Response(res.body, {
		status: res.status,
		headers: responseHeaders,
	});
}
