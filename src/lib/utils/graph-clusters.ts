export const CLUSTER_COLORS = [
	"var(--primary)",
	"var(--secondary)",
	"#d97706",
	"#059669",
	"#7c3aed",
];

interface AuthNode { id: string; label: string; weight: number; }
interface AuthEdge { source: string; target: string; weight: number; }

export function assignClusters(nodes: AuthNode[], edges: AuthEdge[]): number[] {
	const adj = new Map<string, string[]>();
	for (const n of nodes) adj.set(n.id, []);
	for (const e of edges) {
		adj.get(e.source)?.push(e.target);
		adj.get(e.target)?.push(e.source);
	}
	const visited = new Set<string>();
	const cluster = new Map<string, number>();
	let ci = 0;
	for (const n of nodes) {
		if (visited.has(n.id)) continue;
		const queue = [n.id];
		visited.add(n.id);
		for (let i = 0; i < queue.length; i++) {
			cluster.set(queue[i], ci);
			for (const nb of adj.get(queue[i]) ?? []) {
				if (!visited.has(nb)) { visited.add(nb); queue.push(nb); }
			}
		}
		ci++;
	}

	if (ci === 1) {
		const degrees = new Map<string, number>();
		for (const e of edges) {
			degrees.set(e.source, (degrees.get(e.source) ?? 0) + 1);
			degrees.set(e.target, (degrees.get(e.target) ?? 0) + 1);
		}
		const sorted = [...nodes].sort((a, b) => (degrees.get(b.id) ?? 0) - (degrees.get(a.id) ?? 0));
		const perBucket = Math.max(1, Math.ceil(sorted.length / CLUSTER_COLORS.length));
		for (let i = 0; i < sorted.length; i++) {
			cluster.set(sorted[i].id, Math.min(Math.floor(i / perBucket), CLUSTER_COLORS.length - 1));
		}
	}

	return nodes.map((n) => cluster.get(n.id) ?? 0);
}
