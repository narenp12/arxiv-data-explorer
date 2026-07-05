<script lang="ts">
	import type { ConceptTag } from "$lib/types";
	import { base } from "$app/paths";

	let { concepts }: { concepts: ConceptTag[] } = $props();

	const LEVEL_COLORS: Record<number, string> = {
		0: "bg-phantom-violet/15 text-phantom-violet border-phantom-violet/30",
		1: "bg-phantom-violet/10 text-phantom-violet/90 border-phantom-violet/25",
		2: "bg-phantom-violet/8 text-phantom-violet/80 border-phantom-violet/20",
		3: "bg-phantom-violet/6 text-phantom-violet/70 border-phantom-violet/15",
		4: "bg-phantom-violet/5 text-phantom-violet/60 border-phantom-violet/10",
		5: "bg-phantom-violet/4 text-phantom-violet/50 border-phantom-violet/8",
	};
</script>

{#if concepts.length > 0}
	<div class="flex flex-wrap gap-1.5">
		{#each concepts as c}
			<a
				href="{base}/concepts/{c.id}"
				class="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] leading-tight transition-colors hover:opacity-80 {LEVEL_COLORS[c.level] ?? LEVEL_COLORS[5]}"
			>
				{c.name}
			</a>
		{/each}
	</div>
{/if}
