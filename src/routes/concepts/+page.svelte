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
		<p class="label-caps mb-3 text-secondary">OpenAlex concept hierarchy</p>
		<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface">
			Browse by concept
		</h1>
	</header>

	{#if loading}
		<div class="flex items-center gap-2 text-secondary py-8">
			<span class="inline-block w-2 h-2 rounded-full bg-primary animate-pulse"></span>
			<span class="text-sm">Loading concepts…</span>
		</div>
	{:else if topConcepts.length === 0}
		<p class="text-secondary text-sm">No concepts loaded. OpenAlex might be unavailable.</p>
	{:else}
		<p class="text-xs text-secondary mb-6 uppercase tracking-wider">
			Top-level research fields — click to explore sub-concepts
		</p>
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
			{#each topConcepts as concept}
				<a
					href={`${base}/concepts/${concept.id}`}
					class="block rounded border border-outline bg-surface-container px-4 py-3 hover:bg-surface-container-low transition-colors"
				>
					<span class="text-sm font-bold text-on-surface">{concept.name}</span>
					<span class="block text-xs text-secondary mt-1">
						{concept.worksCount.toLocaleString()} works
					</span>
				</a>
			{/each}
		</div>
	{/if}
</div>
