/** Shared helpers for the trends/takeoffs/compare pages. */

export interface CausalEdge {
	source: string;
	target: string;
	weight: number;
	ci_lower: number;
	ci_upper: number;
	prob: number;
}

export interface CausalCategory {
	id: string;
	trend: number; // monthly log-slope
	trend_ci: [number, number];
	anchor: [number, number]; // [tbar, zbar] of the log1p fit
}

export interface CausalData {
	meta: { start: string; months: number; units: string };
	edges: CausalEdge[];
	categories: CausalCategory[];
}

export interface DynamicsData {
	meta: { start: string; months: number };
	series: Record<string, number[]>;
}

/** Convert a monthly log-slope into a human annual growth percentage. */
export function annualPct(monthlyLogSlope: number): number {
	return (Math.exp(12 * monthlyLogSlope) - 1) * 100;
}

export function fmtAnnualPct(monthlyLogSlope: number): string {
	const pct = annualPct(monthlyLogSlope);
	return `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

/** "2007-06" + 14 → Date for that month index. */
export function monthDate(start: string, idx: number): Date {
	const [y, m] = start.split("-").map(Number);
	return new Date(y, m - 1 + idx, 1);
}

export function monthLabel(start: string, idx: number): string {
	return String(monthDate(start, idx).getFullYear());
}

/** Polyline points string for a small sparkline of the series tail. */
export function sparklinePoints(
	series: number[],
	w: number,
	h: number,
	tail = 72,
): string {
	const data = series.slice(-tail);
	const max = Math.max(...data, 1);
	const step = w / Math.max(data.length - 1, 1);
	return data
		.map((v, i) => `${(i * step).toFixed(1)},${(h - (v / max) * (h - 2) - 1).toFixed(1)}`)
		.join(" ");
}
