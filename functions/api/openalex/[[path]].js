// Cloudflare Pages Function: same-origin proxy for the OpenAlex API.
// OpenAlex is a fully open scholarly index; it doesn't require an API key
// but appreciates a User-Agent header for fair-use prioritisation.
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

	return new Response(res.body, {
		status: res.status,
		headers: {
			"Content-Type": res.headers.get("Content-Type") ?? "application/json",
			"Retry-After": res.headers.get("Retry-After") ?? "",
			"Cache-Control": res.ok ? "public, max-age=3600" : "no-store",
		},
	});
}
