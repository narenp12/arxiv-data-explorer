import { describe, it, expect } from "vitest";
import { categoryLabel } from "./categories";

describe("categoryLabel", () => {
	it("returns label for known category", () => {
		expect(categoryLabel("cs.AI")).toBe("Artificial Intelligence");
	});

	it("returns id as fallback for unknown category", () => {
		expect(categoryLabel("zz.UNKNOWN")).toBe("zz.UNKNOWN");
	});

	it("handles empty string", () => {
		expect(categoryLabel("")).toBe("");
	});
});
