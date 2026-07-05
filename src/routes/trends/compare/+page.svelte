<script lang="ts">
	import { onMount } from "svelte";
	import { page } from "$app/stores";
	import { base } from "$app/paths";
	import { replaceState } from "$app/navigation";
	import * as d3 from "d3";
	import { flip } from "svelte/animate";
	import { quintOut } from "svelte/easing";
	import { fly } from "svelte/transition";
	import { categoryLabel } from "$lib/utils/categories";
	import { fmtAnnualPct, monthDate, type CausalData, type DynamicsData } from "$lib/utils/trends";

	const COLORS = ["var(--primary)", "var(--secondary)", "var(--signal-green)", "var(--warning-red)", "var(--outline)"];
	const MAX_SERIES = 5;

	let causal = $state<CausalData | null>(null);
	let dynamics = $state<DynamicsData | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let selected = $state<string[]>([]);
	let query = $state("");
	let logScale = $state(true);
	let chartSvg = $state<SVGSVGElement>();
	let cursor = $state<{ idx: number; x: number } | null>(null);

	onMount(async () => {
		try {
			const [causalRes, dynRes] = await Promise.all([
				fetch(`${base}/data/causal_edges.json`),
				fetch(`${base}/data/category_dynamics.json`),
			]);
			if (!causalRes.ok || !dynRes.ok) throw new Error("Failed to load data");
			causal = await causalRes.json();
			dynamics = await dynRes.json();
			const ids = ($page.url.searchParams.get("ids") ?? "")
				.split(",")
				.map((s) => s.trim())
				.filter((s) => s && dynamics!.series[s]);
			selected = ids.slice(0, MAX_SERIES);
			if (selected.length === 0) selected = ["cs.AI", "cs.LG"].filter((s) => dynamics!.series[s]);
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed";
		} finally {
			loading = false;
		}
	});

	function syncUrl() {
		replaceState(selected.length ? `?ids=${selected.join(",")}` : window.location.pathname, {});
	}

	function add(id: string) {
		if (selected.includes(id) || selected.length >= MAX_SERIES) return;
		selected = [...selected, id];
		query = "";
		syncUrl();
	}

	function remove(id: string) {
		selected = selected.filter((s) => s !== id);
		syncUrl();
	}

	let suggestions = $derived.by(() => {
		if (!dynamics || !query.trim()) return [];
		const q = query.trim().toLowerCase();
		return Object.keys(dynamics.series)
			.filter((id) => id.toLowerCase().includes(q) && !selected.includes(id))
			.sort((a, b) => a.length - b.length)
			.slice(0, 8);
	});

	let trendOf = $derived((id: string) => causal?.categories.find((c) => c.id === id)?.trend ?? null);

	$effect(() => {
		if (!dynamics || !chartSvg || selected.length === 0) return;
		drawChart(dynamics, selected, logScale, chartSvg);
	});

	function drawChart(dyn: DynamicsData, ids: string[], useLog: boolean, el: SVGSVGElement) {
		const w = el.clientWidth || 800;
		const h = 320;
		const margin = { top: 16, right: 16, bottom: 28, left: 48 };

		el.setAttribute("viewBox", `0 0 ${w} ${h}`);
		d3.select(el).selectAll("*").remove();

		const n = dyn.meta.months;
		const dates = d3.range(n).map((i) => monthDate(dyn.meta.start, i));
		const x = d3.scaleTime().domain([dates[0], dates[n - 1]]).range([margin.left, w - margin.right]);
		const allMax = Math.max(...ids.flatMap((id) => dyn.series[id] ?? [1]));
		const y = useLog
			? d3.scaleSymlog().constant(10).domain([0, allMax * 1.1]).range([h - margin.bottom, margin.top])
			: d3.scaleLinear().domain([0, allMax * 1.1]).range([h - margin.bottom, margin.top]);

		const svg = d3.select(el);
		svg.append("g")
			.attr("transform", `translate(0,${h - margin.bottom})`)
			.call(d3.axisBottom(x).ticks(8).tickFormat((d) => String((d as Date).getFullYear())))
			.attr("font-family", "var(--font-mono)")
			.attr("color", "var(--on-surface-variant)");
		svg.append("g")
			.attr("transform", `translate(${margin.left},0)`)
			.call(d3.axisLeft(y).ticks(5, "~s"))
			.attr("font-family", "var(--font-mono)")
			.attr("color", "var(--on-surface-variant)");

		ids.forEach((id, i) => {
			const series = dyn.series[id];
			if (!series) return;
			svg.append("path")
				.datum(series)
				.attr("fill", "none")
				.attr("stroke", COLORS[i % COLORS.length])
				.attr("stroke-width", 1.5)
				.attr("d", d3.line<number>().x((_, j) => x(dates[j])).y((v) => y(v)));
		});

		// synced hover cursor
		const rule = svg.append("line")
			.attr("stroke", "var(--outline)")
			.attr("stroke-width", 1)
			.attr("stroke-dasharray", "2 2")
			.attr("y1", margin.top)
			.attr("y2", h - margin.bottom)
			.style("display", "none");

		svg.append("rect")
			.attr("x", margin.left)
			.attr("y", margin.top)
			.attr("width", w - margin.left - margin.right)
			.attr("height", h - margin.top - margin.bottom)
			.attr("fill", "transparent")
			.on("mousemove", (e: MouseEvent) => {
				const [mx] = d3.pointer(e);
				const idx = Math.max(0, Math.min(n - 1, d3.bisectCenter(dates.map((d) => +d), +x.invert(mx))));
				cursor = { idx, x: x(dates[idx]) };
				rule.style("display", null).attr("x1", x(dates[idx])).attr("x2", x(dates[idx]));
			})
			.on("mouseleave", () => {
				cursor = null;
				rule.style("display", "none");
			});
	}
</script>

<svelte:head>
	<title>Compare categories — arXiv Explorer</title>
	<meta name="description" content="Overlay monthly submission counts for up to five arXiv categories." />
</svelte:head>

<div class="mx-auto max-w-5xl px-4 py-14 sm:px-6 lg:px-8">
	<a href="{base}/trends" class="label-caps mb-6 inline-flex items-center gap-1 transition-colors hover:text-primary">← Causal trends</a>

	<header class="mb-10">
		<p class="label-caps mb-3">Overlay · up to {MAX_SERIES} categories</p>
		<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface border-b-2 border-primary pb-3">Compare</h1>
	</header>

	{#if loading}
		<div class="label-caps flex items-center justify-center gap-2 py-20">
			Loading data…
		</div>
	{:else if error}
		<div class="py-20 text-center font-mono text-sm text-warning-red">{error}</div>
	{:else if dynamics}
		<div class="mb-6 flex flex-wrap items-center gap-2">
			{#each selected as id, i (id)}
				<span animate:flip={{ duration: 300, easing: quintOut }} class="inline-flex items-center gap-2 border border-outline/30 bg-surface-container px-3 py-1.5 font-mono text-xs font-bold text-on-surface">
					<span class="h-2 w-2 rounded-full" style="background: {COLORS[i % COLORS.length]}"></span>
					{id}<span class="ml-0.5 font-normal text-outline">{categoryLabel(id)}</span>
					{#if trendOf(id) !== null}
						<span class="font-normal text-on-surface-variant">{fmtAnnualPct(trendOf(id)!)}/yr</span>
					{/if}
					<button onclick={() => remove(id)} aria-label="Remove {id}" class="text-outline transition-colors hover:text-warning-red">×</button>
				</span>
			{/each}

			{#if selected.length < MAX_SERIES}
				<div class="relative">
					<input
						bind:value={query}
						placeholder="+ add category"
						class="w-40 border border-outline/20 bg-surface px-3 py-1.5 font-mono text-xs text-on-surface transition-colors placeholder:text-outline focus:border-primary focus:outline-none"
					/>
					{#if suggestions.length > 0}
						<ul class="absolute top-full left-0 z-20 mt-1 w-48 border border-outline/30 bg-surface-container shadow-lg">
							{#each suggestions as s (s)}
								<li in:fly={{ y: -4, duration: 120, easing: quintOut }}>
									<button onclick={() => add(s)} class="w-full px-3 py-1.5 text-left font-mono text-xs text-on-surface transition-colors hover:bg-surface-container-high hover:text-primary">
										<div>{s}</div>
										<div class="text-[10px] text-outline">{categoryLabel(s)}</div>
									</button>
								</li>
							{/each}
						</ul>
					{/if}
				</div>
			{/if}

			<label class="ml-auto flex items-center gap-2 font-mono text-xs text-on-surface-variant">
				<input type="checkbox" bind:checked={logScale} class="accent-[var(--primary)]" />
				log scale
			</label>
		</div>

		{#if selected.length === 0}
			<div class="border border-outline/20 bg-surface-container py-20 text-center">
				<p class="font-mono text-sm text-on-surface-variant">Add a category to start comparing.</p>
			</div>
		{:else}
			<div class="border border-outline/20 bg-surface-container p-4">
				<svg bind:this={chartSvg} class="h-[320px] w-full" role="img" aria-label="Monthly submissions comparison"></svg>
			</div>

			<div class="mt-3 flex min-h-8 flex-wrap items-center gap-x-6 gap-y-1 font-mono text-xs text-on-surface-variant">
				{#if cursor}
					<span class="label-caps">{monthDate(dynamics.meta.start, cursor.idx).toLocaleDateString("en", { year: "numeric", month: "short" })}</span>
					{#each selected as id, i (id)}
						<span animate:flip={{ duration: 300, easing: quintOut }} class="inline-flex items-center gap-1.5">
							<span class="h-2 w-2 rounded-full" style="background: {COLORS[i % COLORS.length]}"></span>
							<span class="flex flex-col leading-tight">
								<span>{categoryLabel(id)}</span>
								<span class="text-outline">{id}: <span class="font-bold text-on-surface">{(dynamics.series[id]?.[cursor.idx] ?? 0).toLocaleString()}</span></span>
							</span>
						</span>
					{/each}
				{:else}
					<span class="text-outline">hover the chart for monthly values</span>
				{/if}
			</div>
		{/if}
	{/if}
</div>
