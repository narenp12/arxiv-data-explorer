<script lang="ts">
	import type { PaperResult } from "$lib/utils/db";

	let { paper }: { paper: PaperResult } = $props();
</script>

<a
	href="/papers/{paper.id}"
	class="group block border-b border-outline/10 py-3.5 transition-colors hover:bg-surface-container-low"
>
	<div class="mb-0.5 font-mono text-sm leading-snug text-on-surface group-hover:text-primary transition-colors">
		{paper.title}
	</div>
	<div class="flex items-baseline gap-3 font-mono text-xs text-on-surface-variant">
		<span class="truncate">{paper.authors}</span>
		{#if paper.year}
			<span class="shrink-0 text-outline">· {paper.year}</span>
		{/if}
		{#if paper.citationCount > 0}
			<span class="shrink-0 text-outline">· {paper.citationCount.toLocaleString()} cit.</span>
		{/if}
	</div>
</a>
