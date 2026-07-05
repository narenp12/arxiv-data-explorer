<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import type { NetworkStats } from "$lib/types";

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
</script>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
	<!-- Hero -->
	<div class="mb-16 text-center">
		<div class="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600 shadow-lg">
			<span class="text-2xl font-bold text-white">A</span>
		</div>
		<h1 class="mb-4 text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl dark:text-slate-100">
			arXiv Data Explorer
		</h1>
		<p class="mx-auto max-w-2xl text-lg text-slate-600 dark:text-slate-400">
			Explore the arXiv research corpus through interactive visualizations of paper metadata, author networks, and category relationships.
		</p>
	</div>

	<!-- Stats row -->
	<div class="mb-16 grid grid-cols-2 gap-4 sm:grid-cols-4">
		<div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950">
			<div class="mb-1 text-2xl font-bold text-slate-900 dark:text-slate-100">
				{stats ? fmt(stats.total_papers) : "—"}
			</div>
			<div class="text-sm text-slate-500 dark:text-slate-400">Papers</div>
		</div>
		<div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950">
			<div class="mb-1 text-2xl font-bold text-slate-900 dark:text-slate-100">
				{stats ? fmt(stats.authors) : "—"}
			</div>
			<div class="text-sm text-slate-500 dark:text-slate-400">Authors</div>
		</div>
		<div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950">
			<div class="mb-1 text-2xl font-bold text-slate-900 dark:text-slate-100">
				{stats ? fmt(stats.categories) : "—"}
			</div>
			<div class="text-sm text-slate-500 dark:text-slate-400">Categories</div>
		</div>
		<div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950">
			<div class="mb-1 text-2xl font-bold text-slate-900 dark:text-slate-100">
				{stats ? fmt(stats.multi_author_papers) : "—"}
			</div>
			<div class="text-sm text-slate-500 dark:text-slate-400">Multi-author Papers</div>
		</div>
	</div>

	<!-- Placeholder cards -->
	<div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
		<a href="/categories" class="group rounded-xl border border-slate-200 bg-white p-6 transition-colors hover:border-blue-300 dark:border-slate-800 dark:bg-slate-950 dark:hover:border-blue-700">
			<div class="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950 dark:text-blue-400">
				<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
				</svg>
			</div>
			<h3 class="mb-2 font-semibold text-slate-900 dark:text-slate-100">Category Graph</h3>
			<p class="text-sm text-slate-500 dark:text-slate-400">Explore the hierarchical relationships between arXiv categories.</p>
		</a>

		<a href="/papers" class="group rounded-xl border border-slate-200 bg-white p-6 transition-colors hover:border-blue-300 dark:border-slate-800 dark:bg-slate-950 dark:hover:border-blue-700">
			<div class="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950 dark:text-blue-400">
				<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
					<polyline points="14 2 14 8 20 8" />
					<line x1="16" y1="13" x2="8" y2="13" />
					<line x1="16" y1="17" x2="8" y2="17" />
				</svg>
			</div>
			<h3 class="mb-2 font-semibold text-slate-900 dark:text-slate-100">Search Papers</h3>
			<p class="text-sm text-slate-500 dark:text-slate-400">Search and filter through millions of arXiv papers.</p>
		</a>

		<a href="/authors" class="group rounded-xl border border-slate-200 bg-white p-6 transition-colors hover:border-blue-300 dark:border-slate-800 dark:bg-slate-950 dark:hover:border-blue-700">
			<div class="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950 dark:text-blue-400">
				<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
					<circle cx="9" cy="7" r="4" />
					<path d="M22 21v-2a4 4 0 0 0-3-3.87" />
					<path d="M16 3.13a4 4 0 0 1 0 7.75" />
				</svg>
			</div>
			<h3 class="mb-2 font-semibold text-slate-900 dark:text-slate-100">Author Network</h3>
			<p class="text-sm text-slate-500 dark:text-slate-400">Visualize co-authorship networks and collaboration patterns.</p>
		</a>
	</div>
</div>
