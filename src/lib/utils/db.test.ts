import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getProp, searchPapers, arxivId, authorList } from "./db.js";

describe("getProp", () => {
	it("returns the value for an existing key", () => {
		const obj = { name: "test", count: 42 };
		expect(getProp(obj, "name", "")).toBe("test");
		expect(getProp(obj, "count", 0)).toBe(42);
	});

	it("returns fallback for a missing key", () => {
		const obj = { name: "test" };
		expect(getProp(obj, "missing", "default")).toBe("default");
		expect(getProp(obj, "count", 0)).toBe(0);
	});

	it("returns fallback for undefined values", () => {
		const obj = { name: undefined };
		expect(getProp(obj, "name", "fallback")).toBe("fallback");
	});

	it("returns fallback when key is null (nullish coalescing)", () => {
		const obj = { year: null };
		expect(getProp<number | null>(obj, "year", 0)).toBe(0);
	});

	it("preserves false boolean values", () => {
		const obj = { active: false };
		expect(getProp(obj, "active", true)).toBe(false);
	});
});

describe("arxivId", () => {
	it("extracts ArXiv ID from externalIds", () => {
		const d = { externalIds: { ArXiv: "2301.12345v3" } };
		expect(arxivId(d)).toBe("2301.12345");
	});

	it("strips version suffix", () => {
		const d = { externalIds: { ArXiv: "2006.00123v1" } };
		expect(arxivId(d)).toBe("2006.00123");
	});

	it("returns empty string when no ArXiv ID", () => {
		const d = { externalIds: { DOI: "10.1234/test" } };
		expect(arxivId(d)).toBe("");
	});

	it("returns empty string when no externalIds", () => {
		const d = {};
		expect(arxivId(d)).toBe("");
	});
});

describe("authorList", () => {
	it("joins author names with comma", () => {
		const d = { authors: [{ name: "Alice" }, { name: "Bob" }, { name: "Charlie" }] };
		expect(authorList(d)).toBe("Alice, Bob, Charlie");
	});

	it("returns empty string for empty authors", () => {
		const d = { authors: [] };
		expect(authorList(d)).toBe("");
	});

	it("returns empty string when authors missing", () => {
		const d = {};
		expect(authorList(d)).toBe("");
	});
});

describe("searchPapers", () => {
	const mockFetch = vi.fn();
	const originalFetch = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	it("returns empty results for short queries", async () => {
		const result = await searchPapers("a");
		expect(result).toEqual({ results: [], total: 0 });
		expect(mockFetch).not.toHaveBeenCalled();
	});

	it("returns empty results for whitespace-only queries", async () => {
		const result = await searchPapers("   ");
		expect(result).toEqual({ results: [], total: 0 });
	});

	it("fetches from Semantic Scholar and parses response", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({
				data: [
					{
						paperId: "abc123",
						title: "Test Paper",
						year: 2023,
						citationCount: 10,
						authors: [{ name: "Alice" }],
						externalIds: { ArXiv: "2301.00123v1" },
					},
				],
				total: 1,
			}),
		});

		const result = await searchPapers("test query");
		expect(result.results).toHaveLength(1);
		expect(result.total).toBe(1);
		expect(result.results[0].title).toBe("Test Paper");
		expect(result.results[0].isArxiv).toBe(true);
		expect(result.results[0].citationCount).toBe(10);
	});

	it("caches identical queries", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ data: [], total: 0 }),
		});

		await searchPapers("cached query");
		await searchPapers("cached query");
		expect(mockFetch).toHaveBeenCalledTimes(1);
	});

	it("uses provided limit and offset", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ data: [], total: 0 }),
		});

		await searchPapers("paged", { limit: 10, offset: 20 });
		const calledUrl = mockFetch.mock.calls[0][0];
		expect(calledUrl).toContain("limit=10");
		expect(calledUrl).toContain("offset=20");
	});
});
