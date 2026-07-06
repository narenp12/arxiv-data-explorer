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
	let activeTooltip = $state<{ node: { label: string; weight: number; degree: number }; x: number; y: number } | null>(null);
	let selectedNode = $state<{ id: string; label: string; weight: number } | null>(null);
	let searchQuery = $state("");

	let matchCount = $derived(
		searchQuery.trim()
			? graphNodes.filter((n: any) => n.label.toLowerCase().includes(searchQuery.trim().toLowerCase())).length
			: graphNodes.length
	);

	let svgRoot: d3.Selection<SVGGElement, unknown, null, undefined> | null = null;
	let graphEdges: any[] = $state([]);
	let graphNodes: any[] = $state([]);
	let graphMaxW = 0;

	let coauthorList = $derived.by(() => {
		if (!selectedNode) return [];
		const degrees = new Map<string, number>();
		for (const e of graphEdges) {
			const source = e.source as any;
			const target = e.target as any;
			if (source.id === selectedNode.id) degrees.set(target.label ?? target.id, (degrees.get(target.label ?? target.id) ?? 0) + (e.weight ?? 1));
			if (target.id === selectedNode.id) degrees.set(source.label ?? source.id, (degrees.get(source.label ?? source.id) ?? 0) + (e.weight ?? 1));
		}
		return [...degrees.entries()]
			.map(([name, weight]) => ({ name, weight }))
			.sort((a, b) => b.weight - a.weight)
			.slice(0, 15);
	});

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

	function nodeOpacity(w: number) {
		return 0.35 + (w / Math.max(graphMaxW, 1)) * 0.45;
	}

	$effect(() => {
		const q = searchQuery.trim().toLowerCase();
		const sel = selectedNode;
		if (!svgRoot || !graphEdges.length) return;
		const root = svgRoot;
		if (q) {
			root.selectAll<any, any>("circle")
				.attr("fill-opacity", (d: any) =>
					d.label.toLowerCase().includes(q) ? nodeOpacity(d.weight) : nodeOpacity(d.weight) * 0.1
				);
			root.selectAll<any, any>("line").attr("stroke-opacity", 0.04);
		} else if (sel) {
			root.selectAll<any, any>("circle")
				.attr("fill-opacity", (d: any) => {
					if (d.id === sel.id) return nodeOpacity(d.weight);
					const connected = graphEdges.some(
						(e: any) => ((e.source as any).id === d.id || (e.target as any).id === d.id) &&
							((e.source as any).id === sel.id || (e.target as any).id === sel.id)
					);
					return connected ? nodeOpacity(d.weight) : nodeOpacity(d.weight) * 0.15;
				})
				.attr("stroke", (d: any) => d.id === sel.id ? "var(--primary)" : "var(--surface-container)")
				.attr("stroke-width", (d: any) => d.id === sel.id ? 2.5 : 0.8);
			root.selectAll<any, any>("line")
				.attr("stroke-opacity", (e: any) => {
					const touches = (e.source as any).id === sel.id || (e.target as any).id === sel.id;
					return touches ? 0.5 : 0.04;
				});
		} else {
			root.selectAll<any, any>("circle")
				.attr("fill-opacity", (d: any) => nodeOpacity(d.weight))
				.attr("stroke", "var(--surface-container)")
				.attr("stroke-width", 0.8);
			root.selectAll<any, any>("line")
				.attr("stroke-opacity", (d: any) => Math.min(0.5, 0.12 + Math.log((d as any).weight) * 0.06));
		}
	});

	onMount(() => {
		function onKey(e: KeyboardEvent) {
			if (e.key === "Escape") selectedNode = null;
		}
		document.addEventListener("keydown", onKey);
		return () => document.removeEventListener("keydown", onKey);
	});

	function renderGraph(graph: Top80Graph, svg: SVGSVGElement, w: number, h: number) {
		const prefersReducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
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
		svgRoot = d3.select(svg).append("g");
		graphEdges = edges;
		graphNodes = nodes;
		graphMaxW = Math.max(...graph.nodes.map((n) => n.weight));
		svgRoot.selectAll("line").data(edges).join("line")
			.attr("stroke", "var(--outline)")
			.attr("stroke-width", (d: any) => Math.max(0.2, Math.log((d as AuthEdge).weight) / 4))
			.attr("stroke-opacity", (d: any) => Math.min(0.5, 0.12 + Math.log((d as AuthEdge).weight) * 0.06))
			.attr("x1", (d: any) => d.source.x).attr("y1", (d: any) => d.source.y)
			.attr("x2", (d: any) => d.target.x).attr("y2", (d: any) => d.target.y);
		const root = svgRoot;
		const maxW = graphMaxW;
		const nodeOpacity = (d: { weight: number }) => 0.35 + (d.weight / maxW) * 0.45;
		const radius = (d: any) => Math.max(2, Math.min(8, Math.sqrt(d.weight) * 0.15));
		const circles = root.selectAll("circle").data(nodes).join("circle")
			.attr("r", radius)
			.attr("fill", (d: any) => CLUSTER_COLORS[d.cluster % CLUSTER_COLORS.length])
			.attr("fill-opacity", (d: any) => nodeOpacity(d))
			.attr("stroke", "var(--surface-container)")
			.attr("stroke-width", 0.8)
			.attr("cursor", "pointer")
			.attr("cx", (d: any) => d.x).attr("cy", (d: any) => d.y)
			.on("click", (_e: MouseEvent, d: any) => {
				if (selectedNode?.id === d.id) { selectedNode = null; return; }
				selectedNode = d;
			})
			.on("mouseenter", (event: MouseEvent, d: any) => {
				const rect = (event.currentTarget as SVGSVGElement).closest("svg")!.getBoundingClientRect();
				const degree = edges.filter(
					(e: any) => (e.source as DispNode).id === d.id || (e.target as DispNode).id === d.id
				).length;
				activeTooltip = { node: { label: d.label, weight: d.weight, degree }, x: event.clientX - rect.left, y: event.clientY - rect.top };
				if (!prefersReducedMotion) {
					root.selectAll<SVGCircleElement, any>("circle")
						.attr("fill-opacity", (n: any) => {
							if (n.id === d.id) return nodeOpacity(n);
							const connected = edges.some(
								(e: any) => ((e.source as DispNode).id === n.id || (e.target as DispNode).id === n.id) &&
									((e.source as DispNode).id === d.id || (e.target as DispNode).id === d.id)
							);
							return connected ? nodeOpacity(n) : nodeOpacity(n) * 0.15;
						});
					root.selectAll<any, any>("line")
						.attr("stroke-opacity", (e: any) => {
							const touches = (e.source as DispNode).id === d.id || (e.target as DispNode).id === d.id;
							return touches ? 0.5 : 0.04;
						});
				}
			})
			.on("mouseleave", () => {
				activeTooltip = null;
				if (!prefersReducedMotion) {
					const q = searchQuery.trim().toLowerCase();
					const sel = selectedNode;
					if (q) {
						root.selectAll<SVGCircleElement, any>("circle")
							.attr("fill-opacity", (d: any) =>
								d.label.toLowerCase().includes(q) ? nodeOpacity(d) : nodeOpacity(d) * 0.1
							);
						root.selectAll<any, any>("line").attr("stroke-opacity", 0.04);
					} else if (sel) {
						root.selectAll<SVGCircleElement, any>("circle")
							.attr("fill-opacity", (d: any) => {
								if (d.id === sel.id) return nodeOpacity(d);
								const connected = edges.some(
									(e: any) => ((e.source as any).id === d.id || (e.target as any).id === d.id) &&
										((e.source as any).id === sel.id || (e.target as any).id === sel.id)
								);
								return connected ? nodeOpacity(d) : nodeOpacity(d) * 0.15;
							});
						root.selectAll<any, any>("line")
							.attr("stroke-opacity", (e: any) => {
								const touches = (e.source as any).id === sel.id || (e.target as any).id === sel.id;
								return touches ? 0.5 : 0.04;
							});
					} else {
						root.selectAll<SVGCircleElement, any>("circle")
							.attr("fill-opacity", (d: any) => nodeOpacity(d));
						root.selectAll<any, any>("line")
							.attr("stroke-opacity", (d: any) => Math.min(0.5, 0.12 + Math.log((d as any).weight) * 0.06));
					}
				}
			});

		const dragHandler = d3.drag<SVGCircleElement, any>()
			.on("start", (event, d) => {
				if (prefersReducedMotion) return;
				if (!event.active) sim.alphaTarget(0.3).restart();
				d.fx = d.x;
				d.fy = d.y;
			})
			.on("drag", (event, d) => {
				if (prefersReducedMotion) return;
				d.fx = event.x;
				d.fy = event.y;
			})
			.on("end", (event, d) => {
				if (prefersReducedMotion) return;
				if (!event.active) sim.alphaTarget(0);
				d.fx = null;
				d.fy = null;
			});
		circles.call(dragHandler);

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
	<div class="mb-3 flex items-center gap-3">
		<input
			type="search"
			bind:value={searchQuery}
			placeholder="Find an author…"
			class="flex-1 border border-outline/20 bg-surface-container px-3 py-1.5 font-mono text-xs text-on-surface transition-colors placeholder:text-outline focus:border-primary focus:outline-none"
		/>
		{#if searchQuery.trim()}
			<span class="font-mono text-xs text-on-surface-variant">{matchCount}/{graphNodes.length} matches</span>
		{/if}
	</div>
	<div bind:this={containerEl} class="relative overflow-hidden border border-outline/20 bg-surface-container">
		<svg bind:this={svgEl} class="h-[450px] w-full" role="img" aria-label="Co-authorship network graph — click a node to select it"></svg>
		{#if activeTooltip}
			<div
				class="pointer-events-none absolute z-10 rounded border border-outline/20 bg-surface-container px-3 py-2 font-mono text-xs shadow-lg"
				style="left: {activeTooltip.x}px; top: {activeTooltip.y}px; transform: translate(8px, -50%)"
			>
				<div class="font-bold text-on-surface">{activeTooltip.node.label}</div>
				<div class="text-on-surface-variant">{activeTooltip.node.weight} papers · {activeTooltip.node.degree} co-author{activeTooltip.node.degree !== 1 ? "s" : ""}</div>
			</div>
		{/if}
	</div>
	{#if selectedNode}
		<div class="mt-3 border border-outline/20 bg-surface-container p-4">
			<div class="flex items-start justify-between">
				<div>
					<div class="font-mono text-lg font-bold text-primary">{selectedNode.label}</div>
					<div class="font-mono text-xs text-on-surface-variant">{selectedNode.weight} papers · {coauthorList.length} co-author{coauthorList.length !== 1 ? "s" : ""} in this network</div>
				</div>
				<a
					href="{base}/authors/{encodeURIComponent(selectedNode.id)}"
					class="border border-outline/20 bg-surface px-3 py-1.5 font-mono text-xs font-bold text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
				>
					View profile →
				</a>
			</div>
			{#if coauthorList.length > 0}
				<div class="mt-3 divide-y divide-outline/20 border-t border-outline/20">
					{#each coauthorList as co}
						<a
							href="{base}/authors/{encodeURIComponent(co.name)}"
							class="flex items-center justify-between px-1 py-1.5 font-mono text-xs transition-colors hover:bg-surface-container-low"
						>
							<span class="text-on-surface">{co.name}</span>
							<span class="text-on-surface-variant">{co.weight} collaboration{co.weight !== 1 ? "s" : ""}</span>
						</a>
					{/each}
				</div>
			{:else}
				<div class="mt-3 font-mono text-xs text-on-surface-variant">
					No co-authorship data available for this author in the top-80 network.
				</div>
			{/if}
		</div>
	{/if}
{/if}
