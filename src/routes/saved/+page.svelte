<script lang="ts">
	import { readingList } from "$lib/stores/saved.svelte";

	function exportBibtex() {
		const blob = new Blob([readingList.toBibtex()], { type: "application/x-bibtex" });
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = "reading-list.bib";
		a.click();
		URL.revokeObjectURL(url);
	}
</script>

<svelte:head>
	<title>Saved papers — arXiv Explorer</title>
	<meta name="description" content="Your local reading list — saved arXiv papers with BibTeX export." />
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	<header class="mb-10 flex flex-wrap items-end justify-between gap-4 border-l-4 border-primary pl-8">
		<div>
			<p class="label-caps mb-3">Reading list · stored in this browser</p>
			<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface">Saved papers</h1>
		</div>
		{#if readingList.papers.length > 0}
			<button
				onclick={exportBibtex}
				class="border border-outline/20 bg-surface-container px-5 py-2.5 font-mono text-xs font-bold text-on-surface transition-colors hover:border-primary hover:text-primary"
			>
				EXPORT .BIB ({readingList.papers.length})
			</button>
		{/if}
	</header>

	{#if readingList.papers.length === 0}
		<div class="dot-matrix border border-outline/20 bg-surface-container px-6 py-20 text-center">
			<p class="font-display text-2xl font-bold text-on-surface">Nothing saved yet</p>
			<p class="mt-3 font-mono text-sm text-on-surface-variant">
				Hit the bookmark on any search result to build a reading list.
				It lives in this browser — no account needed.
			</p>
			<a
				href="/papers"
				class="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 font-mono text-xs font-bold text-surface transition-all hover:opacity-85 active:translate-y-px"
			>
				SCAN PAPERS →
			</a>
		</div>
	{:else}
		<div class="border-t border-outline/30">
			{#each readingList.papers as paper (paper.id)}
				<div class="group relative border-b border-outline/10 py-3.5 pr-10 transition-colors hover:bg-surface-container-low">
					<a
						href={paper.isArxiv ? `/papers/${paper.id}` : `https://www.semanticscholar.org/paper/${paper.id}`}
						target={paper.isArxiv ? undefined : "_blank"}
						rel={paper.isArxiv ? undefined : "noopener noreferrer"}
						class="mb-0.5 block font-mono text-sm leading-snug text-on-surface transition-colors group-hover:text-primary"
					>
						{paper.title}
					</a>
					<div class="flex items-baseline gap-3 font-mono text-xs text-on-surface-variant">
						<span class="truncate">{paper.authors}</span>
						{#if paper.year}
							<span class="shrink-0 text-outline">· {paper.year}</span>
						{/if}
					</div>
					<button
						onclick={() => readingList.remove(paper.id)}
						aria-label="Remove from reading list"
						class="absolute top-1/2 right-2 -translate-y-1/2 p-2 text-outline transition-colors hover:text-warning-red"
					>
						<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<path d="M3 6h18" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
						</svg>
					</button>
				</div>
			{/each}
		</div>
	{/if}
</div>
