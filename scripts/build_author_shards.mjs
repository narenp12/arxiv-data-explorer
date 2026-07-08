// Builds sharded/pre-filtered author graph data files from the monolithic
// data-src/author_graph.json so page consumers don't have to download
// the whole 14MB+ file (and the monolith stays out of the deploy).
//
// Outputs:
//   static/data/authors/top80.json   - top 80 nodes by weight + edges among them (<=200)
//   static/data/authors/shard-<n>.json (n = 0..63) - per-author adjacency, sharded by fnv1a32(name) % 64
//
// Run with: node scripts/build_author_shards.mjs
// No dependencies.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..");
const SRC = join(repoRoot, "data-src", "author_graph.json");
const OUT_DIR = join(repoRoot, "static", "data", "authors");
const SHARD_COUNT = 64;

// Must match the TS client implementation exactly.
function fnv1a32(str) {
	let h = 0x811c9dc5;
	for (let i = 0; i < str.length; i++) {
		h ^= str.charCodeAt(i);
		h = Math.imul(h, 0x01000193) >>> 0;
	}
	return h;
}

function main() {
	console.log(`Reading ${SRC} ...`);
	const raw = readFileSync(SRC, "utf8");
	const data = JSON.parse(raw);
	const { nodes, edges } = data;
	console.log(`Loaded ${nodes.length} nodes, ${edges.length} edges.`);

	mkdirSync(OUT_DIR, { recursive: true });

	// --- top80.json ---
	const sorted = [...nodes].sort((a, b) => b.weight - a.weight);
	const top80Nodes = sorted.slice(0, 80);
	const topIds = new Set(top80Nodes.map((n) => n.id));
	const top80Edges = edges
		.filter((e) => topIds.has(e.source) && topIds.has(e.target))
		.sort((a, b) => b.weight - a.weight)
		.slice(0, 200);
	const top80 = { nodes: top80Nodes, edges: top80Edges };
	const top80Path = join(OUT_DIR, "top80.json");
	writeFileSync(top80Path, JSON.stringify(top80));
	console.log(`Wrote ${top80Path} (${top80Nodes.length} nodes, ${top80Edges.length} edges)`);

	// --- adjacency ---
	// name -> { w, coMap: Map<otherName, weight> }
	const adjacency = new Map();

	function ensure(name) {
		let entry = adjacency.get(name);
		if (!entry) {
			entry = { w: 0, coMap: new Map() };
			adjacency.set(name, entry);
		}
		return entry;
	}

	for (const node of nodes) {
		ensure(node.id).w = node.weight;
	}

	for (const edge of edges) {
		const srcEntry = ensure(edge.source);
		const tgtEntry = ensure(edge.target);
		srcEntry.coMap.set(edge.target, edge.weight);
		tgtEntry.coMap.set(edge.source, edge.weight);
	}

	// --- shard authors ---
	const shards = Array.from({ length: SHARD_COUNT }, () => ({}));

	for (const [name, entry] of adjacency) {
		const co = Array.from(entry.coMap.entries())
			.sort((a, b) => b[1] - a[1])
			.map(([otherName, weight]) => [otherName, weight]);
		const shardIdx = fnv1a32(name) % SHARD_COUNT;
		shards[shardIdx][name] = { w: entry.w, co };
	}

	const sizesKb = [];
	for (let i = 0; i < SHARD_COUNT; i++) {
		const shardPath = join(OUT_DIR, `shard-${i}.json`);
		const json = JSON.stringify(shards[i]);
		writeFileSync(shardPath, json);
		sizesKb.push(Buffer.byteLength(json, "utf8") / 1024);
	}

	const total = sizesKb.reduce((a, b) => a + b, 0);
	const min = Math.min(...sizesKb);
	const max = Math.max(...sizesKb);
	const avg = total / sizesKb.length;

	console.log("");
	console.log("Shard summary:");
	console.log(`  shard count: ${SHARD_COUNT}`);
	console.log(`  min shard size: ${min.toFixed(1)} KB`);
	console.log(`  max shard size: ${max.toFixed(1)} KB`);
	console.log(`  avg shard size: ${avg.toFixed(1)} KB`);
	console.log(`  total author entries: ${adjacency.size}`);
}

main();
