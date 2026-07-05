<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import AuthorGraph from "$lib/components/AuthorGraph.svelte";

	interface AuthorRank {
		name: string;
		papers: number;
		relative: number;
	}

	let authors = $state<AuthorRank[]>([]);
	let loading = $state(true);

	onMount(async () => {
		try {
			const res = await fetch(`${base}/data/author_rankings.json`);
			if (res.ok) authors = await res.json();
		} catch {
			// leave empty
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>Authors — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-5xl px-4 py-14 sm:px-6 lg:px-8">
	<header class="mb-10">
		<p class="label-caps mb-3">Top 50k · co-authorship graph</p>
		<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface border-b-2 border-primary pb-3">Authors</h1>
		<p class="mt-2 max-w-xl font-mono text-sm text-on-surface-variant">
			{loading ? "Loading signal…" : `${authors.length.toLocaleString()} most prolific authors in the corpus`}
		</p>
	</header>

	<section class="mb-10">
		<div class="mb-3 flex items-baseline justify-between border-b border-outline/30 pb-2">
			<div>
				<p class="label-caps mb-1">Figure 01 · Co-authorship network</p>
				<h2 class="font-display text-xl font-bold tracking-tight text-on-surface">Co-authorship network</h2>
			</div>
			<p class="hidden font-mono text-[11px] text-on-surface-variant sm:block">{authors.length > 0 ? `Top ${authors.length} authors by paper count` : ""}</p>
		</div>
		<AuthorGraph />
	</section>

	{#if loading}
		<div class="label-caps flex items-center justify-center gap-2 py-16">
			Loading graph…
		</div>
	{:else}
		<div class="divide-y divide-outline/20 border-t border-outline/30">
			{#each authors as author, i}
				<a
					href="{base}/authors/{encodeURIComponent(author.name)}"
					class="group flex items-center gap-4 px-3 py-3 transition-colors hover:bg-surface-container-low"
				>
					<span class="w-8 text-right font-mono text-xs text-outline">{i + 1}</span>
					<div class="flex-1 min-w-0">
						<div class="truncate font-mono text-sm font-bold text-on-surface group-hover:text-primary">
							{author.name}
						</div>
					</div>
					<div class="flex items-baseline gap-3">
						<span class="font-mono text-xs text-on-surface-variant">{author.papers.toLocaleString()} papers</span>
						<div class="h-1 w-20 overflow-hidden bg-surface-container-high">
							<div
								class="h-full bg-primary/60"
								style="width: {author.relative}%"
							></div>
						</div>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</div>
