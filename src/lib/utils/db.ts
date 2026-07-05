import initSqlJs from "sql.js";
import { base } from "$app/paths";

const DB_RANGES = [
	"1991-1999", "2000-2009",
	"2010-2014", "2015-2019",
	"2020-2026",
] as const;

export type YearRange = (typeof DB_RANGES)[number];

let SQL: any = null;
const dbCache = new Map<YearRange, any>();
let sqlInit: Promise<void> | null = null;

async function ensureSql(): Promise<void> {
	if (SQL) return;
	if (sqlInit) return sqlInit;
	sqlInit = (async () => {
		SQL = await initSqlJs();
	})();
	return sqlInit;
}

export async function loadDb(range: YearRange): Promise<any> {
	if (dbCache.has(range)) return dbCache.get(range);
	await ensureSql();
	const resp = await fetch(`${base}/data/search_${range}.db`);
	const buf = await resp.arrayBuffer();
	const db = new SQL.Database(new Uint8Array(buf));
	dbCache.set(range, db);
	return db;
}

export function loadedRanges(): YearRange[] {
	return [...dbCache.keys()];
}

export function dropDb(range: YearRange): void {
	const db = dbCache.get(range);
	if (db) db.close();
	dbCache.delete(range);
}

export interface PaperResult {
	id: string;
	title: string;
	authors: string;
}

function sanitizeQuery(query: string): string {
	return query
		.trim()
		.replace(/[^a-zA-Z0-9\s]/g, "")
		.split(/\s+/)
		.filter(Boolean)
		.join(" AND ");
}

function searchOneDb(
	db: any,
	q: string,
	limit: number,
	offset: number,
): { results: PaperResult[]; total: number } {
	const countStmt = db.prepare(
		"SELECT COUNT(*) as cnt FROM papers_fts WHERE papers_fts MATCH ?",
	);
	countStmt.bind([q]);
	let total = 0;
	if (countStmt.step()) {
		total = countStmt.getAsObject().cnt;
	}
	countStmt.free();

	const stmt = db.prepare(
		"SELECT rowid, id, title, authors FROM papers_fts WHERE papers_fts MATCH ? ORDER BY rank LIMIT ? OFFSET ?",
	);
	stmt.bind([q, limit, offset]);

	const results: PaperResult[] = [];
	while (stmt.step()) {
		const row = stmt.getAsObject() as any;
		results.push({ id: row.id, title: row.title, authors: row.authors });
	}
	stmt.free();

	return { results, total };
}

export function searchPapers(
	query: string,
	ranges?: YearRange[],
	limit = 30,
	offset = 0,
): { results: PaperResult[]; total: number } {
	const q = sanitizeQuery(query);
	if (!q) return { results: [], total: 0 };

	const targets = ranges ?? [...dbCache.keys()];
	if (targets.length === 0) return { results: [], total: 0 };

	const allResults: PaperResult[] = [];
	let total = 0;

	for (const range of targets) {
		const db = dbCache.get(range);
		if (!db) continue;
		const res = searchOneDb(db, q, limit, offset);
		total += res.total;
		allResults.push(...res.results);
	}

	return { results: allResults.slice(0, limit), total };
}
