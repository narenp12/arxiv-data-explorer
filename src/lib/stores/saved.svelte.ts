import { browser } from "$app/environment";

export interface SavedPaper {
	id: string;
	title: string;
	authors: string;
	year: number | null;
	isArxiv: boolean;
	savedAt: number;
}

const STORAGE_KEY = "reading-list";

function load(): SavedPaper[] {
	if (!browser) return [];
	try {
		return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
	} catch {
		return [];
	}
}

class ReadingList {
	papers = $state<SavedPaper[]>(load());

	has(id: string): boolean {
		return this.papers.some((p) => p.id === id);
	}

	toggle(paper: Omit<SavedPaper, "savedAt">) {
		if (this.has(paper.id)) {
			this.papers = this.papers.filter((p) => p.id !== paper.id);
		} else {
			this.papers = [{ ...paper, savedAt: Date.now() }, ...this.papers];
		}
		if (browser) localStorage.setItem(STORAGE_KEY, JSON.stringify(this.papers));
	}

	remove(id: string) {
		this.papers = this.papers.filter((p) => p.id !== id);
		if (browser) localStorage.setItem(STORAGE_KEY, JSON.stringify(this.papers));
	}

	toBibtex(): string {
		return this.papers
			.map((p) => {
				const key = p.isArxiv ? `arxiv${p.id.replace(/[^a-zA-Z0-9]/g, "")}` : `s2${p.id.slice(0, 8)}`;
				const lines = [
					`@misc{${key},`,
					`  title = {${p.title}},`,
					`  author = {${p.authors.split(", ").join(" and ")}},`,
				];
				if (p.year) lines.push(`  year = {${p.year}},`);
				if (p.isArxiv) {
					lines.push(`  eprint = {${p.id}},`);
					lines.push(`  archivePrefix = {arXiv},`);
					lines.push(`  url = {https://arxiv.org/abs/${p.id}},`);
				}
				lines.push(`}`);
				return lines.join("\n");
			})
			.join("\n\n");
	}
}

export const readingList = new ReadingList();
