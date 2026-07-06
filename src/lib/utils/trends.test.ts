import { describe, it, expect } from "vitest";
import { annualPct, fmtAnnualPct, monthDate, monthLabel, sparklinePoints } from "./trends";

describe("annualPct", () => {
	it("returns 0 for a flat slope", () => {
		expect(annualPct(0)).toBeCloseTo(0);
	});

	it("returns positive for growth", () => {
		const result = annualPct(0.1);
		expect(result).toBeGreaterThan(0);
	});

	it("returns negative for decline", () => {
		const result = annualPct(-0.05);
		expect(result).toBeLessThan(0);
	});

	it("compounds correctly", () => {
		const result = annualPct(Math.log(2) / 12);
		expect(result).toBeCloseTo(100, 0);
	});
});

describe("fmtAnnualPct", () => {
	it("adds plus sign for positive", () => {
		expect(fmtAnnualPct(0.1)).toMatch(/^\+/);
	});

	it("has minus sign for negative", () => {
		expect(fmtAnnualPct(-0.1)).toMatch(/^-/);
	});

	it("no plus for zero", () => {
		expect(fmtAnnualPct(0)).toBe("0.0%");
	});

	it("formats to one decimal place", () => {
		expect(fmtAnnualPct(0.01)).toMatch(/^\+?\d+\.\d%/);
	});
});

describe("monthDate", () => {
	it("returns correct date for first month", () => {
		const d = monthDate("2007-06", 0);
		expect(d.getFullYear()).toBe(2007);
		expect(d.getMonth()).toBe(5);
	});

	it("handles offset within same year", () => {
		const d = monthDate("2020-01", 5);
		expect(d.getFullYear()).toBe(2020);
		expect(d.getMonth()).toBe(5);
	});

	it("rolls over to next year", () => {
		const d = monthDate("2020-11", 3);
		expect(d.getFullYear()).toBe(2021);
		expect(d.getMonth()).toBe(1);
	});
});

describe("monthLabel", () => {
	it("returns only the year", () => {
		expect(monthLabel("2007-06", 0)).toBe("2007");
	});

	it("handles year rollover", () => {
		expect(monthLabel("2020-11", 3)).toBe("2021");
	});
});

describe("sparklinePoints", () => {
	const series = [10, 20, 30, 40, 50];

	it("returns correct number of points", () => {
		const points = sparklinePoints(series, 100, 20);
		expect(points.split(" ")).toHaveLength(series.length);
	});

	it("uses only the tail portion", () => {
		const long = Array.from({ length: 100 }, (_, i) => i + 1);
		const points = sparklinePoints(long, 100, 20, 10);
		expect(points.split(" ")).toHaveLength(10);
	});

	it("handles flat data", () => {
		const points = sparklinePoints([5, 5, 5], 100, 20);
		expect(points).toBeTruthy();
	});

	it("handles single element", () => {
		const points = sparklinePoints([42], 100, 20);
		expect(points.split(" ")).toHaveLength(1);
	});
});
