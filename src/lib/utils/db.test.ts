import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getProp, searchPapers, searchArxivCategory, getPaperDetail, arxivId, authorList, clearSearchCache, sanitiseFieldOfStudy } from "./db.js";

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
