<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import * as d3 from "d3";

	interface AuthNode { id: string; label: string; weight: number; }
	interface AuthEdge { source: string; target: string; weight: number; }
	interface AuthGraph { nodes: AuthNode[]; edges: AuthEdge[]; metadata: { total_nodes: number; total_edges: number; } }

	interface DispNode extends d3.SimulationNodeDatum { id: string; label: string; weight: number; }

	let svgEl = $state<SVGSVGElement>();
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			const res = await fetch(`${base}/data/author_graph.json`);
			if (!res.ok) throw new Error("Failed to load");
			const data: AuthGraph = await res.json();
			const sorted = data.nodes.sort((a, b) => b.weight - a.weight);
			const top = sorted.slice(0, 80);
			const topIds = new Set(top.map((n) => n.id));
			const edgeFilter = data.edges.filter((e) => topIds.has(e.source) && topIds.has(e.target)).slice(0, 200);
			renderGraph(top, edgeFilter);
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed to load author graph";
		} finally {
			loading = false;
		}
	});

	function renderGraph(nodes: AuthNode[], edges: AuthEdge[]) {
		if (!svgEl) return;
		const w = svgEl.clientWidth || 800;
		const h = 400;
		svgEl.setAttribute("viewBox", `0 0 ${w} ${h}`);
		d3.select(svgEl).selectAll("*").remove();
		const sim = d3.forceSimulation<DispNode>(nodes.map((n) => ({ ...n })) as DispNode[])
			.force("link", d3.forceLink(edges).id((d: any) => d.id).distance(50).strength(0.3))
			.force("charge", d3.forceManyBody().strength(-20))
			.force("center", d3.forceCenter(w / 2, h / 2))
			.force("collision", d3.forceCollide().radius(4))
			.stop();
		const ticks = Math.ceil(Math.log(sim.alphaMin()) / Math.log(1 - sim.alphaDecay()));
		sim.tick(ticks);
		const g = d3.select(svgEl).append("g");
		g.selectAll("line").data(edges).join("line")
			.attr("stroke", "var(--outline)").attr("stroke-width", 0.3).attr("stroke-opacity", 0.3)
			.attr("x1", (d: any) => d.source.x).attr("y1", (d: any) => d.source.y)
			.attr("x2", (d: any) => d.target.x).attr("y2", (d: any) => d.target.y);
		g.selectAll("circle").data(nodes).join("circle")
			.attr("r", (d: any) => Math.max(2, Math.min(8, Math.sqrt(d.weight) * 0.15)))
			.attr("fill", "var(--primary)").attr("fill-opacity", 0.5)
			.attr("stroke", "var(--primary-container)").attr("stroke-width", 0.5)
			.attr("cx", (d: any) => d.x).attr("cy", (d: any) => d.y)
			.append("title").text((d: any) => `${d.label} (${d.weight} papers)`);
	}
</script>

{#if loading}
	<div class="label-caps flex items-center justify-center gap-2" class:h-[400px]={!svgEl}>
		<span class="live-dot animate-pulse"></span>
		Loading network…
	</div>
{:else if error}
	<div class="flex h-[400px] items-center justify-center font-mono text-xs text-warning-red">{error}</div>
{:else}
	<div class="overflow-hidden border border-outline/20 bg-surface-container">
		<svg bind:this={svgEl} class="h-[400px] w-full" role="img" aria-label="Co-authorship network graph"></svg>
	</div>
{/if}
