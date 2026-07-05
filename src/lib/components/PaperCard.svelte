<script lang="ts">
	import { base } from "$app/paths";
	import { goto } from "$app/navigation";
	import type { PaperResult } from "$lib/utils/db";
	import { readingList } from "$lib/stores/saved.svelte";

	let { paper }: { paper: PaperResult } = $props();

	let saved = $derived(readingList.has(paper.id));

	function toggleSave(e: MouseEvent) {
		e.preventDefault();
		e.stopPropagation();
		readingList.toggle({
			id: paper.id,
			title: paper.title,
			authors: paper.authors,
			year: paper.year,
			isArxiv: paper.isArxiv,
		});
	}

	function gotoAuthor(e: MouseEvent, authorId: string | undefined) {
		if (!authorId) return;
		e.stopPropagation();
		goto(`${base}/authors/${authorId}`);
	}
</script>

<a
	href={paper.isArxiv ? `/papers/${paper.id}` : paper.s2Url}
	target={paper.isArxiv ? undefined : "_blank"}
	rel={paper.isArxiv ? undefined : "noopener noreferrer"}
	class="group relative block border-b border-outline/10 py-3.5 pr-10 transition-colors hover:bg-surface-container-low"
>
	<div class="mb-0.5 font-mono text-sm leading-snug text-on-surface group-hover:text-primary transition-colors">
		{paper.title}
		{#if !paper.isArxiv}
			<span class="label-caps text-[9px] text-outline">S2 ↗</span>
		{/if}
	</div>
	<div class="flex items-baseline gap-3 font-mono text-xs text-on-surface-variant">
		<span class="truncate">
			{#each paper.authorsWithIds as a, i}
				{#if a.authorId}
					<button
						onclick={(e) => gotoAuthor(e, a.authorId)}
						class="inline text-xs hover:text-primary transition-colors"
					>{a.name}</button>
				{:else}
					<span>{a.name}</span>
				{/if}
				{#if i < paper.authorsWithIds.length - 1}, {/if}
			{/each}
		</span>
		{#if paper.year}
			<span class="shrink-0 text-outline">· {paper.year}</span>
		{/if}
		{#if paper.citationCount > 0}
			<span class="shrink-0 text-outline">· {paper.citationCount.toLocaleString()} cit.</span>
		{/if}
	</div>
	<button
		onclick={toggleSave}
		aria-label={saved ? "Remove from reading list" : "Save to reading list"}
		aria-pressed={saved}
		class="absolute top-1/2 right-2 -translate-y-1/2 p-2 transition-colors {saved ? 'text-primary' : 'text-outline hover:text-on-surface'}"
	>
		<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill={saved ? "currentColor" : "none"} stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z" />
		</svg>
	</button>
</a>
