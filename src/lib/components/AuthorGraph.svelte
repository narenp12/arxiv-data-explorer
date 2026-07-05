<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import { goto } from "$app/navigation";
	import * as d3 from "d3";

	interface AuthNode { id: string; label: string; weight: number; }
	interface AuthEdge { source: string; target: string; weight: number; }
	interface Top80Graph { nodes: AuthNode[]; edges: AuthEdge[]; }

	interface DispNode extends d3.SimulationNodeDatum { id: string; label: string; weight: number; }

	let svgEl = $state<SVGSVGElement>();
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

	// Render once both the data and the <svg> exist — the svg only mounts
	// after `loading` flips, so rendering straight from onMount finds no element.
	$effect(() => {
		if (!data || !svgEl) return;
		renderGraph($state.snapshot(data) as Top80Graph, svgEl);
	});

	function renderGraph(graph: Top80Graph, svg: SVGSVGElement) {
		const w = svg.clientWidth || 800;
		const h = 400;
		svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
		d3.select(svg).selectAll("*").remove();
		const nodes: DispNode[] = graph.nodes.map((n) => ({ ...n }));
		const edges = graph.edges.map((e) => ({ ...e }));
		const sim = d3.forceSimulation<DispNode>(nodes)
			.force("link", d3.forceLink(edges).id((d: any) => d.id).distance(50).strength(0.3))
			.force("charge", d3.forceManyBody().strength(-20))
			.force("center", d3.forceCenter(w / 2, h / 2))
			.force("collision", d3.forceCollide().radius(4))
			.stop();
		const ticks = Math.ceil(Math.log(sim.alphaMin()) / Math.log(1 - sim.alphaDecay()));
		sim.tick(ticks);
		const g = d3.select(svg).append("g");
		g.selectAll("line").data(edges).join("line")
			.attr("stroke", "var(--outline)").attr("stroke-width", 0.3).attr("stroke-opacity", 0.3)
			.attr("x1", (d: any) => d.source.x).attr("y1", (d: any) => d.source.y)
			.attr("x2", (d: any) => d.target.x).attr("y2", (d: any) => d.target.y);
		g.selectAll("circle").data(nodes).join("circle")
			.attr("r", (d: any) => Math.max(2, Math.min(8, Math.sqrt(d.weight) * 0.15)))
			.attr("fill", "var(--primary)").attr("fill-opacity", 0.5)
			.attr("stroke", "var(--primary-container)").attr("stroke-width", 0.5)
			.attr("cursor", "pointer")
			.attr("cx", (d: any) => d.x).attr("cy", (d: any) => d.y)
			.on("click", (_e: MouseEvent, d: any) => goto(`/authors/${encodeURIComponent(d.id)}`))
			.append("title").text((d: any) => `${d.label} (${d.weight} papers)`);
	}
</script>

{#if loading}
	<div class="label-caps flex h-[400px] items-center justify-center gap-2">
		<span class="live-dot animate-pulse"></span>
		Loading network…
	</div>
{:else if error}
	<div class="flex h-[400px] items-center justify-center font-mono text-xs text-warning-red">{error}</div>
{:else if data}
	<div class="overflow-hidden border border-outline/20 bg-surface-container">
		<svg bind:this={svgEl} class="h-[400px] w-full" role="img" aria-label="Co-authorship network graph — click a node to open the author"></svg>
	</div>
{/if}
