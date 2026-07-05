export interface NetworkStats {
	total_papers: number;
	single_author_papers: number;
	multi_author_papers: number;
	multi_category_papers: number;
	categories: number;
	authors: number;
}

export interface ConceptTag {
	id: string;
	name: string;
	score: number;
	level: number;
	wikidata: string;
	imageUrl: string | null;
	imageThumbnailUrl: string | null;
}

export interface AuthorProfile {
	id: string;
	name: string;
	orcid: string | null;
	worksCount: number;
	citedByCount: number;
	hIndex: number;
	i10Index: number;
	affiliations: { name: string; startYear: number | null; endYear: number | null }[];
	works: WorkSummary[];
	topCoAuthors: { name: string; authorId: string; count: number }[];
}

export interface WorkSummary {
	id: string;
	title: string;
	authors: { name: string; authorId: string }[];
	publicationYear: number | null;
	doi: string | null;
	citedByCount: number;
	arxivId: string | null;
	openalexUrl: string;
}
