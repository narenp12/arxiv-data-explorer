import { describe, it, expect } from "vitest";
import { assignClusters } from "$lib/utils/graph-clusters";

describe("assignClusters", () => {
	it("assigns different clusters to disconnected components", () => {
		const nodes = [
			{ id: "a", label: "A", weight: 1 },
			{ id: "b", label: "B", weight: 1 },
			{ id: "c", label: "C", weight: 1 },
		];
		const edges = [{ source: "a", target: "b", weight: 1 }];
		const clusters = assignClusters(nodes, edges);
		// component 1: a,b → 0; component 2: c → 1
		expect(clusters[0]).toBe(clusters[1]); // a and b same cluster
		expect(clusters[2]).toBe(1); // c gets next cluster
	});

	it("splits a single component by degree rank", () => {
		const nodes = Array.from({ length: 10 }, (_, i) => ({
			id: `n${i}`,
			label: `N${i}`,
			weight: 1,
		}));
		const edges = nodes.slice(1).map((n) => ({
			source: "n0",
			target: n.id,
			weight: 1,
		}));
		const clusters = assignClusters(nodes, edges);
		const unique = new Set(clusters);
		expect(unique.size).toBeGreaterThan(1);
	});

	it("never returns an out-of-range cluster index", () => {
		const nodes = Array.from({ length: 20 }, (_, i) => ({
			id: `n${i}`,
			label: `N${i}`,
			weight: 1,
		}));
		const edges = nodes.slice(1).map((n) => ({
			source: "n0",
			target: n.id,
			weight: 1,
		}));
		const clusters = assignClusters(nodes, edges);
		for (const c of clusters) {
			expect(c).toBeGreaterThanOrEqual(0);
			expect(c).toBeLessThan(5);
		}
	});

	it("handles empty nodes gracefully", () => {
		expect(assignClusters([], [])).toEqual([]);
	});
});
