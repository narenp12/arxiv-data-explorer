<script lang="ts">
	import { page } from "$app/stores";
	import { base } from "$app/paths";
	import * as d3 from "d3";

	interface Edge { source: string; target: string; weight: number; ci_lower: number; ci_upper: number; prob: number; }
	interface Category { id: string; trend: number; trend_ci: [number, number]; }
	interface Dynamics { [cat: string]: { months: number[]; observed: number[]; } }

	let detail = $state<Category | null>(null);
	let incomingEdges = $state<Edge[]>([]);
	let outgoingEdges = $state<Edge[]>([]);
	let dynamics = $state<Dynamics | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let chartSvg = $state<SVGSVGElement>();

	$effect(() => {
		const id = $page.params.id ?? "";
		if (!id) { error = "No category specified"; loading = false; return; }

		loading = true;
		error = null;

		Promise.all([
			fetch(`${base}/data/causal_edges.json`).then(r => r.json()),
			fetch(`${base}/data/category_dynamics.json`).then(r => r.json()),
		]).then(([causal, dyn]) => {
			dynamics = dyn;
			const cat = causal.categories.find((c: Category) => c.id === id);
			if (cat) detail = cat;
			else error = "Category not found";

			incomingEdges = causal.edges.filter((e: Edge) => e.target === id).sort((a: Edge, b: Edge) => Math.abs(b.weight) - Math.abs(a.weight));
			outgoingEdges = causal.edges.filter((e: Edge) => e.source === id).sort((a: Edge, b: Edge) => Math.abs(b.weight) - Math.abs(a.weight));
		}).catch((e) => { error = e instanceof Error ? e.message : "Failed"; })
		.finally(() => { loading = false; });
	});

	$effect(() => {
		if (!dynamics || !detail || !chartSvg) return;
		const id = $page.params.id!;
		const d = dynamics[id];
		if (!d) return;

		const w = chartSvg.clientWidth || 700;
		const h = 250;
		const margin = { top: 20, right: 20, bottom: 30, left: 50 };

		chartSvg.setAttribute("viewBox", `0 0 ${w} ${h}`);
		d3.select(chartSvg).selectAll("*").remove();

		const x = d3.scaleLinear().domain([0, d.months.length - 1]).range([margin.left, w - margin.right]);
		const y = d3.scaleLinear().domain([0, d3.max(d.observed)! * 1.1]).range([h - margin.bottom, margin.top]);

		const svg = d3.select(chartSvg);

		const dataStartYear = 2007;
		svg.append("g")
			.attr("transform", `translate(0,${h - margin.bottom})`)
			.call(d3.axisBottom(x).ticks(8).tickFormat((_d: d3.NumberValue, i: number) => {
				const monthVal = d.months[Math.round(i)];
				return `${dataStartYear + Math.floor(monthVal / 12)}`;
			}));

		svg.append("g")
			.attr("transform", `translate(${margin.left},0)`)
			.call(d3.axisLeft(y).ticks(5));

		svg.append("path")
			.datum(d.observed.map((v: number, i: number) => [x(i), y(v)]))
			.attr("fill", "none")
			.attr("stroke", "var(--primary)")
			.attr("stroke-width", 1.5)
			.attr("d", d3.line() as any);
	});
</script>

<svelte:head>
	<title>{$page.params.id ?? "Category"} — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	<a href="/trends" class="label-caps mb-6 inline-flex items-center gap-1 transition-colors hover:text-primary">← Causal trends</a>

	{#if loading}
		<div class="label-caps flex items-center justify-center gap-2 py-20">
			<span class="live-dot animate-pulse"></span>
			Loading…
		</div>
	{:else if error}
		<div class="py-20 text-center">
			<p class="font-display text-2xl font-bold text-on-surface">Not found</p>
			<p class="label-caps">{error}</p>
		</div>
	{:else if detail}
		<header class="mb-8 border-l-4 border-primary pl-8">
			<p class="label-caps mb-3">Category dynamics</p>
			<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface">{detail.id}</h1>
			<p class="mt-2 font-mono text-sm text-on-surface-variant">
				Trend: <span class="text-on-surface">{(detail.trend * 100).toFixed(3)}%</span> per month
				<span class="text-outline"> [{(detail.trend_ci[0] * 100).toFixed(3)}, {(detail.trend_ci[1] * 100).toFixed(3)}]</span>
			</p>
		</header>

		<div class="mb-10 border border-outline/20 bg-surface-container p-4">
			<svg bind:this={chartSvg} class="h-[250px] w-full"></svg>
		</div>

		<div class="grid grid-cols-1 gap-px bg-outline/20 sm:grid-cols-2">
			<div class="bg-surface p-5">
				<p class="label-caps mb-3">What drives {detail.id}</p>
				{#if incomingEdges.length === 0}
					<p class="font-mono text-sm text-outline">No significant incoming influences detected.</p>
				{:else}
					<div class="space-y-px">
						{#each incomingEdges.slice(0, 15) as edge}
							<a href="/trends/{edge.source}" class="block border border-outline/20 bg-surface-container p-3 transition-colors hover:neon-border">
								<div class="flex items-baseline justify-between">
									<span class="font-mono text-sm font-bold text-primary">{edge.source}</span>
									<span class="font-mono text-xs" class:text-signal-green={edge.weight > 0} class:text-warning-red={edge.weight < 0}>
										{edge.weight > 0 ? "+" : ""}{(edge.weight * 100).toFixed(2)}%
									</span>
								</div>
								<div class="mt-1 font-mono text-[11px] text-outline">
									CI [{(edge.ci_lower * 100).toFixed(2)}, {(edge.ci_upper * 100).toFixed(2)}]
									· P = {edge.prob.toFixed(2)}
								</div>
							</a>
						{/each}
					</div>
				{/if}
			</div>

			<div class="bg-surface p-5">
				<p class="label-caps mb-3">What {detail.id} drives</p>
				{#if outgoingEdges.length === 0}
					<p class="font-mono text-sm text-outline">No significant outgoing influences detected.</p>
				{:else}
					<div class="space-y-px">
						{#each outgoingEdges.slice(0, 15) as edge}
							<a href="/trends/{edge.target}" class="block border border-outline/20 bg-surface-container p-3 transition-colors hover:neon-border">
								<div class="flex items-baseline justify-between">
									<span class="font-mono text-sm font-bold text-primary">{edge.target}</span>
									<span class="font-mono text-xs" class:text-signal-green={edge.weight > 0} class:text-warning-red={edge.weight < 0}>
										{edge.weight > 0 ? "+" : ""}{(edge.weight * 100).toFixed(2)}%
									</span>
								</div>
								<div class="mt-1 font-mono text-[11px] text-outline">
									CI [{(edge.ci_lower * 100).toFixed(2)}, {(edge.ci_upper * 100).toFixed(2)}]
									· P = {edge.prob.toFixed(2)}
								</div>
							</a>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
