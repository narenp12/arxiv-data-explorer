<script lang="ts">
	import type { PaperResult } from "$lib/utils/db";

	let { paper }: { paper: PaperResult } = $props();
</script>

<a
	href="/papers/{paper.id}"
	class="group block border-b border-line px-1 py-4 transition-colors hover:bg-accent/4"
>
	<div class="mb-1.5 flex items-baseline gap-3">
		<span class="font-mono text-[11px] tracking-wide text-accent">{paper.id}</span>
		{#if paper.year}
			<span class="font-mono text-[11px] text-faint">{paper.year}</span>
		{/if}
		{#if paper.citationCount > 0}
			<span class="font-mono text-[11px] text-faint">{paper.citationCount.toLocaleString()} cit.</span>
		{/if}
	</div>
	<div class="mb-1 text-[15px] leading-snug font-medium text-ink group-hover:underline group-hover:decoration-accent/40 group-hover:underline-offset-4">
		{paper.title}
	</div>
	<div class="truncate text-xs text-faint">
		{paper.authors}
	</div>
</a>
