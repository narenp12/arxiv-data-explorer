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
	let hoverEdge = $state<{ source: string; target: string; weight: number; prob: number } | null>(null);

	onMount(async () => {
		try {
			const causalRes = await fetch(`${base}/data/causal_edges.json`);
			if (!causalRes.ok) throw new Error("Failed to load");
			const causal: CausalData = await causalRes.json();

			data = causal;
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
					prob: d.prob,
				};
			})
			.on("mouseleave", () => { hoverEdge = null; });

		g.selectAll("circle")
			.data(nodes)
			.join("circle")
			.attr("r", 5)
			.attr("fill", (d: any) => d.color)
			.attr("stroke", "var(--surface-container)")
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

<div class="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
	<header class="mb-10 border-l-4 border-primary pl-8">
		<p class="label-caps mb-3">Bayesian Poisson VAR · Graph-regularized</p>
		<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface">Causal trends</h1>
		<p class="mt-2 max-w-2xl font-mono text-sm text-on-surface-variant">
			Directed edges show Granger-causal influence between arXiv categories.
			Opacity = posterior probability, color = sign (green positive, red negative).
			Node color = growth rate (green growing, red declining).
		</p>
	</header>

	{#if loading}
		<div class="label-caps flex h-[500px] items-center justify-center gap-2">
			<span class="live-dot animate-pulse"></span>
			Loading…
		</div>
	{:else if error}
		<div class="flex h-[500px] items-center justify-center font-mono text-sm text-warning-red">{error}</div>
	{:else}
		<div class="mb-4 flex flex-wrap items-center gap-4 font-mono text-xs text-on-surface-variant">
			<span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-signal-green"></span> Growing</span>
			<span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-warning-red"></span> Declining</span>
			<span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-outline"></span> Stable</span>
		</div>

		<div class="overflow-hidden border border-outline/20 bg-surface-container">
			<svg bind:this={svgEl} class="h-[500px] w-full" role="img" aria-label="Causal category graph"></svg>
		</div>

		{#if hoverEdge}
			<div class="mt-4 border border-outline/20 bg-surface-container p-4">
				<span class="font-mono text-sm font-bold text-primary">{hoverEdge.source}</span>
				<span class="text-on-surface-variant font-mono"> → </span>
				<span class="font-mono text-sm font-bold text-primary">{hoverEdge.target}</span>
				<div class="mt-2 grid grid-cols-2 gap-4 font-mono text-xs text-on-surface-variant">
					<div>Weight: <span class="text-on-surface">{hoverEdge.weight.toFixed(4)}</span></div>
					<div>P(edge): <span class="text-on-surface">{hoverEdge.prob.toFixed(2)}</span></div>
				</div>
			</div>
		{/if}

		<div class="mt-8 grid grid-cols-1 gap-px bg-outline/20 sm:grid-cols-2 lg:grid-cols-3">
			{#each data?.categories.filter(c => c.trend > 0.01).sort((a, b) => b.trend - a.trend).slice(0, 6) as cat}
				<a href="/trends/{cat.id}" class="bg-surface p-5 transition-colors hover:bg-surface-container-low">
					<div class="font-mono text-xs font-bold text-primary">{cat.id}</div>
					<div class="mt-1 font-mono text-2xl font-bold text-signal-green">+{(cat.trend * 100).toFixed(2)}%</div>
					<div class="label-caps mt-1 text-[10px]">monthly growth</div>
				</a>
			{/each}
			{#each data?.categories.filter(c => c.trend < -0.01).sort((a, b) => a.trend - b.trend).slice(0, 6) as cat}
				<a href="/trends/{cat.id}" class="bg-surface p-5 transition-colors hover:bg-surface-container-low">
					<div class="font-mono text-xs font-bold text-primary">{cat.id}</div>
					<div class="mt-1 font-mono text-2xl font-bold text-warning-red">{(cat.trend * 100).toFixed(2)}%</div>
					<div class="label-caps mt-1 text-[10px]">monthly growth</div>
				</a>
			{/each}
		</div>
	{/if}
</div>
