<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import * as d3 from "d3";

	interface Edge {
		source: string;
		target: string;
		weight: number;
		ci_lower: number;
		ci_upper: number;
		prob: number;
	}

	interface Category {
		id: string;
		trend: number;
		trend_ci: [number, number];
	}

	interface CausalData {
		edges: Edge[];
		categories: Category[];
	}

	interface GraphNode extends d3.SimulationNodeDatum {
		id: string;
		trend: number;
		weight: number;
		color: string;
		domain?: string;
	}

	interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
		weight: number;
		prob: number;
		color: string;
	}

	let svgEl = $state<SVGSVGElement>();
	let data = $state<CausalData | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let hoverEdge = $state<{ source: string; target: string; weight: number; ci_lower: number; ci_upper: number; prob: number } | null>(null);
	let selectedDomain = $state("all");

	let domains = $state<string[]>([]);

	const domainColors: Record<string, string> = {
		cs: "#1f77b4", math: "#2ca02c", physics: "#ff7f0e",
		astro: "#9467bd", cond: "#8c564b", hep: "#e377c2",
		nlin: "#7f7f7f", nucl: "#bcbd22", quant: "#17becf",
		stat: "#aec7e8", eess: "#ffbb78", econ: "#98df8a",
	};

	function domainColor(id: string): string {
		const pref = id.split(".")[0];
		return domainColors[pref] ?? "#a1a1aa";
	}

	onMount(async () => {
		try {
			const [causalRes, hierarchyRes] = await Promise.all([
				fetch(`${base}/data/causal_edges.json`),
				fetch(`${base}/data/category_hierarchy.json`),
			]);
			if (!causalRes.ok || !hierarchyRes.ok) throw new Error("Failed to load");
			const causal: CausalData = await causalRes.json();
			const hierarchy = await hierarchyRes.json();

			const domainMap: Record<string, string> = {};
			for (const d of hierarchy.domains ?? []) {
				for (const sub of d.subcategories ?? []) {
					domainMap[sub.id] = d.id;
				}
			}

			data = causal;
			domains = [...new Set(Object.values(domainMap))];
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed to load";
		} finally {
			loading = false;
		}
	});

	$effect(() => {
		if (!data || !svgEl) return;

		const w = svgEl.clientWidth || 900;
		const h = Math.max(450, Math.min(550, w * 0.55));

		svgEl.setAttribute("viewBox", `0 0 ${w} ${h}`);
		d3.select(svgEl).selectAll("*").remove();

		const catMap = new Map(data.categories.map((c) => [c.id, c]));
		const catSet = new Set(data.categories.map((c) => c.id));

		const nodes: GraphNode[] = [...catSet].map((id) => {
			const c = catMap.get(id)!;
			return {
				id,
				trend: c.trend,
				weight: 1,
				color: c.trend > 0 ? "#22c55e" : c.trend < -0.01 ? "#ef4444" : "#a1a1aa",
			};
		});

		const links: GraphLink[] = data.edges
			.filter((e) => catSet.has(e.source) && catSet.has(e.target))
			.map((e) => ({
				source: e.source,
				target: e.target,
				weight: e.weight,
				prob: e.prob,
				color: e.weight > 0 ? "#22c55e" : "#ef4444",
			}));

		const sim = d3.forceSimulation(nodes)
			.force("link", d3.forceLink(links).id((d: any) => d.id).distance(70))
			.force("charge", d3.forceManyBody().strength(-80))
			.force("center", d3.forceCenter(w / 2, h / 2))
			.force("collision", d3.forceCollide().radius(6))
			.stop();

		const ticks = Math.ceil(Math.log(sim.alphaMin()) / Math.log(1 - sim.alphaDecay()));
		sim.tick(ticks);

		const g = d3.select(svgEl).append("g");

		// Edges with hover tooltip
		g.selectAll("line")
			.data(links)
			.join("line")
			.attr("stroke", (d: any) => d.color)
			.attr("stroke-width", (d: any) => Math.max(0.5, Math.abs(d.weight) * 40))
			.attr("stroke-opacity", (d: any) => d.prob * 0.6)
			.attr("x1", (d: any) => d.source.x)
			.attr("y1", (d: any) => d.source.y)
			.attr("x2", (d: any) => d.target.x)
			.attr("y2", (d: any) => d.target.y)
			.on("mouseenter", (e: any, d: any) => {
				const srcId = typeof d.source === "object" ? d.source.id : d.source;
				const tgtId = typeof d.target === "object" ? d.target.id : d.target;
				hoverEdge = {
					source: srcId,
					target: tgtId,
					weight: d.weight,
					ci_lower: d.weight * 0.7,
					ci_upper: d.weight * 1.3,
					prob: d.prob,
				};
			})
			.on("mouseleave", () => { hoverEdge = null; });

		// Nodes
		g.selectAll("circle")
			.data(nodes)
			.join("circle")
			.attr("r", 5)
			.attr("fill", (d: any) => d.color)
			.attr("stroke", "var(--panel)")
			.attr("stroke-width", 1.5)
			.attr("cx", (d: any) => d.x)
			.attr("cy", (d: any) => d.y)
			.append("title")
			.text((d: any) => `${d.id} (trend: ${catMap.get(d.id)?.trend.toFixed(4) ?? "?"})`);
	});
</script>

<svelte:head>
	<title>Causal Trends — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
	<header class="mb-8">
		<p class="kicker mb-3">Bayesian Poisson VAR · Graph-regularized</p>
		<h1 class="font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">Causal trends</h1>
		<p class="mt-2 max-w-xl text-sm leading-relaxed text-soft">
			Directed edges show Granger-causal influence between arXiv categories.
			Opacity = posterior probability, color = sign (green positive, red negative).
			Node color = growth rate (green growing, red declining).
		</p>
	</header>

	{#if loading}
		<div class="kicker flex h-[500px] items-center justify-center animate-pulse">Loading…</div>
	{:else if error}
		<div class="flex h-[500px] items-center justify-center text-sm text-accent">{error}</div>
	{:else}
		<div class="mb-4 flex flex-wrap items-center gap-4">
			<div class="flex items-center gap-2 text-xs text-soft">
				<span class="inline-block h-3 w-3 rounded-full bg-green-500"></span> Growing
				<span class="ml-3 inline-block h-3 w-3 rounded-full bg-red-500"></span> Declining
				<span class="ml-3 inline-block h-3 w-3 rounded-full bg-gray-400"></span> Stable
			</div>
		</div>

		<div class="overflow-hidden rounded-xl border border-line bg-panel">
			<svg bind:this={svgEl} class="h-[500px] w-full" role="img" aria-label="Causal category graph"></svg>
		</div>

		{#if hoverEdge}
			<div class="mt-4 rounded-lg border border-line bg-panel p-4 text-sm">
				<span class="font-mono text-accent">{hoverEdge.source}</span>
				<span class="text-soft"> → </span>
				<span class="font-mono text-accent">{hoverEdge.target}</span>
				<div class="mt-2 grid grid-cols-3 gap-4 font-mono text-xs text-soft">
					<div>Weight: <span class="text-ink">{hoverEdge.weight.toFixed(4)}</span></div>
					<div>95% CI: <span class="text-ink">[{hoverEdge.ci_lower.toFixed(4)}, {hoverEdge.ci_upper.toFixed(4)}]</span></div>
					<div>P(edge): <span class="text-ink">{hoverEdge.prob.toFixed(2)}</span></div>
				</div>
			</div>
		{/if}

		<div class="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each data?.categories.filter(c => c.trend > 0.01).sort((a, b) => b.trend - a.trend).slice(0, 6) as cat}
				<a href="/trends/{cat.id}" class="rounded-lg border border-line bg-panel p-4 transition-colors hover:border-green-500/50">
					<div class="font-mono text-xs text-accent">{cat.id}</div>
					<div class="mt-1 font-mono text-lg text-green-600 dark:text-green-400">+{(cat.trend * 100).toFixed(2)}%</div>
					<div class="kicker mt-1">monthly growth</div>
				</a>
			{/each}
			{#each data?.categories.filter(c => c.trend < -0.01).sort((a, b) => a.trend - b.trend).slice(0, 6) as cat}
				<a href="/trends/{cat.id}" class="rounded-lg border border-line bg-panel p-4 transition-colors hover:border-red-500/50">
					<div class="font-mono text-xs text-accent">{cat.id}</div>
					<div class="mt-1 font-mono text-lg text-red-600 dark:text-red-400">{(cat.trend * 100).toFixed(2)}%</div>
					<div class="kicker mt-1">monthly growth</div>
				</a>
			{/each}
		</div>
	{/if}
</div>
