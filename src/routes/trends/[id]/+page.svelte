<script lang="ts">
	import { page } from "$app/stores";
	import { base } from "$app/paths";
	import * as d3 from "d3";
	import {
		fmtAnnualPct,
		annualPct,
		monthDate,
		type CausalData,
		type CausalCategory,
		type CausalEdge,
		type DynamicsData,
	} from "$lib/utils/trends";
	import { categoryLabel } from "$lib/utils/categories";

	let detail = $state<CausalCategory | null>(null);
	let observed = $state<number[] | null>(null);
	let startMonth = $state("2007-06");
	let incomingEdges = $state<CausalEdge[]>([]);
	let outgoingEdges = $state<CausalEdge[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let chartSvg = $state<SVGSVGElement>();
	let requestSeq = 0;

	$effect(() => {
		const id = $page.params.id ?? "";
		if (!id) { error = "No category specified"; loading = false; return; }

		loading = true;
		error = null;
		const seq = ++requestSeq;

		Promise.all([
			fetch(`${base}/data/causal_edges.json`).then((r) => {
				if (!r.ok) throw new Error("Failed to load causal data");
				return r.json() as Promise<CausalData>;
			}),
			fetch(`${base}/data/category_dynamics.json`).then((r) => {
				if (!r.ok) throw new Error("Failed to load category dynamics");
				return r.json() as Promise<DynamicsData>;
			}),
		]).then(([causal, dyn]) => {
			if (seq !== requestSeq) return;
			startMonth = dyn.meta.start;
			observed = dyn.series[id] ?? null;
			detail = causal.categories.find((c) => c.id === id) ?? null;
			if (!observed && !detail) {
				error = "Category not found";
				return;
			}
			incomingEdges = causal.edges.filter((e) => e.target === id).sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));
			outgoingEdges = causal.edges.filter((e) => e.source === id).sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));
		}).catch((e) => { if (seq === requestSeq) error = e instanceof Error ? e.message : "Failed"; })
		.finally(() => { if (seq === requestSeq) loading = false; });
	});

	$effect(() => {
		if (!observed || !chartSvg) return;
		drawChart(observed, detail, startMonth, chartSvg);
	});

	function drawChart(
		counts: number[],
		cat: CausalCategory | null,
		start: string,
		el: SVGSVGElement,
	) {
		const w = el.clientWidth || 700;
		const h = 280;
		const margin = { top: 16, right: 16, bottom: 28, left: 48 };

		el.setAttribute("viewBox", `0 0 ${w} ${h}`);
		d3.select(el).selectAll("*").remove();

		const n = counts.length;
		const dates = counts.map((_, i) => monthDate(start, i));
		const x = d3.scaleTime()
			.domain([dates[0], dates[n - 1]])
			.range([margin.left, w - margin.right]);
		const yMax = d3.max(counts)! * 1.1;
		const y = d3.scaleLinear().domain([0, yMax]).range([h - margin.bottom, margin.top]);

		const svg = d3.select(el);

		svg.append("g")
			.attr("transform", `translate(0,${h - margin.bottom})`)
			.call(d3.axisBottom(x).ticks(8).tickFormat((d) => String((d as Date).getFullYear())))
			.attr("font-family", "var(--font-mono)")
			.attr("color", "var(--on-surface-variant)");

		svg.append("g")
			.attr("transform", `translate(${margin.left},0)`)
			.call(d3.axisLeft(y).ticks(5).tickFormat((v) => d3.format("~s")(v as number)))
			.attr("font-family", "var(--font-mono)")
			.attr("color", "var(--on-surface-variant)");

		// Fitted exponential trend + CI band, anchored at the fit's centroid
		if (cat?.anchor) {
			const [tbar, zbar] = cat.anchor;
			const t = d3.range(n);
			const curve = (slope: number) => t.map((ti) => Math.max(0, Math.expm1(zbar + slope * (ti - tbar))));

			const lo = curve(cat.trend_ci[0]);
			const hi = curve(cat.trend_ci[1]);
			svg.append("path")
				.datum(t)
				.attr("fill", "var(--primary)")
				.attr("fill-opacity", 0.08)
				.attr("d", d3.area<number>()
					.x((ti) => x(dates[ti]))
					.y0((ti) => y(Math.min(lo[ti], yMax)))
					.y1((ti) => y(Math.min(hi[ti], yMax))));

			const fit = curve(cat.trend);
			svg.append("path")
				.datum(t)
				.attr("fill", "none")
				.attr("stroke", "var(--secondary)")
				.attr("stroke-width", 1)
				.attr("stroke-dasharray", "4 3")
				.attr("d", d3.line<number>()
					.x((ti) => x(dates[ti]))
					.y((ti) => y(Math.min(fit[ti], yMax))));
		}

		svg.append("path")
			.datum(counts)
			.attr("fill", "none")
			.attr("stroke", "var(--primary)")
			.attr("stroke-width", 1.5)
			.attr("d", d3.line<number>()
				.x((_, i) => x(dates[i]))
				.y((v) => y(v)));
	}
</script>

<svelte:head>
	<title>{categoryLabel($page.params.id ?? "")} ({$page.params.id ?? "Category"}) — arXiv Explorer</title>
	<meta name="description" content="Monthly submission dynamics and causal drivers for {categoryLabel($page.params.id ?? "")} (arXiv {$page.params.id})." />
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	<a href="{base}/trends" class="label-caps mb-6 inline-flex items-center gap-1 transition-colors hover:text-primary">← Causal trends</a>

	{#if loading}
		<div class="label-caps flex items-center justify-center gap-2 py-20">
			Loading dynamics…
		</div>
	{:else if error}
		<div class="py-20 text-center">
			<p class="font-display text-2xl font-bold text-on-surface">Not found</p>
			<p class="label-caps mt-2">{error}</p>
			<a href="{base}/trends" class="label-caps mt-4 inline-block text-primary underline underline-offset-4 decoration-primary/30">← Back to trends</a>
		</div>
	{:else}
		<header class="mb-8 flex flex-wrap items-end justify-between gap-4">
			<div>
				<p class="label-caps mb-3">Category dynamics · since {startMonth}</p>
				<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface border-b-2 border-primary pb-3">{$page.params.id}</h1>
				<p class="mt-0.5 font-mono text-sm text-on-surface-variant">{categoryLabel($page.params.id ?? "")}</p>
				{#if detail}
					<p class="mt-2 font-mono text-sm text-on-surface-variant">
						<span class="font-bold" class:text-signal-green={detail.trend > 0} class:text-warning-red={detail.trend < 0}>
							{fmtAnnualPct(detail.trend)}
						</span> per year
						<span class="text-outline">
							[{annualPct(detail.trend_ci[0]).toFixed(1)}, {annualPct(detail.trend_ci[1]).toFixed(1)}]
						</span>
					</p>
				{:else}
					<p class="mt-2 font-mono text-sm text-on-surface-variant">Legacy category — no trend model fitted.</p>
				{/if}
			</div>
			<a
				href="{base}/trends/compare?ids={$page.params.id}"
				class="border border-outline/20 bg-surface-container px-4 py-2 font-mono text-xs font-bold text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
			>
				+ COMPARE
			</a>
		</header>

		{#if observed}
			<div class="mb-3 flex items-center gap-4 font-mono text-[11px] text-on-surface-variant">
				<span class="inline-flex items-center gap-1.5"><span class="inline-block h-0.5 w-5 bg-primary"></span> observed / month</span>
				{#if detail}
					<span class="inline-flex items-center gap-1.5"><span class="inline-block h-0.5 w-5 border-t border-dashed border-secondary"></span> exponential fit</span>
					<span class="inline-flex items-center gap-1.5"><span class="inline-block h-2 w-5 bg-primary/10"></span> 95% CI</span>
				{/if}
			</div>
			<div class="mb-10 border border-outline/20 bg-surface-container p-4">
				<svg bind:this={chartSvg} class="h-[280px] w-full" role="img" aria-label="Monthly submissions for {categoryLabel($page.params.id ?? '')} ({$page.params.id})"></svg>
			</div>
		{/if}

		{#if detail}
			<div class="grid grid-cols-1 gap-px bg-outline/20 sm:grid-cols-2">
				<div class="bg-surface p-5">
					<p class="label-caps mb-3">What drives {detail.id}</p>
					{#if incomingEdges.length === 0}
						<p class="font-mono text-sm text-outline">No significant incoming influences detected.</p>
					{:else}
						<div class="space-y-px">
							{#each incomingEdges.slice(0, 15) as edge}
								<a href="{base}/trends/{edge.source}" class="block border border-outline/20 bg-surface-container p-3 transition-colors hover:neon-border">
									<div class="flex items-baseline justify-between">
										<span class="font-mono text-sm font-bold text-primary">{edge.source}</span>
										<span class="font-mono text-[10px] text-on-surface-variant truncate ml-2">{categoryLabel(edge.source)}</span>
										<span class="font-mono text-xs" class:text-signal-green={edge.weight > 0} class:text-warning-red={edge.weight < 0}>
											{edge.weight > 0 ? "+" : ""}{edge.weight.toFixed(3)}
										</span>
									</div>
									<div class="mt-1 font-mono text-[11px] text-on-surface-variant">
										lag coef · CI [{edge.ci_lower.toFixed(2)}, {edge.ci_upper.toFixed(2)}]
										· conf {edge.prob.toFixed(2)}
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
								<a href="{base}/trends/{edge.target}" class="block border border-outline/20 bg-surface-container p-3 transition-colors hover:neon-border">
									<div class="flex items-baseline justify-between">
										<span class="font-mono text-sm font-bold text-primary">{edge.target}</span>
										<span class="font-mono text-[10px] text-on-surface-variant truncate ml-2">{categoryLabel(edge.target)}</span>
										<span class="font-mono text-xs" class:text-signal-green={edge.weight > 0} class:text-warning-red={edge.weight < 0}>
											{edge.weight > 0 ? "+" : ""}{edge.weight.toFixed(3)}
										</span>
									</div>
									<div class="mt-1 font-mono text-[11px] text-on-surface-variant">
										lag coef · CI [{edge.ci_lower.toFixed(2)}, {edge.ci_upper.toFixed(2)}]
										· conf {edge.prob.toFixed(2)}
									</div>
								</a>
							{/each}
						</div>
					{/if}
				</div>
			</div>
		{/if}
	{/if}
</div>
