<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import { goto } from "$app/navigation";
	import * as d3 from "d3";
	import { fmtAnnualPct, type CausalData, type CausalEdge } from "$lib/utils/trends";
	import { categoryLabel } from "$lib/utils/categories";

	interface GraphNode extends d3.SimulationNodeDatum {
		id: string;
		trend: number;
		vol: number; // zbar — mean log volume, drives radius
	}

	let svgEl = $state<SVGSVGElement>();
	let data = $state<CausalData | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let minProb = $state(0.95);
	let selectedId = $state<string | null>(null);
	let hoverEdge = $state<CausalEdge | null>(null);

	// positioned layout, computed once per data load
	let layout: { nodes: GraphNode[]; links: (CausalEdge & { sx: number; sy: number; tx: number; ty: number })[] } | null = null;

	onMount(async () => {
		try {
			const res = await fetch(`${base}/data/causal_edges.json`);
			if (!res.ok) throw new Error("Failed to load causal data");
			data = await res.json();
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed to load";
		} finally {
			loading = false;
		}
	});

	let visibleEdges = $derived(data ? data.edges.filter((e) => e.prob >= minProb) : []);

	let neighborhood = $derived.by(() => {
		if (!selectedId) return null;
		const up = new Set<string>();
		const down = new Set<string>();
		for (const e of visibleEdges) {
			if (e.target === selectedId) up.add(e.source);
			if (e.source === selectedId) down.add(e.target);
		}
		return { up, down };
	});

	function nodeColor(trend: number): string {
		if (trend > 0.005) return "var(--signal-green)";
		if (trend < -0.005) return "var(--warning-red)";
		return "var(--outline)";
	}

	$effect(() => {
		if (!data || !svgEl) return;
		const snapshot = $state.snapshot(data) as CausalData;

		const w = svgEl.clientWidth || 900;
		const h = Math.max(450, Math.min(560, w * 0.55));
		svgEl.setAttribute("viewBox", `0 0 ${w} ${h}`);

		if (!layout) {
			const nodes: GraphNode[] = snapshot.categories.map((c) => ({
				id: c.id,
				trend: c.trend,
				vol: c.anchor?.[1] ?? 1,
			}));
			const nodeIds = new Set(nodes.map((n) => n.id));
			const simLinks = snapshot.edges
				.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
				.map((e) => ({ ...e }));

			const sim = d3.forceSimulation(nodes)
				.force("link", d3.forceLink(simLinks as any).id((d: any) => d.id).distance(60).strength(0.2))
				.force("charge", d3.forceManyBody().strength(-90))
				.force("center", d3.forceCenter(w / 2, h / 2))
				.force("collision", d3.forceCollide().radius(10))
				.stop();
			const ticks = Math.ceil(Math.log(sim.alphaMin()) / Math.log(1 - sim.alphaDecay()));
			sim.tick(ticks);

			const pos = new Map(nodes.map((n) => [n.id, n]));
			layout = {
				nodes,
				links: snapshot.edges
					.filter((e) => pos.has(e.source) && pos.has(e.target))
					.map((e) => ({
						...e,
						sx: pos.get(e.source)!.x!,
						sy: pos.get(e.source)!.y!,
						tx: pos.get(e.target)!.x!,
						ty: pos.get(e.target)!.y!,
					})),
			};
		}

		draw(layout, w, h, minProb, selectedId);
	});

	function draw(
		lay: NonNullable<typeof layout>,
		w: number,
		h: number,
		threshold: number,
		selected: string | null,
	) {
		const svg = d3.select(svgEl!);
		svg.selectAll("*").remove();

		const defs = svg.append("defs");
		for (const [name, color] of [["arrow-pos", "var(--signal-green)"], ["arrow-neg", "var(--warning-red)"]] as const) {
			defs.append("marker")
				.attr("id", name)
				.attr("viewBox", "0 -4 8 8")
				.attr("refX", 12)
				.attr("markerWidth", 5)
				.attr("markerHeight", 5)
				.attr("orient", "auto")
				.append("path")
				.attr("d", "M0,-4L8,0L0,4")
				.attr("fill", color);
		}

		const root = svg.append("g");

		const nb = selected
			? {
					up: new Set(lay.links.filter((l) => l.prob >= threshold && l.target === selected).map((l) => l.source)),
					down: new Set(lay.links.filter((l) => l.prob >= threshold && l.source === selected).map((l) => l.target)),
				}
			: null;

		const inFocus = (id: string) =>
			!selected || id === selected || nb!.up.has(id) || nb!.down.has(id);

		root.append("g")
			.selectAll("line")
			.data(lay.links.filter((l) => l.prob >= threshold))
			.join("line")
			.attr("stroke", (d) => (d.weight > 0 ? "var(--signal-green)" : "var(--warning-red)"))
			.attr("stroke-width", (d) => Math.max(0.6, Math.min(3.5, Math.abs(d.weight) * 6)))
			.attr("stroke-opacity", (d) => {
				const touches = !selected || d.source === selected || d.target === selected;
				return touches ? 0.15 + (d.prob - 0.9) * 6 : 0.04;
			})
			.attr("marker-end", (d) => {
				const touches = !selected || d.source === selected || d.target === selected;
				return touches ? `url(#${d.weight > 0 ? "arrow-pos" : "arrow-neg"})` : null;
			})
			.attr("x1", (d) => d.sx)
			.attr("y1", (d) => d.sy)
			.attr("x2", (d) => d.tx)
			.attr("y2", (d) => d.ty)
			.attr("cursor", "pointer")
			.on("mouseenter", (_e, d) => { hoverEdge = d; })
			.on("mouseleave", () => { hoverEdge = null; })
			.on("click", (e, d) => { e.stopPropagation(); hoverEdge = d; });

		root.append("g")
			.selectAll("circle")
			.data(lay.nodes)
			.join("circle")
			.attr("r", (d) => 2.5 + Math.max(0, d.vol) * 0.8)
			.attr("fill", (d) => nodeColor(d.trend))
			.attr("fill-opacity", (d) => (inFocus(d.id) ? 0.95 : 0.15))
			.attr("stroke", (d) => (d.id === selected ? "var(--primary)" : "var(--surface-container)"))
			.attr("stroke-width", (d) => (d.id === selected ? 2.5 : 1))
			.attr("cx", (d) => d.x!)
			.attr("cy", (d) => d.y!)
			.attr("cursor", "pointer")
			.on("click", (e, d) => {
				e.stopPropagation();
				selectedId = selectedId === d.id ? null : d.id;
			})
			.append("title")
			.text((d) => `${categoryLabel(d.id)} · ${fmtAnnualPct(d.trend)}/yr — click to trace influence`);

		const labelled = new Set(
			[...lay.nodes].sort((a, b) => b.vol - a.vol).slice(0, 16).map((n) => n.id),
		);
		if (selected) {
			labelled.add(selected);
			nb!.up.forEach((id) => labelled.add(id));
			nb!.down.forEach((id) => labelled.add(id));
		}
		root.append("g")
			.selectAll("text")
			.data(lay.nodes.filter((n) => labelled.has(n.id)))
			.join("text")
			.attr("x", (d) => d.x!)
			.attr("y", (d) => d.y! - (2.5 + Math.max(0, d.vol) * 0.8) - 3)
			.attr("text-anchor", "middle")
			.attr("font-family", "var(--font-mono)")
			.attr("font-size", "8.5px")
			.attr("font-weight", "700")
			.attr("fill", (d) => (inFocus(d.id) ? "var(--on-surface-variant)" : "var(--outline-variant)"))
			.attr("pointer-events", "none")
			.text((d) => { const l = categoryLabel(d.id); return l.length > 20 ? l.slice(0, 18) + '…' : l; });

		svg.on("click", () => { selectedId = null; });

		const zoom = d3.zoom<SVGSVGElement, unknown>()
			.scaleExtent([0.5, 6])
			.on("zoom", (e) => root.attr("transform", e.transform));
		svg.call(zoom);
	}

	let selectedCat = $derived(
		selectedId && data ? data.categories.find((c) => c.id === selectedId) ?? null : null,
	);
	let selectedIn = $derived(
		selectedId ? visibleEdges.filter((e) => e.target === selectedId).sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight)) : [],
	);
	let selectedOut = $derived(
		selectedId ? visibleEdges.filter((e) => e.source === selectedId).sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight)) : [],
	);
</script>

<svelte:head>
	<title>Causal Trends — arXiv Explorer</title>
	<meta name="description" content="A Granger-causal influence map of arXiv research categories — trace what drives growth in each field." />
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
	<header class="mb-10">
		<p class="label-caps mb-3">Poisson-lag Granger regression · Graph-restricted</p>
		<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface border-b-2 border-primary pb-3">Causal trends</h1>
		<p class="mt-2 max-w-2xl font-mono text-sm text-on-surface-variant">
			Arrows show lagged influence between categories. Click a node to trace
			what drives it — and what it drives. Node size = publication volume,
			color = growth direction.
		</p>
	</header>

	{#if loading}
		<div class="label-caps flex h-[500px] items-center justify-center gap-2">
			Loading graph…
		</div>
	{:else if error}
		<div class="flex h-[500px] items-center justify-center font-mono text-sm text-warning-red">{error}</div>
	{:else if data}
		<div class="mb-4 flex flex-wrap items-center justify-between gap-4">
			<div class="flex flex-wrap items-center gap-4 font-mono text-xs text-on-surface-variant">
				<span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-signal-green"></span> Growing</span>
				<span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-warning-red"></span> Declining</span>
				<span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-outline"></span> Stable</span>
			</div>
			<label class="flex items-center gap-3 font-mono text-xs text-on-surface-variant">
				<span class="label-caps">Confidence ≥ {minProb.toFixed(2)}</span>
				<input
					type="range"
					min="0.9"
					max="1"
					step="0.01"
					bind:value={minProb}
					class="w-36 accent-[var(--primary)]"
				/>
				<span class="w-20 text-right">{visibleEdges.length} edges</span>
			</label>
		</div>

		<div class="overflow-hidden border border-outline/20 bg-surface-container">
			<svg bind:this={svgEl} class="h-[500px] w-full" role="img" aria-label="Causal category graph — click nodes to trace influence, scroll to zoom"></svg>
		</div>

		{#if selectedCat}
			<div class="mt-4 border border-primary/40 bg-surface-container p-5 neon-border">
				<div class="flex flex-wrap items-baseline justify-between gap-3">
					<div>
						<div>
							<span class="font-mono text-lg font-bold text-primary">{selectedCat.id}</span>
							<span class="ml-2 font-mono text-xs text-on-surface-variant">{categoryLabel(selectedCat.id)}</span>
						</div>
						<span class="ml-3 font-mono text-sm" class:text-signal-green={selectedCat.trend > 0} class:text-warning-red={selectedCat.trend < 0}>
							{fmtAnnualPct(selectedCat.trend)}/yr
						</span>
					</div>
					<div class="flex items-center gap-4">
						<a href="{base}/trends/{selectedCat.id}" class="font-mono text-xs font-bold text-primary underline underline-offset-4 decoration-primary/30">
							Open detail →
						</a>
						<button onclick={() => (selectedId = null)} class="label-caps transition-colors hover:text-primary">Clear</button>
					</div>
				</div>
				<div class="mt-3 grid grid-cols-1 gap-4 font-mono text-xs text-on-surface-variant sm:grid-cols-2">
					<div>
						<p class="label-caps mb-1.5">Driven by ({selectedIn.length})</p>
						{#each selectedIn.slice(0, 5) as e}
							<div class="flex justify-between py-0.5">
								<a href="{base}/trends/{e.source}" class="text-on-surface transition-colors hover:text-primary">
									{e.source}<span class="ml-1.5 font-mono text-[10px] text-outline">{categoryLabel(e.source)}</span>
								</a>
								<span class:text-signal-green={e.weight > 0} class:text-warning-red={e.weight < 0}>{e.weight > 0 ? "+" : ""}{e.weight.toFixed(2)}</span>
							</div>
						{:else}
							<p class="text-outline">none at this confidence</p>
						{/each}
					</div>
					<div>
						<p class="label-caps mb-1.5">Drives ({selectedOut.length})</p>
						{#each selectedOut.slice(0, 5) as e}
							<div class="flex justify-between py-0.5">
								<a href="{base}/trends/{e.target}" class="text-on-surface transition-colors hover:text-primary">
									{e.target}<span class="ml-1.5 font-mono text-[10px] text-outline">{categoryLabel(e.target)}</span>
								</a>
								<span class:text-signal-green={e.weight > 0} class:text-warning-red={e.weight < 0}>{e.weight > 0 ? "+" : ""}{e.weight.toFixed(2)}</span>
							</div>
						{:else}
							<p class="text-outline">none at this confidence</p>
						{/each}
					</div>
				</div>
			</div>
		{:else if hoverEdge}
			<div class="mt-4 border border-outline/20 bg-surface-container p-4">
				<span class="font-mono text-sm font-bold text-primary">{hoverEdge.source}</span>
				<span class="ml-1 font-mono text-[10px] text-outline">{categoryLabel(hoverEdge.source)}</span>
				<span class="text-on-surface-variant font-mono"> → </span>
				<span class="font-mono text-sm font-bold text-primary">{hoverEdge.target}</span>
				<span class="ml-1 font-mono text-[10px] text-outline">{categoryLabel(hoverEdge.target)}</span>
				<div class="mt-2 grid grid-cols-2 gap-4 font-mono text-xs text-on-surface-variant">
					<div>Lag coefficient: <span class="text-on-surface">{hoverEdge.weight.toFixed(3)}</span></div>
					<div>Confidence: <span class="text-on-surface">{hoverEdge.prob.toFixed(2)}</span></div>
				</div>
			</div>
		{/if}

		<div class="mt-8 grid grid-cols-1 gap-px bg-outline/20 sm:grid-cols-2 lg:grid-cols-3">
			{#each [...data.categories].sort((a, b) => b.trend - a.trend).slice(0, 6) as cat}
				<a href="{base}/trends/{cat.id}" class="bg-surface p-5 transition-colors hover:bg-surface-container-low">
					<div class="font-mono text-xs font-bold text-primary">{cat.id}</div>
					<div class="mt-0.5 font-mono text-[10px] text-on-surface-variant truncate">{categoryLabel(cat.id)}</div>
					<div class="mt-1 font-mono text-2xl font-bold text-signal-green">{fmtAnnualPct(cat.trend)}</div>
					<div class="label-caps mt-1 text-[10px]">annual growth</div>
				</a>
			{/each}
			{#each [...data.categories].sort((a, b) => a.trend - b.trend).slice(0, 3) as cat}
				<a href="{base}/trends/{cat.id}" class="bg-surface p-5 transition-colors hover:bg-surface-container-low">
					<div class="font-mono text-xs font-bold text-primary">{cat.id}</div>
					<div class="mt-0.5 font-mono text-[10px] text-on-surface-variant truncate">{categoryLabel(cat.id)}</div>
					<div class="mt-1 font-mono text-2xl font-bold text-warning-red">{fmtAnnualPct(cat.trend)}</div>
					<div class="label-caps mt-1 text-[10px]">annual growth</div>
				</a>
			{/each}
		</div>
	{/if}
</div>
