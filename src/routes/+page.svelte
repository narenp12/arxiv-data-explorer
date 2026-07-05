<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import type { NetworkStats } from "$lib/types";
	import CategoryGraph from "$lib/components/CategoryGraph.svelte";
	import { fmtAnnualPct, sparklinePoints, type CausalData, type DynamicsData } from "$lib/utils/trends";
	import { categoryLabel } from "$lib/utils/categories";

	let stats = $state<NetworkStats | null>(null);
	let error = $state(false);
	let pulse = $state<{ id: string; trend: number; points: string }[]>([]);
	let categoryCount = $state(0);

	onMount(async () => {
		try {
			const res = await fetch(`${base}/data/network_stats.json`);
			if (res.ok) {
				stats = await res.json();
			} else {
				error = true;
			}
		} catch {
			error = true;
		}

		try {
			const [causalRes, dynRes] = await Promise.all([
				fetch(`${base}/data/causal_edges.json`),
				fetch(`${base}/data/category_dynamics.json`),
			]);
			if (causalRes.ok && dynRes.ok) {
				const causal: CausalData = await causalRes.json();
				const dyn: DynamicsData = await dynRes.json();
				categoryCount = causal.categories.length;
				pulse = [...causal.categories]
					.sort((a, b) => b.trend - a.trend)
					.slice(0, 5)
					.map((c) => ({
						id: c.id,
						trend: c.trend,
						points: sparklinePoints(dyn.series[c.id] ?? [], 120, 32),
					}));
			}
		} catch {
			// pulse strip simply doesn't render
		}
	});

	function fmt(n: number): string {
		if (n >= 1_000_000) return (n / 1_000_000).toFixed(2).replace(/\.?0+$/, "") + "M";
		if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
		return n.toLocaleString();
	}

	const statCells = $derived([
		{ label: "Papers", value: stats ? fmt(stats.total_papers) : null },
		{ label: "Authors", value: stats ? fmt(stats.authors) : null },
		{ label: "Categories", value: stats ? fmt(stats.categories) : null },
		{ label: "Multi-author", value: stats ? fmt(stats.multi_author_papers) : null },
	]);
</script>

<svelte:head>
	<title>arXiv Explorer — optical laboratory</title>
	<meta name="description" content="Search millions of arXiv papers and explore category networks, co-authorship graphs, and causal research trends." />
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
	<!-- Hero — left-aligned asymmetric -->
	<header class="mb-16">
		<p class="label-caps mb-4 flex items-center gap-2">
			<span class="inline-flex h-2 w-2 items-center justify-center">
				<span class="inline-block h-1 w-1 bg-primary/70"></span>
			</span>
			ARXIV METADATA · 1991 → {new Date().getFullYear()}
		</p>
		<h1 class="font-display max-w-4xl text-[clamp(2.5rem,5vw,4rem)] leading-[1.04] font-bold tracking-tight text-on-surface border-b-2 border-primary pb-3">
			The shape of <span class="text-primary italic">science</span>,<br />one paper at a time.
		</h1>
		<p class="mt-6 max-w-2xl font-body text-sm leading-relaxed text-on-surface-variant">
			Search three million arXiv papers, trace co-authorship networks, and watch
			research fields rise and fall across three decades of metadata.
		</p>
		<div class="mt-8 flex flex-wrap items-center gap-4">
			<a
				href="{base}/papers"
				class="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 font-mono text-xs font-bold text-[#0a0a0a] transition-all hover:opacity-85 active:translate-y-px"
			>
				SCAN PAPERS →
			</a>
			<a href="{base}/about" class="font-mono text-xs font-bold text-on-surface-variant transition-colors hover:text-primary">
				ABOUT THE DATA
			</a>
		</div>
	</header>

	<!-- Bento data cells — signal readout band -->
	<div class="mb-16 grid grid-cols-2 border-y border-outline/30 sm:grid-cols-4">
		{#each statCells as cell, i}
			<div
				class="px-5 py-6 transition-colors hover:bg-surface-container-low {i > 0 ? 'border-l border-outline/30 max-sm:odd:border-l-0' : ''} {i >= 2 ? 'max-sm:border-t max-sm:border-outline/30' : ''}"
			>
				{#if cell.value}
					<div class="font-mono text-3xl font-bold tracking-tight text-on-surface">{cell.value}</div>
				{:else}
					<div class="skeleton h-9 w-20"></div>
				{/if}
				<div class="label-caps mt-1.5 text-[10px]">{cell.label}</div>
			</div>
		{/each}
	</div>

	<!-- Field pulse — fastest-growing categories -->
	{#if pulse.length > 0}
		<section class="mb-16">
			<div class="mb-4 flex items-baseline justify-between border-b border-outline/30 pb-3">
				<div>
					<p class="label-caps mb-1">Field pulse · annual growth</p>
					<h2 class="font-display text-2xl font-bold tracking-tight text-on-surface">Taking off right now</h2>
				</div>
				<a href="{base}/takeoffs" class="font-mono text-xs font-bold text-on-surface-variant transition-colors hover:text-primary">
					ALL {categoryCount} →
				</a>
			</div>
			<div class="grid grid-cols-2 gap-px bg-outline/20 sm:grid-cols-5">
				{#each pulse as cat}
					<a href="{base}/trends/{cat.id}" class="group bg-surface px-4 py-5 transition-colors hover:bg-surface-container-low">
						<div class="font-mono text-xs font-bold text-primary">{cat.id}</div>
						<div class="font-mono text-[9px] text-on-surface-variant truncate">{categoryLabel(cat.id)}</div>
						<div class="mt-1 font-mono text-xl font-bold text-signal-green">{fmtAnnualPct(cat.trend)}</div>
						<svg viewBox="0 0 120 32" class="mt-3 h-8 w-full" preserveAspectRatio="none" aria-hidden="true">
							<polyline
								points={cat.points}
								fill="none"
								stroke="var(--primary)"
								stroke-width="1.5"
								class="opacity-60 transition-opacity group-hover:opacity-100"
							/>
						</svg>
					</a>
				{/each}
			</div>
		</section>
	{/if}

	<!-- Category network panel -->
	<section class="mb-16">
		<div class="mb-4 flex items-baseline justify-between border-b border-outline/30 pb-3">
			<div>
				<p class="label-caps mb-1">Figure 01 · Force-directed</p>
				<h2 class="font-display text-2xl font-bold tracking-tight text-on-surface">
					Category network
				</h2>
			</div>
			<div class="hidden max-w-xs text-right font-mono text-[11px] leading-relaxed text-on-surface-variant sm:block">
				Co-occurrence of {stats ? stats.categories : "—"} arXiv categories.
				Node size = paper count, color = domain.
			</div>
		</div>
		<div class="overflow-hidden border border-outline/20 bg-surface-container">
			<CategoryGraph />
		</div>
	</section>

	<!-- Link panels — border-top accent cards -->
	<div class="grid gap-px bg-outline/20 sm:grid-cols-2">
		<a
			href="{base}/papers"
			class="group bg-surface px-6 py-8 transition-all hover:bg-surface-container-low"
		>
			<p class="label-caps mb-4 font-mono text-[11px] text-primary">01 · Search</p>
			<h3 class="font-display mb-2 text-2xl font-bold tracking-tight text-on-surface">
				Papers <span class="inline-block text-primary transition-transform group-hover:translate-x-1">→</span>
			</h3>
			<p class="font-mono text-sm leading-relaxed text-on-surface-variant">
				Full-text search across millions of titles and author lists, filtered by era.
			</p>
		</a>

		<a
			href="{base}/authors"
			class="group bg-surface px-6 py-8 transition-all hover:bg-surface-container-low"
		>
			<p class="mb-4 font-mono text-[11px] text-primary">02 · Networks</p>
			<h3 class="font-display mb-2 text-2xl font-bold tracking-tight text-on-surface">
				Authors <span class="inline-block text-primary transition-transform group-hover:translate-x-1">→</span>
			</h3>
			<p class="font-mono text-sm leading-relaxed text-on-surface-variant">
				Co-authorship graphs and collaboration patterns across the corpus.
			</p>
		</a>
	</div>
</div>
