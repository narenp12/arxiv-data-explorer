import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../../../static/wasm/arxwasm/arxwasm.js", () => ({
	default: vi.fn(async () => {}),
	init: vi.fn(),
	search: vi.fn(),
	search_stats: vi.fn(() => ({ total_authors: 0, with_rankings: 0 })),
}));

import { loadAuthorSearch, getInitError, searchAuthors, getStats } from "./wasm-search.js";
import * as arxwasm from "../../../static/wasm/arxwasm/arxwasm.js";

function okResponse(text: string) {
	return {
		ok: true,
		status: 200,
		text: async () => text,
		clone() { return this; },
	};
}

const arxwasmDefault = vi.mocked(arxwasm.default);
const arxwasmInit = vi.mocked(arxwasm.init);
const arxwasmSearch = vi.mocked(arxwasm.search);
const arxwasmSearchStats = vi.mocked(arxwasm.search_stats);

describe("wasm-search", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	describe("default state", () => {
		it("getInitError returns null before any init attempt", () => {
			expect(getInitError()).toBeNull();
		});

		it("searchAuthors returns empty array when WASM is not loaded", () => {
			expect(searchAuthors("test query")).toEqual([]);
		});

		it("getStats returns zeroes when WASM is not loaded", () => {
			expect(getStats()).toEqual({ totalAuthors: 0, withRankings: 0 });
		});
	});

	describe("loadAuthorSearch", () => {
		let originalFetch: typeof globalThis.fetch;

		beforeEach(() => {
			originalFetch = globalThis.fetch;
			globalThis.fetch = vi.fn(() => Promise.resolve(okResponse("data")));
		});

		afterEach(() => {
			globalThis.fetch = originalFetch;
		});

		it("sets initError and re-throws when WASM init fails", async () => {
			arxwasmDefault.mockRejectedValueOnce(new Error("WASM init failed"));
			await expect(loadAuthorSearch()).rejects.toThrow("WASM init failed");
			expect(getInitError()).toBe("Error: WASM init failed");
		});

		it("fetches 32 shard/ranking URLs and initialises WASM", async () => {
			await loadAuthorSearch();

			expect(arxwasmDefault).toHaveBeenCalledOnce();
			expect(arxwasmInit).toHaveBeenCalledOnce();
			expect(arxwasmInit).toHaveBeenCalledWith(
				expect.stringContaining("data"),
				"data",
			);
			expect(globalThis.fetch).toHaveBeenCalledTimes(32);
		});

		it("is idempotent when already loaded", async () => {
			await loadAuthorSearch();
			vi.clearAllMocks();

			await loadAuthorSearch();
			expect(arxwasmDefault).not.toHaveBeenCalled();
			expect(arxwasmInit).not.toHaveBeenCalled();
		});
	});

	describe("searchAuthors after load", () => {
		let originalFetch: typeof globalThis.fetch;

		beforeEach(async () => {
			originalFetch = globalThis.fetch;
			globalThis.fetch = vi.fn(() => Promise.resolve(okResponse("data")));
			await loadAuthorSearch();
		});

		afterEach(() => {
			globalThis.fetch = originalFetch;
		});

		it("passes query and max to wasmSearch", () => {
			arxwasmSearch.mockReturnValue([]);
			searchAuthors("test query", 10);
			expect(arxwasmSearch).toHaveBeenCalledWith("test query", 10);
		});

		it("uses default max of 20", () => {
			arxwasmSearch.mockReturnValue([]);
			searchAuthors("query");
			expect(arxwasmSearch).toHaveBeenCalledWith("query", 20);
		});

		it("returns wasmSearch results as-is", () => {
			const wasmResult = [
				{ name: "Alice", weight: 0.9, coauthors: 5, rank: 1 },
				{ name: "Bob", weight: 0.5, coauthors: 3, rank: null },
			];
			arxwasmSearch.mockReturnValue(wasmResult);
			expect(searchAuthors("A")).toEqual(wasmResult);
		});
	});

	describe("getStats after load", () => {
		let originalFetch: typeof globalThis.fetch;

		beforeEach(async () => {
			originalFetch = globalThis.fetch;
			globalThis.fetch = vi.fn(() => Promise.resolve(okResponse("data")));
			await loadAuthorSearch();
		});

		afterEach(() => {
			globalThis.fetch = originalFetch;
		});

		it("calls wasmSearchStats and maps keys to camelCase", () => {
			arxwasmSearchStats.mockReturnValue({ total_authors: 100, with_rankings: 75 });
			expect(getStats()).toEqual({ totalAuthors: 100, withRankings: 75 });
			expect(arxwasmSearchStats).toHaveBeenCalledOnce();
		});
	});
});
