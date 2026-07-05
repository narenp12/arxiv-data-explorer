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
	<title>arXiv Explorer — the shape of science</title>
</svelte:head>

<div class="mx-auto max-w-5xl px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
	<!-- Hero -->
	<header class="mb-14">
		<p class="kicker mb-5">arXiv metadata · 1991 → 2026</p>
		<h1 class="font-display max-w-3xl text-5xl leading-[1.04] font-bold tracking-tight text-ink sm:text-6xl">
			The shape of <span class="text-accent">science</span>, one paper at a&nbsp;time.
		</h1>
		<p class="mt-6 max-w-xl text-base leading-relaxed text-soft">
			Search millions of arXiv papers instantly, and explore the networks that connect
			authors, categories, and three decades of research.
		</p>
		<div class="mt-8 flex flex-wrap items-center gap-4">
			<a
				href="/papers"
				class="rounded-full bg-accent px-6 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-85"
			>
				Search papers
			</a>
			<a href="/about" class="kicker transition-colors hover:text-accent">
				About the data ↗
			</a>
		</div>
	</header>

	<!-- Stats band -->
	<div class="mb-16 grid grid-cols-2 border-y border-line sm:grid-cols-4">
		{#each statCells as cell, i}
			<div class="px-5 py-6 {i > 0 ? 'border-l border-line max-sm:odd:border-l-0' : ''} {i >= 2 ? 'max-sm:border-t max-sm:border-line' : ''}">
				<div class="font-display text-4xl tracking-tight text-ink">{cell.value}</div>
				<div class="kicker mt-1.5">{cell.label}</div>
			</div>
		{/each}
	</div>

	<!-- Category graph -->
	<section class="mb-16">
		<div class="mb-4 flex items-baseline justify-between">
			<div>
				<p class="kicker mb-1.5">Figure 01 · Force-directed</p>
				<h2 class="font-display text-2xl tracking-tight text-ink">Category network</h2>
			</div>
			<p class="hidden max-w-xs text-right text-xs leading-relaxed text-faint sm:block">
				Co-occurrence of {stats ? stats.categories : ""} arXiv categories.
				Node size = paper count, color = domain.
			</p>
		</div>
		<div class="dot-grid overflow-hidden rounded-xl border border-line bg-panel">
			<CategoryGraph />
		</div>
	</section>

	<!-- Link cards -->
	<div class="grid gap-5 sm:grid-cols-2">
		<a
			href="/papers"
			class="group rounded-xl border border-line bg-panel p-6 transition-all hover:-translate-y-0.5 hover:border-accent/50"
		>
			<p class="mb-4 font-mono text-xs text-faint">01 · Search</p>
			<h3 class="font-display mb-2 text-2xl tracking-tight text-ink">
				Papers <span class="inline-block text-accent transition-transform group-hover:translate-x-1">→</span>
			</h3>
			<p class="text-sm leading-relaxed text-soft">
				Full-text search across millions of titles and author lists, filtered by era.
			</p>
		</a>

		<a
			href="/authors"
			class="group rounded-xl border border-line bg-panel p-6 transition-all hover:-translate-y-0.5 hover:border-accent/50"
		>
			<p class="mb-4 font-mono text-xs text-faint">02 · Networks</p>
			<h3 class="font-display mb-2 text-2xl tracking-tight text-ink">
				Authors <span class="inline-block text-accent transition-transform group-hover:translate-x-1">→</span>
			</h3>
			<p class="text-sm leading-relaxed text-soft">
				Co-authorship graphs and collaboration patterns across the corpus.
			</p>
		</a>
	</div>
</div>
