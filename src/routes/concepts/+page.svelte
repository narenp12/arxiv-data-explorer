<script lang="ts">
	import { base } from "$app/paths";

	let topConcepts = $state<{ id: string; name: string; worksCount: number }[]>([]);
	let loading = $state(true);

	$effect(() => {
		fetch("/api/openalex/concepts?per_page=25&sort=works_count:desc&filter=level:0&select=id,display_name,works_count")
			.then((r) => r.ok ? r.json() : { results: [] })
			.then((d) => {
				topConcepts = (d.results ?? []).map((c: Record<string, unknown>) => ({
					id: (c.id as string).replace(/^https?:\/\/openalex\.org\/concepts\//, ""),
					name: (c as { display_name?: string }).display_name ?? "",
					worksCount: (c as { works_count?: number }).works_count ?? 0,
				}));
			})
			.finally(() => { loading = false; });
	});
</script>

<svelte:head>
	<title>Concepts — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	<header class="mb-10 border-l-4 border-primary pl-8">
		<p class="label-caps mb-3 text-on-surface-variant">OpenAlex concept hierarchy</p>
		<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface">
			Browse by concept
		</h1>
	</header>

	{#if loading}
		<div class="label-caps flex items-center gap-2 py-8">
			<span class="live-dot animate-pulse"></span>
			Loading concepts…
		</div>
	{:else if topConcepts.length === 0}
		<p class="font-mono text-sm text-on-surface-variant">No concepts loaded. OpenAlex might be unavailable.</p>
	{:else}
		<p class="label-caps mb-6">
			Top-level research fields — click to explore sub-concepts
		</p>
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-px bg-outline/20">
			{#each topConcepts as concept}
				<a
					href={`${base}/concepts/${concept.id}`}
					class="block bg-surface-container px-4 py-3 transition-colors hover:bg-surface-container-low"
				>
					<span class="font-mono text-sm font-bold text-on-surface">{concept.name}</span>
					<span class="font-mono text-xs text-on-surface-variant ml-2">
						{concept.worksCount.toLocaleString()} works
					</span>
				</a>
			{/each}
		</div>
	{/if}
</div>
