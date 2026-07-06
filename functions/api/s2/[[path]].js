// Cloudflare Pages Function: same-origin proxy for the Semantic Scholar API.
// S2 error responses (429 etc.) lack CORS headers, which surfaces as an opaque
// "Failed to fetch" in browsers. Proxying makes errors readable and lets an
// optional S2_API_KEY env binding raise the rate limit without exposing the key.
const FORWARD_HEADERS = new Set([
	"content-type", "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining",
	"x-ratelimit-reset", "cache-control", "expires",
]);

export async function onRequest({ request, params, env }) {
	const url = new URL(request.url);
	const path = Array.isArray(params.path) ? params.path.join("/") : (params.path ?? "");
	const upstream = new URL(`https://api.semanticscholar.org/${path}`);
	upstream.search = url.search;

	const headers = { "User-Agent": "arxiv-data-explorer (Cloudflare Pages proxy)" };
	if (env.S2_API_KEY) headers["x-api-key"] = env.S2_API_KEY;

	const res = await fetch(upstream.toString(), { headers });

	const responseHeaders = {};
	for (const [key, val] of res.headers) {
		if (FORWARD_HEADERS.has(key.toLowerCase())) {
			responseHeaders[key] = val;
		}
	}
	responseHeaders["Content-Type"] = res.headers.get("content-type") ?? "application/json";
	responseHeaders["Cache-Control"] = res.ok ? "public, max-age=600" : "no-store";

	return new Response(res.body, {
		status: res.status,
		headers: responseHeaders,
	});
}
