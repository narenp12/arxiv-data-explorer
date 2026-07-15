<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";

	import * as d3 from "d3";
	import { assignClusters, CLUSTER_COLORS } from "$lib/utils/graph-clusters";

	interface AuthNode { id: string; label: string; weight: number; }
	interface AuthEdge { source: string; target: string; weight: number; }
	interface Top80Graph { nodes: AuthNode[]; edges: AuthEdge[]; }

	interface DispNode extends d3.SimulationNodeDatum { id: string; label: string; weight: number; cluster: number; }

	type D3SimNode = d3.SimulationNodeDatum & DispNode;
	type D3SimEdge = d3.SimulationLinkDatum<D3SimNode> & Omit<AuthEdge, "source" | "target">;

	let svgEl = $state<SVGSVGElement>();
	let containerEl = $state<HTMLDivElement>();
	let data = $state<Top80Graph | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let activeTooltip = $state<{ node: { label: string; weight: number; degree: number }; x: number; y: number } | null>(null);
	let selectedNode = $state<{ id: string; label: string; weight: number } | null>(null);
	let searchQuery = $state("");

	let svgRoot: d3.Selection<SVGGElement, unknown, null, undefined> | null = null;
	let graphEdges: D3SimEdge[] = $state([]);
	let graphNodes: D3SimNode[] = $state([]);
	let graphMaxW = 0;
	let labelSet = new Set<string>();
	const graphRadius = (w: number) => Math.max(2, Math.min(8, Math.sqrt(w) * 0.15));

	let matchCount = $derived(
		searchQuery.trim()
			? graphNodes.filter((n: D3SimNode) => n.label.toLowerCase().includes(searchQuery.trim().toLowerCase())).length
			: graphNodes.length
	);

	let coauthorList = $derived.by(() => {
		if (!selectedNode) return [];
		const degrees = new Map<string, number>();
		for (const e of graphEdges) {
			const source = e.source as D3SimNode;
			const target = e.target as D3SimNode;
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
			root.selectAll<SVGCircleElement, D3SimNode>("circle")
				.attr("fill-opacity", (d: D3SimNode) =>
					d.label.toLowerCase().includes(q) ? nodeOpacity(d.weight) : nodeOpacity(d.weight) * 0.1
				);
			root.selectAll<SVGPathElement, D3SimEdge>("path").attr("stroke-opacity", 0.04);
		} else if (sel) {
			const motionOk = !matchMedia("(prefers-reduced-motion: reduce)").matches;
			root.selectAll<SVGCircleElement, D3SimNode>("circle")
				.attr("fill-opacity", (d: D3SimNode) => {
					if (d.id === sel.id) return nodeOpacity(d.weight);
					const connected = graphEdges.some(
						(e: D3SimEdge) => ((e.source as D3SimNode).id === d.id || (e.target as D3SimNode).id === d.id) &&
							((e.source as D3SimNode).id === sel.id || (e.target as D3SimNode).id === sel.id)
					);
					return connected ? nodeOpacity(d.weight) : nodeOpacity(d.weight) * 0.15;
				})
				.attr("stroke", (d: D3SimNode) => d.id === sel.id ? "var(--primary)" : "var(--surface-container)")
				.attr("stroke-width", (d: D3SimNode) => d.id === sel.id ? 2.5 : 0.8)
				.attr("style", (d: D3SimNode) =>
					d.id === sel.id && motionOk
						? "animation: select-pulse 0.4s ease-out 2; transition: stroke-width 150ms ease, stroke-opacity 150ms ease"
						: "transition: fill-opacity 150ms ease, stroke-opacity 150ms ease, stroke-width 150ms ease"
				);
			const egoIds = new Set([sel.id]);
			for (const e of graphEdges) {
				if ((e.source as D3SimNode).id === sel.id) egoIds.add((e.target as D3SimNode).id);
				if ((e.target as D3SimNode).id === sel.id) egoIds.add((e.source as D3SimNode).id);
			}
			const egoUnlabelled = graphNodes.filter((n: D3SimNode) => egoIds.has(n.id) && !labelSet.has(n.id));
			if (egoUnlabelled.length) {
				root.selectAll<SVGTextElement, D3SimNode>("text.node-ego-label").data(egoUnlabelled).join("text")
					.attr("class", "node-ego-label")
					.attr("x", (d: D3SimNode) => d.x).attr("y", (d: D3SimNode) => d.y - graphRadius(d.weight) - 3)
					.attr("text-anchor", "middle")
					.attr("font-family", "var(--font-mono)").attr("font-size", "8px").attr("font-weight", "700")
					.attr("fill", "var(--on-surface-variant)").attr("pointer-events", "none")
					.text((d: D3SimNode) => d.label);
			}
			root.selectAll<SVGPathElement, D3SimEdge>("path")
				.attr("stroke-opacity", (e: D3SimEdge) => {
					const touches = (e.source as D3SimNode).id === sel.id || (e.target as D3SimNode).id === sel.id;
					return touches ? 0.5 : 0.04;
				});
		} else {
			root.selectAll<SVGCircleElement, D3SimNode>("circle")
				.attr("fill-opacity", (d: D3SimNode) => nodeOpacity(d.weight))
				.attr("stroke", "var(--surface-container)")
				.attr("stroke-width", 0.8)
				.attr("style", "transition: fill-opacity 150ms ease, stroke-opacity 150ms ease, stroke-width 150ms ease");
			root.selectAll<SVGPathElement, D3SimEdge>("path")
				.attr("stroke-opacity", (d: D3SimEdge) => Math.min(0.5, 0.12 + Math.log(d.weight) * 0.06));
			root.selectAll<SVGTextElement, D3SimNode>("text.node-ego-label").remove();
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
		const edges = graph.edges.map((e) => ({ ...e })) as unknown as D3SimEdge[];
		const sim = d3.forceSimulation<DispNode>(nodes)
			.force("link", d3.forceLink<D3SimNode, D3SimEdge>(edges).id((d) => d.id).distance(50).strength(0.3))
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
		function edgePath(d: D3SimEdge): string {
			const src = d.source as D3SimNode, tgt = d.target as D3SimNode;
			const sx = src.x, sy = src.y, tx = tgt.x, ty = tgt.y;
			const mx = (sx + tx) / 2, my = (sy + ty) / 2;
			const dx = tx - sx, dy = ty - sy, len = Math.hypot(dx, dy) || 1;
			const offset = 4 + Math.log(d.weight) * 2;
			const cx = mx + (-dy / len) * offset, cy = my + (dx / len) * offset;
			return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`;
		}
		svgRoot.selectAll("path").data(edges).join("path")
			.attr("d", edgePath)
			.attr("fill", "none")
			.attr("stroke", "var(--outline)")
			.attr("stroke-width", (d: D3SimEdge) => Math.max(0.2, Math.log(d.weight) / 4))
			.attr("stroke-opacity", (d: D3SimEdge) => Math.min(0.5, 0.12 + Math.log(d.weight) * 0.06))
			.attr("style", "transition: stroke-opacity 150ms ease");
		const root = svgRoot;

		const radius = (d: D3SimNode) => Math.max(2, Math.min(8, Math.sqrt(d.weight) * 0.15));
		const circles = root.selectAll<SVGCircleElement, D3SimNode>("circle").data(nodes).join("circle")
			.attr("r", radius)
			.attr("fill", (d: D3SimNode) => CLUSTER_COLORS[d.cluster % CLUSTER_COLORS.length])
			.attr("fill-opacity", (d: D3SimNode) => nodeOpacity(d.weight))
			.attr("stroke", "var(--surface-container)")
			.attr("stroke-width", 0.8)
			.attr("cursor", "pointer")
			.attr("style", "transition: fill-opacity 150ms ease, stroke-opacity 150ms ease")
			.attr("cx", (d: D3SimNode) => d.x).attr("cy", (d: D3SimNode) => d.y)
			.on("click", (_e: MouseEvent, d: D3SimNode) => {
				if (selectedNode?.id === d.id) { selectedNode = null; return; }
				selectedNode = d;
			})
			.on("mouseenter", (event: MouseEvent, d: D3SimNode) => {
				if ("ontouchstart" in window) return;
				const rect = (event.currentTarget as SVGSVGElement).closest("svg")!.getBoundingClientRect();
				const degree = edges.filter(
					(e: D3SimEdge) => (e.source as D3SimNode).id === d.id || (e.target as D3SimNode).id === d.id
				).length;
				activeTooltip = { node: { label: d.label, weight: d.weight, degree }, x: event.clientX - rect.left, y: event.clientY - rect.top };
				if (!prefersReducedMotion) {
					root.selectAll<SVGCircleElement, D3SimNode>("circle")
						.attr("fill-opacity", (n: D3SimNode) => {
							if (n.id === d.id) return nodeOpacity(n.weight);
							const connected = edges.some(
								(e: D3SimEdge) => ((e.source as D3SimNode).id === n.id || (e.target as D3SimNode).id === n.id) &&
									((e.source as D3SimNode).id === d.id || (e.target as D3SimNode).id === d.id)
							);
							return connected ? nodeOpacity(n.weight) : nodeOpacity(n.weight) * 0.15;
						});
					root.selectAll<SVGPathElement, D3SimEdge>("path")
						.attr("stroke-opacity", (e: D3SimEdge) => {
							const touches = (e.source as D3SimNode).id === d.id || (e.target as D3SimNode).id === d.id;
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
						root.selectAll<SVGCircleElement, D3SimNode>("circle")
							.attr("fill-opacity", (d: D3SimNode) =>
								d.label.toLowerCase().includes(q) ? nodeOpacity(d.weight) : nodeOpacity(d.weight) * 0.1
							);
						root.selectAll<SVGPathElement, D3SimEdge>("path").attr("stroke-opacity", 0.04);
					} else if (sel) {
						root.selectAll<SVGCircleElement, D3SimNode>("circle")
							.attr("fill-opacity", (d: D3SimNode) => {
								if (d.id === sel.id) return nodeOpacity(d.weight);
								const connected = edges.some(
									(e: D3SimEdge) => ((e.source as D3SimNode).id === d.id || (e.target as D3SimNode).id === d.id) &&
										((e.source as D3SimNode).id === sel.id || (e.target as D3SimNode).id === sel.id)
								);
								return connected ? nodeOpacity(d.weight) : nodeOpacity(d.weight) * 0.15;
							});
						root.selectAll<SVGPathElement, D3SimEdge>("path")
							.attr("stroke-opacity", (e: D3SimEdge) => {
								const touches = (e.source as D3SimNode).id === sel.id || (e.target as D3SimNode).id === sel.id;
								return touches ? 0.5 : 0.04;
							});
					} else {
						root.selectAll<SVGCircleElement, D3SimNode>("circle")
							.attr("fill-opacity", (d: D3SimNode) => nodeOpacity(d.weight));
						root.selectAll<SVGPathElement, D3SimEdge>("path")
							.attr("stroke-opacity", (d: D3SimEdge) => Math.min(0.5, 0.12 + Math.log(d.weight) * 0.06));
					}
				}
			});

		const dragHandler = d3.drag<SVGCircleElement, D3SimNode>()
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
		labelSet = new Set(labelled.map((n: D3SimNode) => n.id));
		root.selectAll("text").data(labelled).join("text")
			.attr("x", (d: D3SimNode) => d.x).attr("y", (d: D3SimNode) => d.y - radius(d) - 3)
			.attr("text-anchor", "middle")
			.attr("class", "node-label")
			.attr("font-family", "var(--font-mono)").attr("font-size", "8px").attr("font-weight", "700")
			.attr("fill", "var(--on-surface-variant)").attr("pointer-events", "none")
			.text((d: D3SimNode) => d.label);

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
{:else if data && data.nodes.length === 0}
	<div class="flex h-[450px] items-center justify-center font-mono text-sm text-on-surface-variant">
		No co-authorship data available.
	</div>
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
	<div class="mt-2 flex items-center gap-3 font-mono text-[10px] text-on-surface-variant">
		Clusters
		{#each CLUSTER_COLORS as color}
			<span class="inline-block h-2 w-2 rounded-full" style="background: {color}"></span>
		{/each}
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

<style>
	@keyframes -global-select-pulse {
		0% { stroke-width: 2.5; stroke-opacity: 1; }
		50% { stroke-width: 4; stroke-opacity: 0.6; }
		100% { stroke-width: 2.5; stroke-opacity: 1; }
	}
</style>
