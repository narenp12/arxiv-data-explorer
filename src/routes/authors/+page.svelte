<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";

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

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
	<header class="mb-8">
		<p class="kicker mb-3">Co-authorship networks</p>
		<h1 class="font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">Authors</h1>
		<p class="mt-2 max-w-xl text-sm leading-relaxed text-soft">
			{loading ? "Loading…" : `${authors.length.toLocaleString()} most prolific authors in the corpus`}
		</p>
	</header>

	{#if loading}
		<div class="kicker animate-pulse py-16 text-center">Loading…</div>
	{:else}
		<div class="divide-y divide-line">
			{#each authors as author, i}
				<a
					href="/papers?q={encodeURIComponent(author.name)}"
					class="group flex items-center gap-4 px-2 py-3 transition-colors hover:bg-accent/4"
				>
					<span class="w-8 text-right font-mono text-xs text-faint">{i + 1}</span>
					<div class="flex-1 min-w-0">
						<div class="truncate text-sm font-medium text-ink group-hover:text-accent">
							{author.name}
						</div>
					</div>
					<div class="flex items-baseline gap-3">
						<span class="font-mono text-xs text-soft">{author.papers.toLocaleString()} papers</span>
						<div class="h-1.5 w-20 overflow-hidden rounded-full bg-line">
							<div
								class="h-full rounded-full bg-accent/50"
								style="width: {author.relative}%"
							></div>
						</div>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</div>
