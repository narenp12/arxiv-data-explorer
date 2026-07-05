<script lang="ts">
	import { page } from "$app/stores";
	import { base } from "$app/paths";

	let concept = $state<{ id: string; name: string; description: string | null; worksCount: number } | null>(null);
	let subConcepts = $state<{ id: string; name: string; worksCount: number }[]>([]);
	let works = $state<{ id: string; title: string; authors: string; year: number | null; isArxiv: boolean; openalexUrl: string }[]>([]);
	let loading = $state(true);

	async function loadConcept() {
		const id = $page.params.id;
		if (!id) return;

		concept = null;
		subConcepts = [];
		works = [];
		loading = true;
		try {
			const [conceptRes, subRes, worksRes] = await Promise.all([
				fetch(`/api/openalex/concepts/${encodeURIComponent(id)}?select=id,display_name,description,works_count`),
				fetch(`/api/openalex/concepts?filter=parent_ids:${encodeURIComponent(id)}&per_page=50&select=id,display_name,works_count&sort=works_count:desc`),
				fetch(`/api/openalex/works?filter=concept.id:${encodeURIComponent(id)}&per_page=25&sort=cited_by_count:desc&select=id,title,authorships,publication_year`),
			]);

			if (conceptRes.ok) {
				const d = await conceptRes.json();
				concept = {
					id,
					name: d.display_name ?? "",
					description: d.description ?? null,
					worksCount: d.works_count ?? 0,
				};
			}

			if (subRes.ok) {
				const d = await subRes.json();
				subConcepts = (d.results ?? []).map((c: Record<string, unknown>) => ({
					id: (c.id as string).replace(/^https?:\/\/openalex\.org\/concepts\//, ""),
					name: (c as { display_name?: string }).display_name ?? "",
					worksCount: (c as { works_count?: number }).works_count ?? 0,
				}));
			}

			if (worksRes.ok) {
				const d = await worksRes.json();
				works = (d.results ?? []).map((w: Record<string, unknown>) => {
					const authorships = (w as { authorships?: Record<string, unknown>[] }).authorships ?? [];
					const doi = (w as { doi?: string | null }).doi ?? null;
					const arxivMatch = doi ? doi.match(/^https?:\/\/doi\.org\/10\.48550\/arXiv\.(.+)$/i) : null;
					const arxivId = arxivMatch ? arxivMatch[1] : null;
					const oaId = (w.id as string).replace(/^https?:\/\/openalex\.org\/works\//, "");
					return {
						id: arxivId ?? oaId,
						title: (w as { title?: string }).title ?? "",
						authors: authorships.map((a) => (a.author as { display_name?: string })?.display_name ?? "").join(", "),
						year: (w as { publication_year?: number | null }).publication_year ?? null,
						isArxiv: !!arxivId,
						openalexUrl: `https://openalex.org/${oaId}`,
					};
				});
			}
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadConcept();
	});
</script>

<svelte:head>
	<title>{concept?.name ?? "Concept"} — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	<nav class="label-caps mb-6">
		<a href="{base}/concepts" class="transition-colors hover:text-primary">Concepts</a>
		<span class="text-outline mx-2">/</span>
		<span class="text-on-surface">{concept?.name ?? "…"}</span>
	</nav>

	{#if loading}
		<div class="label-caps flex items-center gap-2 py-8">
			Loading concept…
		</div>
	{:else if !concept}
		<p class="font-mono text-sm text-on-surface-variant">Concept not found.</p>
	{:else}
		<header class="mb-8">
			<p class="label-caps mb-3">Concept detail</p>
			<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface border-b-2 border-primary pb-3">
				{concept.name}
			</h1>
			{#if concept.description}
				<p class="font-mono text-sm text-on-surface-variant mt-3 max-w-2xl">{concept.description}</p>
			{/if}
			<p class="font-mono text-xs text-on-surface-variant mt-2">{concept.worksCount.toLocaleString()} works</p>
		</header>

		{#if subConcepts.length > 0}
			<section class="mb-10">
				<h2 class="font-display text-xl font-bold text-on-surface mb-4">Sub-concepts</h2>
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-px bg-outline/20">
					{#each subConcepts as sc}
						<a
							href="{base}/concepts/{sc.id}"
							class="block bg-surface-container px-3 py-2 transition-colors hover:bg-surface-container-low"
						>
							<span class="font-mono text-sm text-on-surface">{sc.name}</span>
							<span class="font-mono text-xs text-on-surface-variant ml-2">({sc.worksCount.toLocaleString()})</span>
						</a>
					{/each}
				</div>
			</section>
		{/if}

		<section>
			<h2 class="font-display text-xl font-bold text-on-surface mb-4">Top papers</h2>
			{#if works.length === 0}
				<p class="font-mono text-sm text-on-surface-variant">No papers found for this concept.</p>
			{:else}
				<div class="divide-y divide-outline/20">
					{#each works as w}
						<div class="py-3">
							{#if w.isArxiv}
								<a href="{base}/papers/{w.id}" class="font-mono text-sm font-bold text-on-surface transition-colors hover:text-primary">
									{w.title}
								</a>
							{:else}
								<a href={w.openalexUrl} target="_blank" rel="noopener noreferrer" class="font-mono text-sm font-bold text-on-surface transition-colors hover:text-primary">
									{w.title}
								</a>
							{/if}
							<p class="font-mono text-xs text-on-surface-variant mt-1">
								{w.authors}{#if w.year} · {w.year}{/if}
								{#if !w.isArxiv}<span class="text-outline"> · openalex.org ↗</span>{/if}
							</p>
						</div>
					{/each}
				</div>
			{/if}
		</section>
	{/if}
</div>
