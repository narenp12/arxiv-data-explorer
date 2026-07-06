import { describe, it, expect, vi } from "vitest";

vi.mock("$app/environment", () => ({ browser: false }));

describe("toBibtex", () => {
	it("formats an arxiv paper", async () => {
		const { readingList } = await import("./saved.svelte");
		readingList.papers = [{
			id: "2301.00123",
			title: "Test Paper",
			authors: "Alice, Bob",
			year: 2023,
			isArxiv: true,
			savedAt: 100,
		}];
		const bib = readingList.toBibtex();
		expect(bib).toContain("@misc{arxiv230100123,");
		expect(bib).toContain("title = {Test Paper}");
		expect(bib).toContain("author = {Alice and Bob}");
		expect(bib).toContain("year = {2023}");
		expect(bib).toContain("eprint = {2301.00123}");
		expect(bib).toContain("archivePrefix = {arXiv}");
	});

	it("formats a non-arxiv paper", async () => {
		const { readingList } = await import("./saved.svelte");
		readingList.papers = [{
			id: "abc12345",
			title: "Non-arXiv",
			authors: "Charlie",
			year: null,
			isArxiv: false,
			savedAt: 200,
		}];
		const bib = readingList.toBibtex();
		expect(bib).toContain("@misc{s2abc12345,");
		expect(bib).not.toContain("eprint");
		expect(bib).not.toContain("year");
	});

	it("formats multiple papers", async () => {
		const { readingList } = await import("./saved.svelte");
		readingList.papers = [
			{ id: "A", title: "First", authors: "Alice", year: 2023, isArxiv: true, savedAt: 1 },
			{ id: "B", title: "Second", authors: "Bob", year: 2022, isArxiv: false, savedAt: 2 },
		];
		const bib = readingList.toBibtex();
		expect(bib).toContain("@misc{arxivA,");
		expect(bib).toContain("@misc{s2B,");
	});
});
