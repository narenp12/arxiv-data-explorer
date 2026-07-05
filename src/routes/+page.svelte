<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import type { NetworkStats } from "$lib/types";
	import CategoryGraph from "$lib/components/CategoryGraph.svelte";

	let stats = $state<NetworkStats | null>(null);
	let error = $state(false);

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
	});

	function fmt(n: number): string {
		if (n >= 1_000_000) return (n / 1_000_000).toFixed(2).replace(/\.?0+$/, "") + "M";
		if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
		return n.toLocaleString();
	}

	const statCells = $derived([
		{ label: "Papers", value: stats ? fmt(stats.total_papers) : "—" },
		{ label: "Authors", value: stats ? fmt(stats.authors) : "—" },
		{ label: "Categories", value: stats ? fmt(stats.categories) : "—" },
		{ label: "Multi-author", value: stats ? fmt(stats.multi_author_papers) : "—" },
	]);
</script>

<svelte:head>
	<title>arXiv Explorer — optical laboratory</title>
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
	<!-- Hero — left-aligned asymmetric -->
	<header class="mb-16 border-l-4 border-primary pl-8">
		<p class="label-caps mb-4 flex items-center gap-2">
			<span class="live-dot animate-pulse"></span>
			ARXIV METADATA · 1991 → 2026
		</p>
		<h1 class="font-display max-w-4xl text-[clamp(2.5rem,5vw,4rem)] leading-[1.04] font-bold tracking-tight text-on-surface">
			The shape of <span class="text-primary italic">science</span>,<br />one paper at a time.
		</h1>
		<p class="mt-6 max-w-2xl font-mono text-sm leading-relaxed text-on-surface-variant">
			Search millions of arXiv papers through a live optical terminal. Explore networks
			that connect authors, categories, and three decades of research.
		</p>
		<div class="mt-8 flex flex-wrap items-center gap-4">
			<a
				href="/papers"
				class="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 font-mono text-xs font-bold text-[#0a0a0a] transition-all hover:opacity-85 active:translate-y-px"
			>
				SCAN PAPERS →
			</a>
			<a href="/about" class="font-mono text-xs font-bold text-on-surface-variant transition-colors hover:text-primary">
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
				<div class="font-mono text-3xl font-bold tracking-tight text-on-surface">{cell.value}</div>
				<div class="label-caps mt-1.5 text-[10px]">{cell.label}</div>
			</div>
		{/each}
	</div>

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
		<div class="overflow-hidden border border-outline/20 bg-surface-container dot-matrix opacity-90">
			<CategoryGraph />
		</div>
	</section>

	<!-- Link panels — border-top accent cards -->
	<div class="grid gap-px bg-outline/20 sm:grid-cols-2">
		<a
			href="/papers"
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
			href="/authors"
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
