<script lang="ts">
	import { onMount } from "svelte";
	import * as d3 from "d3";
	import { base } from "$app/paths";
	import { fetchReferences, fetchCitations } from "$lib/utils/openalex";
	import type { WorkSummary } from "$lib/types";

	let { openalexWorkId, currentTitle, arxivId }: {
		openalexWorkId: string | null;
		currentTitle: string;
		arxivId: string;
	} = $props();

	let svgEl = $state<SVGSVGElement>();
	let containerEl = $state<HTMLDivElement>();
	let loading = $state(true);
	let timedOut = $state(false);

	interface GraphNode extends d3.SimulationNodeDatum {
		id: string;
		label: string;
		citationCount: number;
		isCenter: boolean;
	}

	interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
		source: string;
		target: string;
	}

	onMount(async () => {
		const TIMEOUT_MS = 3000;
		const controller = new AbortController();
		const timer = setTimeout(() => {
			controller.abort();
			timedOut = true;
			loading = false;
		}, TIMEOUT_MS);

		try {
			const id = openalexWorkId ?? arxivId;
			if (!id) { loading = false; return; }

			const [refs, cites] = await Promise.all([
				fetchReferences(id, 15),
				fetchCitations(id, 15),
			]);

			clearTimeout(timer);

			if (refs.length === 0 && cites.length === 0) {
				loading = false;
				return;
			}

			const nodeMap = new Map<string, GraphNode>();
			const links: GraphLink[] = [];

			nodeMap.set("center", {
				id: "center",
				label: currentTitle.slice(0, 50) + (currentTitle.length > 50 ? "…" : ""),
				citationCount: 100,
				isCenter: true,
			});

			for (const r of refs) {
				nodeMap.set(r.id, {
					id: r.id,
					label: r.title.slice(0, 50) + (r.title.length > 50 ? "…" : ""),
					citationCount: r.citedByCount,
					isCenter: false,
				});
				links.push({ source: "center", target: r.id });
			}

			for (const c of cites) {
				if (!nodeMap.has(c.id)) {
					nodeMap.set(c.id, {
						id: c.id,
						label: c.title.slice(0, 50) + (c.title.length > 50 ? "…" : ""),
						citationCount: c.citedByCount,
						isCenter: false,
					});
				}
				links.push({ source: c.id, target: "center" });
			}

			const nodes = Array.from(nodeMap.values());
			const width = containerEl.clientWidth;
			const height = 350;

			const svg = d3.select(svgEl)
				.attr("viewBox", [0, 0, width, height]);

			const simulation = d3.forceSimulation<GraphNode>(nodes)
				.force("link", d3.forceLink<GraphNode, GraphLink>(links).id((d) => d.id).distance(100))
				.force("charge", d3.forceManyBody().strength(-200))
				.force("center", d3.forceCenter(width / 2, height / 2));

			const link = svg.append("g")
				.selectAll("line")
				.data(links)
				.join("line")
				.attr("stroke", "var(--color-outline-dim, #3a494b)")
				.attr("stroke-width", 1)
				.attr("stroke-opacity", 0.5);

			const node = svg.append("g")
				.selectAll("g")
				.data(nodes)
				.join("g")
				.style("cursor", "pointer")
				.on("click", (_event, d) => {
					if (!d.isCenter) {
						window.location.href = `${base}/papers/${d.id}`;
					}
				});

			node.append("circle")
				.attr("r", (d) => d.isCenter ? 10 : Math.max(3, Math.sqrt(d.citationCount) * 0.8))
				.attr("fill", (d) => d.isCenter ? "var(--color-primary, #00dbe7)" : "var(--color-phantom-violet, #d0bcff)")
				.attr("stroke", "var(--color-surface-container, #181818)")
				.attr("stroke-width", 1.5);

			node.append("title")
				.text((d) => d.label);

			node.append("text")
				.text((d) => d.label.slice(0, 25) + (d.label.length > 25 ? "…" : ""))
				.attr("x", 12)
				.attr("y", 4)
				.attr("font-size", "10px")
				.attr("fill", "var(--color-secondary, #b9cacb)");

			simulation.on("tick", () => {
				link
					.attr("x1", (d) => (d.source as GraphNode).x!)
					.attr("y1", (d) => (d.source as GraphNode).y!)
					.attr("x2", (d) => (d.target as GraphNode).x!)
					.attr("y2", (d) => (d.target as GraphNode).y!);
				node.attr("transform", (d) => `translate(${d.x},${d.y})`);
			});

		} catch {
			clearTimeout(timer);
			if (!controller.signal.aborted) timedOut = true;
		} finally {
			loading = false;
		}
	});
</script>

<div bind:this={containerEl} class="mt-4">
	{#if loading}
		<div class="flex items-center gap-2 text-secondary py-4">
			<span class="inline-block w-2 h-2 rounded-full bg-primary animate-pulse"></span>
			<span class="text-sm">Loading citation graph…</span>
		</div>
	{:else if timedOut}
		<p class="text-xs text-secondary py-4">Citation graph timed out. Data is available in the tabular views above.</p>
	{:else}
		<svg bind:this={svgEl} class="w-full rounded border border-outline-dim bg-surface-container"></svg>
	{/if}
</div>
