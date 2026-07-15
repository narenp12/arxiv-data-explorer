const RATE_LIMIT_MS = 1100;
let lastRequest = 0;
let requestQueue: Promise<void> = Promise.resolve();
const inFlight = new Map<string, Promise<Response>>();

export function resetRateLimitState() {
	lastRequest = 0;
	requestQueue = Promise.resolve();
	inFlight.clear();
}

export async function rateLimitedFetch(url: string): Promise<Response> {
	const retryDelaysMs = [2000, 5000];

	const once = async (): Promise<Response> => {
		const prev = requestQueue;
		let resolveNext: () => void;
		requestQueue = new Promise((r) => { resolveNext = r; });
		await prev;

		const inflight = inFlight.get(url);
		if (inflight) { resolveNext!(); return inflight.then((r) => r.clone()); }

		const now = Date.now();
		const wait = Math.max(0, RATE_LIMIT_MS - (now - lastRequest));
		if (wait > 0) await new Promise((r) => setTimeout(r, wait));
		lastRequest = Date.now();
		const promise = fetch(url);
		inFlight.set(url, promise);
		promise.finally(() => {
			resolveNext!();
			queueMicrotask(() => inFlight.delete(url));
		});
		return promise.then((r) => r.clone());
	};

	let res = await once();
	for (const fallbackDelay of retryDelaysMs) {
		if (res.status !== 429) return res;
		const retryAfter = res.headers.get("Retry-After");
		const retrySeconds = retryAfter ? parseFloat(retryAfter) : NaN;
		const delayMs = Number.isFinite(retrySeconds) ? retrySeconds * 1000 : fallbackDelay;
		await new Promise((r) => setTimeout(r, delayMs));
		res = await once();
	}
	if (res.status === 429) throw new Error("SEARCH_BUSY");
	return res;
}
