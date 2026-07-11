import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getProp, searchPapers, searchArxivCategory, getPaperDetail, arxivId, authorList, clearSearchCache, sanitiseFieldOfStudy, sanitiseYearRange, sanitiseMinCites, getCached, setCached, parseArxivTotal, scoreCategory } from "./db/index.js";

vi.mock("../../../static/wasm/arxcheck/arxcheck.js", () => ({
	default: async () => {},
	validate_paper_result_json: () => [],
	validate_paper_detail_json: () => [],
	validate_profile_json: () => [],
}));

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

describe("scoreCategory", () => {
	const item = { label: "Machine Learning", id: "cs.LG" };

	it("returns 100 for exact match", () => {
		expect(scoreCategory(item, "Machine Learning")).toBe(100);
		expect(scoreCategory(item, "cs.lg")).toBe(100);
	});

	it("returns 80 when query is prefix", () => {
		expect(scoreCategory(item, "Machine")).toBe(80);
		expect(scoreCategory(item, "cs.")).toBe(80);
	});

	it("returns 60 when query starts a word", () => {
		expect(scoreCategory(item, "Learn")).toBe(60);
	});

	it("returns 40 for substring match", () => {
		expect(scoreCategory(item, "chine")).toBe(40);
	});

	it("returns 0 for no match", () => {
		expect(scoreCategory(item, "Physics")).toBe(0);
	});

	it("is case-insensitive", () => {
		expect(scoreCategory(item, "machine learning")).toBe(100);
		expect(scoreCategory(item, "CS.LG")).toBe(100);
		expect(scoreCategory(item, "LEARN")).toBe(60);
	});
});

describe("sanitiseFieldOfStudy", () => {
	it("accepts single-word fields", () => {
		expect(sanitiseFieldOfStudy("Physics")).toBe("Physics");
	});

	it("accepts multi-word fields with spaces", () => {
		expect(sanitiseFieldOfStudy("Computer Science")).toBe("Computer Science");
		expect(sanitiseFieldOfStudy("Materials Science")).toBe("Materials Science");
	});

	it("accepts comma-separated lists", () => {
		expect(sanitiseFieldOfStudy("Computer Science,Physics")).toBe("Computer Science,Physics");
	});

	it("rejects values with disallowed characters", () => {
		expect(sanitiseFieldOfStudy("Physics; DROP TABLE")).toBe("");
		expect(sanitiseFieldOfStudy("1234")).toBe("");
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
		clearSearchCache();
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
			clone() { return this; },
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
			clone() { return this; },
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
			clone() { return this; },
			json: async () => ({ data: [], total: 0 }),
		});

		await searchPapers("paged", { limit: 10, offset: 20 });
		const calledUrl = mockFetch.mock.calls[0][0];
		expect(calledUrl).toContain("limit=10");
		expect(calledUrl).toContain("offset=20");
	});

	it("deduplicates in-flight requests", async () => {
		let resolve: (v: unknown) => void;
		mockFetch.mockReturnValue(new Promise((r) => { resolve = r; }));
		const p1 = searchPapers("dedup");
		const p2 = searchPapers("dedup");
		resolve!({ ok: true, status: 200, clone() { return this; }, json: async () => ({ data: [], total: 0 }) });
		await Promise.all([p1, p2]);
		expect(mockFetch).toHaveBeenCalledTimes(1);
	});

	it("gives each concurrent caller an independent response body", async () => {
		// Model a real Response: the body can be read only once, and clone()
		// yields a fresh, independently-readable Response. Regresses the bug
		// where two racing callers shared one Response and the second .json()
		// threw "body stream already read".
		const makeResp = () => {
			let read = false;
			return {
				ok: true,
				status: 200,
				clone: () => makeResp(),
				json: async () => {
					if (read) throw new TypeError("body stream already read");
					read = true;
					return { data: [], total: 0 };
				},
			};
		};
		let resolve: (v: unknown) => void;
		mockFetch.mockReturnValue(new Promise((r) => { resolve = r; }));
		const p1 = searchPapers("concurrent-body");
		const p2 = searchPapers("concurrent-body");
		resolve!(makeResp());
		const [a, b] = await Promise.all([p1, p2]);
		expect(a).toEqual({ results: [], total: 0 });
		expect(b).toEqual({ results: [], total: 0 });
		expect(mockFetch).toHaveBeenCalledTimes(1);
	});

	it("re-fetches on 429 despite in-flight dedup", async () => {
		let call = 0;
		mockFetch.mockImplementation(async () => {
			call++;
			return {
				ok: call > 1,
				status: call > 1 ? 200 : 429,
				headers: new Map(),
				clone() { return this; },
				json: async () => ({ data: [], total: 0 }),
			};
		});
		const result = await searchPapers("retry-429");
		expect(result).toEqual({ results: [], total: 0 });
		expect(mockFetch).toHaveBeenCalledTimes(2);
	});
});

describe("getPaperDetail", () => {
	const mockFetch = vi.fn();
	const originalFetch = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
		clearSearchCache();
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	it("returns null for 404", async () => {
		mockFetch.mockResolvedValue({ ok: false, status: 404, clone() { return this; } });
		const result = await getPaperDetail("2301.00123");
		expect(result).toBeNull();
	});

	it("parses a paper detail response", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			clone() { return this; },
			json: async () => ({
				paperId: "abc",
				title: "Detail Test",
				authors: [{ name: "Alice" }],
				abstract: "An abstract",
				venue: "Test Venue",
				year: 2023,
				citationCount: 5,
				externalIds: { DOI: "10.1234/test" },
				publicationDate: "2023-06",
			}),
		});
		const result = await getPaperDetail("2301.99999");
		expect(result).not.toBeNull();
		expect(result!.title).toBe("Detail Test");
		expect(result!.doi).toBe("10.1234/test");
		expect(result!.citationCount).toBe(5);
	});
});

describe("searchArxivCategory", () => {
	const mockFetch = vi.fn();
	const originalFetch = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	it("parses arXiv XML response", async () => {
		const xml = `<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
  xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>42</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2301.00123</id>
    <title>  An arXiv Paper  </title>
    <author><name>Alice</name></author>
    <author><name>Bob</name></author>
    <published>2023-01-01T00:00:00Z</published>
  </entry>
</feed>`;
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			clone() { return this; },
			text: async () => xml,
		});
		const result = await searchArxivCategory("cs.LG", { limit: 10 });
		expect(result.total).toBe(42);
		expect(result.results).toHaveLength(1);
		expect(result.results[0].title).toBe("An arXiv Paper");
		expect(result.results[0].authors).toBe("Alice, Bob");
		expect(result.results[0].isArxiv).toBe(true);
	});
});

describe("sanitiseYearRange", () => {
	it("handles typical range", () => {
		expect(sanitiseYearRange("2020-2024")).toBe("2020-2024");
	});
	it("handles single year", () => {
		expect(sanitiseYearRange("2024")).toBe("2024");
	});
	it("handles empty string", () => {
		expect(sanitiseYearRange("")).toBe("");
	});
	it("handles undefined values", () => {
		expect(sanitiseYearRange(undefined as unknown as string)).toBe("");
	});
	it("handles reversed years", () => {
		expect(sanitiseYearRange("2024-2020")).toBe("2024-2020");
	});
	it("rejects invalid formats", () => {
		expect(sanitiseYearRange("abc")).toBe("");
		expect(sanitiseYearRange("20-24")).toBe("");
		expect(sanitiseYearRange("2024-")).toBe("");
		expect(sanitiseYearRange("-2024")).toBe("");
		expect(sanitiseYearRange("20241-2025")).toBe("");
	});
});

describe("sanitiseMinCites", () => {
	it("handles valid numbers", () => {
		expect(sanitiseMinCites("5")).toBe("5");
		expect(sanitiseMinCites("100")).toBe("100");
		expect(sanitiseMinCites("999999")).toBe("999999");
	});
	it("handles empty string", () => {
		expect(sanitiseMinCites("")).toBe("");
	});
	it("handles undefined", () => {
		expect(sanitiseMinCites(undefined as unknown as string)).toBe("");
	});
	it("rejects values over 6 digits", () => {
		expect(sanitiseMinCites("1000000")).toBe("");
	});
	it("rejects non-numeric input", () => {
		expect(sanitiseMinCites("abc")).toBe("");
		expect(sanitiseMinCites("-5")).toBe("");
	});
});

describe("getCached / setCached / clearSearchCache", () => {
	it("stores and retrieves values", () => {
		const cache = new Map<string, number>();
		setCached(cache, "key", 42);
		expect(getCached(cache, "key")).toBe(42);
	});

	it("returns undefined for missing key", () => {
		const cache = new Map<string, number>();
		expect(getCached(cache, "nope")).toBeUndefined();
	});

	it("promotes accessed key to end (LRU)", () => {
		const cache = new Map<string, number>();
		setCached(cache, "a", 1);
		setCached(cache, "b", 2);
		setCached(cache, "c", 3);
		getCached(cache, "a");
		expect([...cache.keys()]).toEqual(["b", "c", "a"]);
	});

	it("evicts oldest entry when exceeding limit", () => {
		const cache = new Map<number, string>();
		for (let i = 0; i < 100; i++) setCached(cache, i, `v${i}`);
		expect(cache.size).toBe(100);
		setCached(cache, 100, "overflow");
		expect(cache.size).toBe(100);
		expect(cache.has(0)).toBe(false);
		expect(cache.has(100)).toBe(true);
	});

	it("updates existing key in place", () => {
		const cache = new Map<string, string>();
		setCached(cache, "k", "old");
		setCached(cache, "k", "new");
		expect(cache.size).toBe(1);
		expect(getCached(cache, "k")).toBe("new");
	});

	it("clearSearchCache empties module-level caches", async () => {
		const mockFetch = vi.fn();
		const orig = globalThis.fetch;
		globalThis.fetch = mockFetch;
		mockFetch.mockResolvedValue({
			ok: true, status: 200,
			clone() { return this; },
			json: async () => ({ data: [], total: 0 }),
		});
		clearSearchCache();
		await searchPapers("ccc");
		clearSearchCache();
		await searchPapers("ccc");
		expect(mockFetch).toHaveBeenCalledTimes(2);
		globalThis.fetch = orig;
	});
});

describe("rateLimitedFetchOnce", () => {
	const mockFetch = vi.fn();
	const orig = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
		clearSearchCache();
	});

	afterEach(() => {
		globalThis.fetch = orig;
	});

	it("deduplicates concurrent requests for the same URL", async () => {
		let resolve!: (v: unknown) => void;
		mockFetch.mockReturnValue(new Promise((r) => { resolve = r; }));
		const p1 = searchPapers("dedup-rlfo");
		const p2 = searchPapers("dedup-rlfo");
		resolve!({ ok: true, status: 200, clone() { return this; }, json: async () => ({ data: [], total: 0 }) });
		await Promise.all([p1, p2]);
		expect(mockFetch).toHaveBeenCalledTimes(1);
	});

	it("handles sequential requests to different URLs", async () => {
		mockFetch.mockResolvedValue({
			ok: true, status: 200,
			clone() { return this; },
			json: async () => ({ data: [], total: 0 }),
		});
		await searchPapers("seq-a");
		await searchPapers("seq-b");
		expect(mockFetch).toHaveBeenCalledTimes(2);
	});
});

describe("buildSearchUrl", () => {
	const mockFetch = vi.fn();
	const orig = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
		clearSearchCache();
		mockFetch.mockResolvedValue({
			ok: true, status: 200,
			clone() { return this; },
			json: async () => ({ data: [], total: 0 }),
		});
	});

	afterEach(() => {
		globalThis.fetch = orig;
	});

	it("constructs URL with basic query", async () => {
		await searchPapers("test");
		const url = mockFetch.mock.calls[0][0] as string;
		expect(url).toContain("/api/s2/graph/v1/paper/search");
		expect(url).toContain("query=test");
	});

	it("includes limit and offset", async () => {
		await searchPapers("paged", { limit: 5, offset: 10 });
		const url = mockFetch.mock.calls[0][0] as string;
		expect(url).toContain("limit=5");
		expect(url).toContain("offset=10");
	});

	it("includes year range when valid", async () => {
		await searchPapers("years", { yearRange: "2020-2024" });
		const url = mockFetch.mock.calls[0][0] as string;
		expect(url).toContain("year=2020-2024");
	});

	it("omits year range when sanitised empty", async () => {
		await searchPapers("bad-year", { yearRange: "invalid" });
		const url = mockFetch.mock.calls[0][0] as string;
		expect(url).not.toContain("year=");
	});

	it("includes minCites when valid", async () => {
		await searchPapers("cited", { minCites: "50" });
		const url = mockFetch.mock.calls[0][0] as string;
		expect(url).toContain("minCitationCount=50");
	});

	it("handles all options together", async () => {
		await searchPapers("all-options", { yearRange: "2022", fieldOfStudy: "Physics", minCites: "10", limit: 50, offset: 100 });
		const url = mockFetch.mock.calls[0][0] as string;
		expect(url).toContain("query=all-options");
		expect(url).toContain("limit=50");
		expect(url).toContain("offset=100");
		expect(url).toContain("year=2022");
		expect(url).toContain("fieldsOfStudy=Physics");
		expect(url).toContain("minCitationCount=10");
	});
});

describe("parseSearchResponse", () => {
	const mockFetch = vi.fn();
	const orig = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
		clearSearchCache();
	});

	afterEach(() => {
		globalThis.fetch = orig;
	});

	it("parses a valid response with results", async () => {
		mockFetch.mockResolvedValue({
			ok: true, status: 200,
			clone() { return this; },
			json: async () => ({
				data: [
					{ paperId: "abc", title: "Paper A", year: 2024, citationCount: 5, authors: [{ name: "Alice" }], externalIds: { ArXiv: "2401.00123v1" } },
					{ paperId: "def", title: "Paper B", year: null, citationCount: 0, authors: [{ name: "Bob" }], externalIds: {} },
				],
				total: 2,
			}),
		});
		const result = await searchPapers("two-results");
		expect(result.results).toHaveLength(2);
		expect(result.total).toBe(2);
		expect(result.results[0].id).toBe("2401.00123");
		expect(result.results[0].isArxiv).toBe(true);
		expect(result.results[1].id).toBe("def");
		expect(result.results[1].isArxiv).toBe(false);
	});

	it("handles empty result set", async () => {
		mockFetch.mockResolvedValue({
			ok: true, status: 200,
			clone() { return this; },
			json: async () => ({ data: [], total: 0 }),
		});
		const result = await searchPapers("empty-results");
		expect(result.results).toEqual([]);
		expect(result.total).toBe(0);
	});

	it("handles missing fields gracefully", async () => {
		mockFetch.mockResolvedValue({
			ok: true, status: 200,
			clone() { return this; },
			json: async () => ({
				data: [
					{},
					{ paperId: "abc", title: "T", authors: [{ name: "A" }] },
				] as Record<string, unknown>[],
				total: 2,
			}),
		});
		const result = await searchPapers("sparse-data");
		expect(result.results).toHaveLength(2);
		expect(result.results[0].title).toBe("");
		expect(result.results[0].citationCount).toBe(0);
		expect(result.results[1].title).toBe("T");
	});

	it("handles authors with missing names", async () => {
		mockFetch.mockResolvedValue({
			ok: true, status: 200,
			clone() { return this; },
			json: async () => ({
				data: [
					{ paperId: "abc", title: "T", year: 2024, citationCount: 1, authors: [{ name: "Alice" }, {}], externalIds: {} },
				],
				total: 1,
			}),
		});
		const result = await searchPapers("authors");
		expect(result.results[0].authors).toBe("Alice, ");
	});
});

describe("parseArxivTotal", () => {
	it("extracts total results count from XML", () => {
		const xml = `<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>100</opensearch:totalResults>
</feed>`;
		const doc = new DOMParser().parseFromString(xml, "application/xml");
		expect(parseArxivTotal(doc)).toBe(100);
	});

	it("returns 0 when totalResults is missing", () => {
		const xml = `<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>Test</title></entry>
</feed>`;
		const doc = new DOMParser().parseFromString(xml, "application/xml");
		expect(parseArxivTotal(doc)).toBe(0);
	});

	it("returns 0 when totalResults is empty", () => {
		const xml = `<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults></opensearch:totalResults>
</feed>`;
		const doc = new DOMParser().parseFromString(xml, "application/xml");
		expect(parseArxivTotal(doc)).toBe(0);
	});
});
