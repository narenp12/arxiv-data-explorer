// Default import: the package is UMD/CommonJS, named imports break Vite SSR interop
import pkg from "sql.js-httpvfs";
import type { WorkerHttpvfs } from "sql.js-httpvfs";
const { createDbWorker } = pkg;
import { base } from "$app/paths";
import workerUrl from "sql.js-httpvfs/dist/sqlite.worker.js?url";
import wasmUrl from "sql.js-httpvfs/dist/sql-wasm.wasm?url";

// Where the .db files live. Set VITE_DATA_BASE_URL to the R2 public bucket URL
// in production; falls back to local /data for dev.
const DATA_BASE: string =
	import.meta.env.VITE_DATA_BASE_URL || `${base}/data`;

// Must match SQLITE_PAGE_SIZE in scripts/build_data.py
const REQUEST_CHUNK_SIZE = 4096;

const DB_RANGES = [
	"1991-1999", "2000-2009",
	"2010-2014", "2015-2019",
	"2020-2026",
] as const;

export type YearRange = (typeof DB_RANGES)[number];

const searchWorkers = new Map<YearRange, WorkerHttpvfs>();
const searchPending = new Map<YearRange, Promise<WorkerHttpvfs>>();
const detailWorkers = new Map<YearRange, WorkerHttpvfs>();
const detailPending = new Map<YearRange, Promise<WorkerHttpvfs>>();

function createWorker(url: string): Promise<WorkerHttpvfs> {
	return createDbWorker(
		[{
			from: "inline",
			config: {
				serverMode: "full",
				url,
				requestChunkSize: REQUEST_CHUNK_SIZE,
			},
		}],
		workerUrl,
		wasmUrl,
	);
}

function loadWorker(
	range: YearRange,
	prefix: "search" | "detail",
	cache: Map<YearRange, WorkerHttpvfs>,
	pending: Map<YearRange, Promise<WorkerHttpvfs>>,
): Promise<WorkerHttpvfs> {
	const cached = cache.get(range);
	if (cached) return Promise.resolve(cached);
	const inflight = pending.get(range);
	if (inflight) return inflight;

	const p = createWorker(`${DATA_BASE}/${prefix}_${range}.db`)
		.then((worker) => {
			cache.set(range, worker);
			pending.delete(range);
			return worker;
		})
		.catch((e) => {
			pending.delete(range);
			throw e;
		});
	pending.set(range, p);
	return p;
}

export function loadDb(range: YearRange): Promise<WorkerHttpvfs> {
	return loadWorker(range, "search", searchWorkers, searchPending);
}

export function loadedRanges(): YearRange[] {
	return [...searchWorkers.keys()];
}

export function dropDb(range: YearRange): void {
	const worker = searchWorkers.get(range);
	if (worker) dbOf(worker).close();
	searchWorkers.delete(range);
}

export interface PaperResult {
	id: string;
	title: string;
	authors: string;
}

export interface PaperDetail {
	id: string;
	abstract: string;
	categories: string;
	doi: string | null;
	license: string | null;
	update_date: string | null;
}

interface ExecResult {
	columns: string[];
	values: unknown[][];
}

// Comlink's Remote<LazyHttpDatabase> type loses the sql.js Database methods
// (exec, close); this facade restores the ones we use.
interface RemoteDb {
	exec(sql: string, params?: unknown[]): Promise<ExecResult[]>;
	close(): Promise<void>;
}

function dbOf(worker: WorkerHttpvfs): RemoteDb {
	return worker.db as unknown as RemoteDb;
}

// The Comlink-proxied query(sql, ...params) drops variadic params; exec with a
// param array binds correctly, so all queries go through exec + this mapper.
function toObjects<T>(res: ExecResult[]): T[] {
	if (!res[0]) return [];
	const { columns, values } = res[0];
	return values.map(
		(row) => Object.fromEntries(columns.map((c, i) => [c, row[i]])),
	) as T[];
}

function sanitizeQuery(query: string): string {
	return query
		.trim()
		.replace(/[^a-zA-Z0-9\s]/g, "")
		.split(/\s+/)
		.filter(Boolean)
		.join(" AND ");
}

export async function searchPapers(
	query: string,
	ranges?: YearRange[],
	limit = 30,
	offset = 0,
): Promise<{ results: PaperResult[]; total: number }> {
	const q = sanitizeQuery(query);
	if (!q) return { results: [], total: 0 };

	const targets = ranges ?? [...searchWorkers.keys()];
	if (targets.length === 0) return { results: [], total: 0 };

	let total = 0;
	const allRows: Array<PaperResult & { rank: number }> = [];

	await Promise.all(targets.map(async (range) => {
		const worker = searchWorkers.get(range);
		if (!worker) return;

		const countRows = toObjects<{ cnt: number }>(await dbOf(worker).exec(
			"SELECT COUNT(*) AS cnt FROM papers_fts WHERE papers_fts MATCH ?",
			[q],
		));
		total += countRows[0]?.cnt ?? 0;

		// Fetch enough rows from each range to fill the requested page after
		// merging: ranks are only comparable after a global sort.
		const rows = toObjects<PaperResult & { rank: number }>(await dbOf(worker).exec(
			"SELECT id, title, authors, rank FROM papers_fts WHERE papers_fts MATCH ? ORDER BY rank LIMIT ?",
			[q, offset + limit],
		));
		allRows.push(...rows);
	}));

	allRows.sort((a, b) => a.rank - b.rank);

	return {
		results: allRows
			.slice(offset, offset + limit)
			.map(({ id, title, authors }) => ({ id, title, authors })),
		total,
	};
}

export function rangeForId(id: string): YearRange | null {
	let digits: string;
	if (id.includes("/")) {
		digits = id.split("/")[1]?.slice(0, 2) ?? "";
	} else {
		digits = id.split(".")[0]?.slice(0, 2) ?? "";
	}
	const yy = parseInt(digits, 10);
	if (isNaN(yy)) return null;
	const year = yy + (yy < 50 ? 2000 : 1900);
	for (const range of DB_RANGES) {
		const [start, end] = range.split("-").map(Number);
		if (year >= start && year <= end) return range;
	}
	return null;
}

export async function getPaperDetail(id: string): Promise<PaperDetail | null> {
	const range = rangeForId(id);
	if (!range) return null;
	const worker = await loadWorker(range, "detail", detailWorkers, detailPending);
	const rows = toObjects<PaperDetail>(await dbOf(worker).exec(
		"SELECT id, abstract, categories, doi, license, update_date FROM papers WHERE id = ?",
		[id],
	));
	return rows[0] ?? null;
}
