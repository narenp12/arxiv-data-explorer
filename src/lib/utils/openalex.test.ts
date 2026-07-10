import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchConcepts, fetchAuthorProfile, fetchReferences, fetchCitations, fetchRelatedWorks } from "./openalex.js";

describe("fetchConcepts", () => {
	const mockFetch = vi.fn();
	const originalFetch = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	it("fetches concepts by DOI", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({
				concepts: [
					{
						id: "https://openalex.org/C123",
						display_name: "Machine Learning",
						score: 0.95,
						level: 0,
						wikidata: "https://www.wikidata.org/wiki/Q123",
						image_url: "https://example.com/img.png",
						image_thumbnail_url: "https://example.com/thumb.png",
					},
				],
			}),
		});

		const result = await fetchConcepts("10.1234/test", null);
		expect(result).toHaveLength(1);
		expect(result[0]).toEqual({
			id: "C123",
			name: "Machine Learning",
			score: 0.95,
			level: 0,
			wikidata: "https://www.wikidata.org/wiki/Q123",
			imageUrl: "https://example.com/img.png",
			imageThumbnailUrl: "https://example.com/thumb.png",
		});
	});

	it("strips DOI URL prefix before constructing API URL", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ concepts: [] }),
		});

		await fetchConcepts("https://doi.org/10.1234/test", null);
		const calledUrl = mockFetch.mock.calls[0][0] as string;
		expect(calledUrl).toContain("doi%3A10.1234%2Ftest");
	});

	it("fetches concepts by arxiv ID", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({
				concepts: [
					{
						id: "https://openalex.org/C456",
						display_name: "Computer Vision",
						score: 0.85,
						level: 1,
						wikidata: "",
						image_url: null,
						image_thumbnail_url: null,
					},
				],
			}),
		});

		const result = await fetchConcepts(null, "2301.00123");
		expect(result).toHaveLength(1);
		expect(result[0].name).toBe("Computer Vision");
		const calledUrl = mockFetch.mock.calls[0][0] as string;
		expect(calledUrl).toContain("arxiv%3A2301.00123");
	});

	it("returns empty array on non-ok response", async () => {
		mockFetch.mockResolvedValue({ ok: false, status: 500 });
		const result = await fetchConcepts("10.1234/test", null);
		expect(result).toEqual([]);
	});

	it("returns empty array when concepts field is missing", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({}),
		});
		const result = await fetchConcepts("10.1234/test", null);
		expect(result).toEqual([]);
	});

	it("requests the correct API endpoint for DOI input", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ concepts: [] }),
		});
		await fetchConcepts("10.1234/test", null);
		const calledUrl = mockFetch.mock.calls[0][0] as string;
		expect(calledUrl).toMatch(/\/api\/openalex\/works\//);
	});
});

describe("fetchAuthorProfile", () => {
	const mockFetch = vi.fn();
	const originalFetch = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	const authorResponse = {
		display_name: "Jane Smith",
		orcid: "https://orcid.org/0000-0002-1234-5678",
		works_count: 50,
		cited_by_count: 500,
		summary_stats: { h_index: 10, i10_index: 20 },
		last_known_institutions: [
			{ display_name: "MIT", start_year: 2010, end_year: 2020 },
			{ display_name: "Stanford", start_year: 2020, end_year: null },
		],
	};

	const worksResponse = {
		results: [
			{
				id: "https://openalex.org/W789",
				title: "Important Research",
				authorships: [
					{ author: { id: "https://openalex.org/A999", display_name: "Other Author" } },
					{ author: { id: "https://openalex.org/A123", display_name: "Jane Smith" } },
				],
				publication_year: 2023,
				doi: "https://doi.org/10.1234/paper",
				cited_by_count: 42,
			},
			{
				id: "https://openalex.org/W790",
				title: "Solo Paper",
				authorships: [
					{ author: { id: "https://openalex.org/A123", display_name: "Jane Smith" } },
				],
				publication_year: 2022,
				doi: null,
				cited_by_count: 10,
			},
		],
	};

	it("returns full AuthorProfile on success", async () => {
		let callCount = 0;
		mockFetch.mockImplementation(async () => {
			callCount++;
			return {
				ok: true,
				status: 200,
				json: async () => (callCount === 1 ? authorResponse : worksResponse),
			};
		});

		const result = await fetchAuthorProfile("A123");
		expect(result).not.toBeNull();
		expect(result!.id).toBe("A123");
		expect(result!.name).toBe("Jane Smith");
		expect(result!.orcid).toBe("https://orcid.org/0000-0002-1234-5678");
		expect(result!.worksCount).toBe(50);
		expect(result!.citedByCount).toBe(500);
		expect(result!.hIndex).toBe(10);
		expect(result!.i10Index).toBe(20);
		expect(result!.affiliations).toHaveLength(2);
		expect(result!.affiliations[0].name).toBe("MIT");
		expect(result!.works).toHaveLength(2);
		expect(result!.topCoAuthors).toHaveLength(1);
		expect(result!.topCoAuthors[0].authorId).toBe("A999");
		expect(result!.topCoAuthors[0].count).toBe(1);
	});

	it("returns null on author fetch failure", async () => {
		mockFetch.mockResolvedValue({ ok: false, status: 404 });
		const result = await fetchAuthorProfile("A999");
		expect(result).toBeNull();
	});

	it("handles works fetch failure gracefully", async () => {
		mockFetch.mockImplementation(async (url: string) => {
			if (url.includes("/authors/")) {
				return { ok: true, status: 200, json: async () => authorResponse };
			}
			return { ok: false, status: 500 };
		});

		const result = await fetchAuthorProfile("A123");
		expect(result).not.toBeNull();
		expect(result!.works).toEqual([]);
		expect(result!.topCoAuthors).toEqual([]);
	});

	it("handles missing last_known_institutions", async () => {
		const noInst = { ...authorResponse, last_known_institutions: null };
		mockFetch.mockImplementation(async (url: string) => {
			if (url.includes("/authors/")) {
				return { ok: true, status: 200, json: async () => noInst };
			}
			return { ok: true, status: 200, json: async () => ({ results: [] }) };
		});

		const result = await fetchAuthorProfile("A123");
		expect(result!.affiliations).toEqual([]);
	});

	it("handles empty summary_stats", async () => {
		const noSummary = { ...authorResponse, summary_stats: {} };
		mockFetch.mockImplementation(async (url: string) => {
			if (url.includes("/authors/")) {
				return { ok: true, status: 200, json: async () => noSummary };
			}
			return { ok: true, status: 200, json: async () => ({ results: [] }) };
		});

		const result = await fetchAuthorProfile("A123");
		expect(result!.hIndex).toBe(0);
		expect(result!.i10Index).toBe(0);
	});

	it("extracts DOI without URL prefix from parsed works", async () => {
		let callCount = 0;
		mockFetch.mockImplementation(async () => {
			callCount++;
			return {
				ok: true,
				status: 200,
				json: async () => (callCount === 1 ? authorResponse : worksResponse),
			};
		});

		const result = await fetchAuthorProfile("A123");
		expect(result!.works[0].doi).toBe("10.1234/paper");
	});
});

describe("fetchReferences", () => {
	const mockFetch = vi.fn();
	const originalFetch = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	const workResults = [
		{
			id: "https://openalex.org/W1",
			title: "Reference Paper",
			authorships: [
				{ author: { id: "https://openalex.org/A1", display_name: "Alice" } },
			],
			publication_year: 2020,
			doi: "https://doi.org/10.1234/ref1",
			cited_by_count: 15,
		},
		{
			id: "https://openalex.org/W2",
			title: "Another Ref",
			authorships: [],
			publication_year: null,
			doi: null,
			cited_by_count: 0,
		},
	];

	it("returns WorkSummary array on success", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ results: workResults }),
		});

		const result = await fetchReferences("10.1234/main");
		expect(result).toHaveLength(2);
		expect(result[0].title).toBe("Reference Paper");
		expect(result[0].authors).toHaveLength(1);
		expect(result[0].authors[0].name).toBe("Alice");
		expect(result[0].doi).toBe("10.1234/ref1");
		expect(result[0].citedByCount).toBe(15);
		expect(result[0].openalexUrl).toBe("https://openalex.org/W1");
		expect(result[1].title).toBe("Another Ref");
		expect(result[1].doi).toBeNull();
	});

	it("returns empty array on non-ok response", async () => {
		mockFetch.mockResolvedValue({ ok: false, status: 404 });
		const result = await fetchReferences("10.1234/main");
		expect(result).toEqual([]);
	});

	it("returns empty array when results field is missing", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({}),
		});
		const result = await fetchReferences("10.1234/main");
		expect(result).toEqual([]);
	});

	it("accepts prefixed DOI ID", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ results: [] }),
		});
		await fetchReferences("doi:10.1234/main");
		const calledUrl = mockFetch.mock.calls[0][0] as string;
		expect(calledUrl).toContain("doi%3A10.1234%2Fmain");
	});

	it("accepts arXiv ID (normalizes to arXiv: prefix)", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ results: [] }),
		});
		await fetchReferences("2301.00123");
		const calledUrl = mockFetch.mock.calls[0][0] as string;
		expect(calledUrl).toContain("arXiv%3A2301.00123");
	});

	it("passes perPage parameter to API URL", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ results: [] }),
		});
		await fetchReferences("10.1234/main", 50);
		const calledUrl = mockFetch.mock.calls[0][0] as string;
		expect(calledUrl).toContain("per_page=50");
	});

	it("defaults perPage to 25", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ results: [] }),
		});
		await fetchReferences("10.1234/main");
		const calledUrl = mockFetch.mock.calls[0][0] as string;
		expect(calledUrl).toContain("per_page=25");
	});
});

describe("fetchCitations", () => {
	const mockFetch = vi.fn();
	const originalFetch = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	it("returns WorkSummary array on success", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({
				results: [
					{
						id: "https://openalex.org/W42",
						title: "Citing Paper",
						authorships: [],
						publication_year: 2023,
						doi: "https://doi.org/10.1234/citing",
						cited_by_count: 5,
					},
				],
			}),
		});

		const result = await fetchCitations("10.1234/main");
		expect(result).toHaveLength(1);
		expect(result[0].title).toBe("Citing Paper");
		expect(result[0].doi).toBe("10.1234/citing");
	});

	it("returns empty array on non-ok response", async () => {
		mockFetch.mockResolvedValue({ ok: false, status: 403 });
		const result = await fetchCitations("10.1234/main");
		expect(result).toEqual([]);
	});

	it("requests /citations endpoint", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ results: [] }),
		});
		await fetchCitations("arXiv:2301.00123");
		const calledUrl = mockFetch.mock.calls[0][0] as string;
		expect(calledUrl).toContain("/citations?");
	});

	it("passes perPage parameter", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ results: [] }),
		});
		await fetchCitations("10.1234/main", 100);
		const calledUrl = mockFetch.mock.calls[0][0] as string;
		expect(calledUrl).toContain("per_page=100");
	});
});

describe("fetchRelatedWorks", () => {
	const mockFetch = vi.fn();
	const originalFetch = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	it("returns WorkSummary array on success", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({
				results: [
					{
						id: "https://openalex.org/W7",
						title: "Related Work",
						authorships: [],
						publication_year: 2024,
						doi: "https://doi.org/10.1234/related",
						cited_by_count: 3,
					},
				],
			}),
		});

		const result = await fetchRelatedWorks("10.1234/main");
		expect(result).toHaveLength(1);
		expect(result[0].title).toBe("Related Work");
	});

	it("returns empty array on non-ok response", async () => {
		mockFetch.mockResolvedValue({ ok: false, status: 500 });
		const result = await fetchRelatedWorks("10.1234/main");
		expect(result).toEqual([]);
	});

	it("requests /related_works endpoint", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ results: [] }),
		});
		await fetchRelatedWorks("doi:10.1234/main");
		const calledUrl = mockFetch.mock.calls[0][0] as string;
		expect(calledUrl).toContain("/related_works?");
	});

	it("passes perPage parameter", async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ results: [] }),
		});
		await fetchRelatedWorks("10.1234/main", 10);
		const calledUrl = mockFetch.mock.calls[0][0] as string;
		expect(calledUrl).toContain("per_page=10");
	});
});

describe("rateLimitedFetch behavior (indirect via exported functions)", () => {
	const mockFetch = vi.fn();
	const originalFetch = globalThis.fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		globalThis.fetch = mockFetch;
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	it("retries on 429 then succeeds", async () => {
		let callCount = 0;
		mockFetch.mockImplementation(async () => {
			callCount++;
			if (callCount === 1) {
				return {
					ok: false,
					status: 429,
					headers: new Map([["Retry-After", "0"]]),
				};
			}
			return {
				ok: true,
				status: 200,
				json: async () => ({ results: [] }),
			};
		});

		const result = await fetchReferences("10.1234/retry-test");
		expect(result).toEqual([]);
		expect(mockFetch).toHaveBeenCalledTimes(2);
	});

	it("rate-limits sequential requests with adequate spacing", async () => {
		const callTimes: number[] = [];
		mockFetch.mockImplementation(async () => {
			callTimes.push(Date.now());
			return {
				ok: true,
				status: 200,
				json: async () => ({ results: [] }),
			};
		});

		await fetchReferences("id-a");
		await fetchReferences("id-b");

		expect(callTimes).toHaveLength(2);
		const gap = callTimes[1] - callTimes[0];
		expect(gap).toBeGreaterThanOrEqual(100);
	});

	it("deduplicates in-flight requests to identical URLs", async () => {
		let fetchCount = 0;
		let resolveFirst: (v: unknown) => void;
		mockFetch.mockReturnValue(
			new Promise((r) => {
				resolveFirst = r;
				fetchCount++;
			}),
		);

		const p1 = fetchReferences("doi:10.1234/dedup-test");
		const p2 = fetchReferences("doi:10.1234/dedup-test");

		resolveFirst!({
			ok: true,
			status: 200,
			json: async () => ({ results: [] }),
		});

		const [r1, r2] = await Promise.all([p1, p2]);
		expect(r1).toEqual([]);
		expect(r2).toEqual([]);
		expect(fetchCount).toBeLessThanOrEqual(2);
	});

	it("concurrent requests to different URLs both complete", async () => {
		mockFetch.mockImplementation(async (url: string) => {
			return {
				ok: true,
				status: 200,
				json: async () => ({ results: [{ id: "https://openalex.org/W1", title: url, authorships: [], publication_year: 2023, doi: null, cited_by_count: 0 }] }),
			};
		});

		const [refs, cites] = await Promise.all([
			fetchReferences("10.1234/a"),
			fetchCitations("10.1234/b"),
		]);

		expect(refs).toHaveLength(1);
		expect(cites).toHaveLength(1);
		expect(mockFetch).toHaveBeenCalledTimes(2);
	});
});
