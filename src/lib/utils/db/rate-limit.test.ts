import { describe, it, expect, vi, beforeEach } from "vitest";

beforeEach(async () => {
	vi.restoreAllMocks();
	const { resetRateLimitState } = await import("./rate-limit");
	resetRateLimitState();
});

describe("rateLimitedFetch", () => {
	it("returns response on success", async () => {
		const mockResponse = new Response(JSON.stringify({ ok: true }), { status: 200 });
		globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

		const { rateLimitedFetch } = await import("./rate-limit");
		const res = await rateLimitedFetch("https://example.com/test");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.ok).toBe(true);
	});

	it("retries on 429 then succeeds", async () => {
		let attempts = 0;
		globalThis.fetch = vi.fn().mockImplementation(async () => {
			attempts++;
			if (attempts === 1) {
				return new Response(null, { status: 429, headers: { "Retry-After": "0" } });
			}
			return new Response(JSON.stringify({ ok: true }), { status: 200 });
		});

		const { rateLimitedFetch } = await import("./rate-limit");
		const res = await rateLimitedFetch("https://example.com/retry-test");
		expect(res.status).toBe(200);
		expect(attempts).toBe(2);
	});

	it("throws SEARCH_BUSY after exhausting retries", async () => {
		globalThis.fetch = vi.fn().mockResolvedValue(
			new Response(null, { status: 429, headers: { "Retry-After": "0" } })
		);

		const { rateLimitedFetch } = await import("./rate-limit");
		await expect(rateLimitedFetch("https://example.com/busy")).rejects.toThrow("SEARCH_BUSY");
	});
});
