<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import { goto } from "$app/navigation";
	import * as d3 from "d3";
	import { assignClusters, CLUSTER_COLORS } from "$lib/utils/graph-clusters";

	interface AuthNode { id: string; label: string; weight: number; }
	interface AuthEdge { source: string; target: string; weight: number; }
	interface Top80Graph { nodes: AuthNode[]; edges: AuthEdge[]; }

	interface DispNode extends d3.SimulationNodeDatum { id: string; label: string; weight: number; cluster: number; }

	let svgEl = $state<SVGSVGElement>();
	let containerEl = $state<HTMLDivElement>();
	let data = $state<Top80Graph | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			const res = await fetch(`${base}/data/authors/top80.json`);
			if (!res.ok) throw new Error("Failed to load");
			data = await res.json();
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed to load author graph";
		} finally {
			loading = false;
		}
	});

	$effect(() => {
		if (!data || !svgEl) return;
		const w = svgEl.clientWidth || containerEl?.clientWidth || 800;
		const h = Math.max(400, Math.min(600, w * 0.55));
		renderGraph($state.snapshot(data) as Top80Graph, svgEl, w, h);
	});

	function renderGraph(graph: Top80Graph, svg: SVGSVGElement, w: number, h: number) {
		const clusters = assignClusters(graph.nodes, graph.edges);
		svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
		d3.select(svg).selectAll("*").remove();
		const nodes: DispNode[] = graph.nodes.map((n, i) => ({ ...n, cluster: clusters[i] }));
		const edges = graph.edges.map((e) => ({ ...e }));
		const sim = d3.forceSimulation<DispNode>(nodes)
			.force("link", d3.forceLink(edges).id((d: any) => d.id).distance(50).strength(0.3))
			.force("charge", d3.forceManyBody().strength(-20))
			.force("center", d3.forceCenter(w / 2, h / 2))
			.force("collision", d3.forceCollide().radius(4))
			.stop();
		const ticks = Math.ceil(Math.log(sim.alphaMin()) / Math.log(1 - sim.alphaDecay()));
		sim.tick(ticks);
		const root = d3.select(svg).append("g");
		root.selectAll("line").data(edges).join("line")
			.attr("stroke", "var(--outline)")
			.attr("stroke-width", (d: any) => Math.max(0.2, Math.log((d as AuthEdge).weight) / 4))
			.attr("stroke-opacity", (d: any) => Math.min(0.5, 0.12 + Math.log((d as AuthEdge).weight) * 0.06))
			.attr("x1", (d: any) => d.source.x).attr("y1", (d: any) => d.source.y)
			.attr("x2", (d: any) => d.target.x).attr("y2", (d: any) => d.target.y);
		const maxW = Math.max(...graph.nodes.map((n) => n.weight));
		const radius = (d: any) => Math.max(2, Math.min(8, Math.sqrt(d.weight) * 0.15));
		root.selectAll("circle").data(nodes).join("circle")
			.attr("r", radius)
			.attr("fill", (d: any) => CLUSTER_COLORS[d.cluster % CLUSTER_COLORS.length])
			.attr("fill-opacity", (d: any) => 0.35 + (d.weight / maxW) * 0.45)
			.attr("stroke", "var(--surface-container)")
			.attr("stroke-width", 0.8)
			.attr("cursor", "pointer")
			.attr("cx", (d: any) => d.x).attr("cy", (d: any) => d.y)
			.on("click", (_e: MouseEvent, d: any) => goto(`/authors/${encodeURIComponent(d.id)}`))
			.append("title").text((d: any) => `${d.label} (${d.weight} papers)`);

		const labelled = [...nodes].sort((a, b) => b.weight - a.weight).slice(0, 12);
		root.selectAll("text").data(labelled).join("text")
			.attr("x", (d: any) => d.x).attr("y", (d: any) => d.y - radius(d) - 3)
			.attr("text-anchor", "middle")
			.attr("font-family", "var(--font-mono)").attr("font-size", "8px").attr("font-weight", "700")
			.attr("fill", "var(--on-surface-variant)").attr("pointer-events", "none")
			.text((d: any) => d.label);

		const zoom = d3.zoom<SVGSVGElement, unknown>()
			.scaleExtent([0.5, 6])
			.on("zoom", (e) => root.attr("transform", e.transform));
		d3.select(svg).call(zoom);
	}
</script>

{#if loading}
	<div bind:this={containerEl} class="label-caps flex h-[450px] items-center justify-center gap-2">
		Loading network…
	</div>
{:else if error}
	<div class="flex h-[450px] items-center justify-center font-mono text-xs text-warning-red">{error}</div>
{:else if data}
	<div bind:this={containerEl} class="overflow-hidden border border-outline/20 bg-surface-container">
		<svg bind:this={svgEl} class="h-[450px] w-full" role="img" aria-label="Co-authorship network graph — click a node to open the author"></svg>
	</div>
{/if}
