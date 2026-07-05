<script lang="ts">
	import { page } from "$app/stores";
	import { base } from "$app/paths";
	import type { AuthorProfile } from "$lib/types";
	import { fetchAuthorProfile } from "$lib/utils/openalex";

	let profile = $state<AuthorProfile | null>(null);
	let loading = $state(true);

	interface AuthorShardEntry { w: number; co: [string, number][]; }
	type AuthorShard = Record<string, AuthorShardEntry>;
	const SHARD_COUNT = 64;

	function fnv1a32(str: string): number {
		let h = 0x811c9dc5;
		for (let i = 0; i < str.length; i++) {
			h ^= str.charCodeAt(i);
			h = Math.imul(h, 0x01000193) >>> 0;
		}
		return h;
	}

	let graphAuthor = $state<{ label: string; weight: number } | null>(null);
	let coauthors = $state<{ name: string; weight: number }[]>([]);
	let graphError = $state<string | null>(null);

	let requestSeq = 0;

	$effect(() => {
		const id = $page.params.id;
		if (!id) { loading = false; return; }
		const seq = ++requestSeq;
		loading = true;
		profile = null;
		graphAuthor = null;
		coauthors = [];
		graphError = null;

		fetchAuthorProfile(id).then((p) => {
			if (seq !== requestSeq) return;
			profile = p;
			if (p) { loading = false; return; }
			const shard = fnv1a32(id) % SHARD_COUNT;
			return fetch(`${base}/data/authors/shard-${shard}.json`).then((r) => {
				if (!r.ok) throw new Error("Failed to load");
				return r.json() as Promise<AuthorShard>;
			}).then((data) => {
				if (seq !== requestSeq) return;
				let matchedName: string | null = null;
				let entry: AuthorShardEntry | undefined = data[id];
				if (entry) {
					matchedName = id;
				} else {
					const key = Object.keys(data).find((k) => k.toLowerCase() === id.toLowerCase());
					if (key) { matchedName = key; entry = data[key]; }
				}
				if (!entry || !matchedName) { graphError = "Author not found"; return; }
				graphAuthor = { label: matchedName, weight: entry.w };
				coauthors = entry.co.slice(0, 20).map(([coName, weight]) => ({ name: coName, weight }));
			});
		}).catch(() => {
			if (seq !== requestSeq) return;
			graphError = "Failed to load profile";
		}).finally(() => {
			if (seq === requestSeq) loading = false;
		});
	});
</script>

<svelte:head>
	<title>{profile?.name ?? graphAuthor?.label ?? "Author"} — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	<a href="{base}/authors" class="label-caps mb-6 inline-flex items-center gap-1 transition-colors hover:text-primary">← All authors</a>

	{#if loading}
		<div class="label-caps flex items-center justify-center gap-2 py-20">
			Loading author…
		</div>
	{:else if !profile && !graphAuthor}
		<div class="py-20 text-center">
			<p class="font-display text-2xl font-bold text-on-surface">Not found</p>
			<p class="label-caps mt-2">{graphError ?? "Author not found."}</p>
		</div>
	{:else if profile}
		<header class="mb-8">
			<p class="label-caps mb-3 text-secondary">Author profile</p>
			<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface border-b-2 border-primary pb-3">
				{profile.name}
			</h1>
			{#if profile.orcid}
				<a
					href="https://orcid.org/{profile.orcid}"
					target="_blank"
					rel="noopener noreferrer"
					class="text-xs text-primary hover:underline mt-1 inline-block"
				>
					ORCID: {profile.orcid}
				</a>
			{/if}
		</header>

		<div class="flex flex-wrap gap-4 mb-8">
			<div class="rounded border border-outline bg-surface-container px-4 py-3 text-center min-w-[100px]">
				<div class="text-2xl font-bold text-on-surface">{profile.worksCount}</div>
				<div class="text-xs text-secondary">Papers</div>
			</div>
			<div class="rounded border border-outline bg-surface-container px-4 py-3 text-center min-w-[100px]">
				<div class="text-2xl font-bold text-on-surface">{profile.citedByCount}</div>
				<div class="text-xs text-secondary">Citations</div>
			</div>
			<div class="rounded border border-outline bg-surface-container px-4 py-3 text-center min-w-[100px]">
				<div class="text-2xl font-bold text-on-surface">{profile.hIndex}</div>
				<div class="text-xs text-secondary">h-index</div>
			</div>
			<div class="rounded border border-outline bg-surface-container px-4 py-3 text-center min-w-[100px]">
				<div class="text-2xl font-bold text-on-surface">{profile.i10Index}</div>
				<div class="text-xs text-secondary">i10-index</div>
			</div>
		</div>

		{#if profile.affiliations.length > 0}
			<section class="mb-8">
				<h2 class="font-display text-xl font-bold text-on-surface mb-3">Affiliations</h2>
				<ul class="space-y-1">
					{#each profile.affiliations as aff}
						<li class="text-sm text-secondary">
							{aff.name}
							{#if aff.startYear || aff.endYear}
								<span class="text-xs text-outline">
									({aff.startYear ?? "?"}–{aff.endYear ?? "present"})
								</span>
							{/if}
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if profile.topCoAuthors.length > 0}
			<section class="mb-8">
				<h2 class="font-display text-xl font-bold text-on-surface mb-3">Top co-authors</h2>
				<div class="flex flex-wrap gap-2">
					{#each profile.topCoAuthors as co}
						<a
							href="{base}/authors/{co.authorId}"
							class="text-xs rounded border border-outline bg-surface-container px-2.5 py-1 hover:bg-surface-container-low transition-colors"
						>
							{co.name}
							<span class="text-outline ml-1">({co.count})</span>
						</a>
					{/each}
				</div>
			</section>
		{/if}

		<section>
			<h2 class="font-display text-xl font-bold text-on-surface mb-4">Top papers</h2>
			{#if profile.works.length === 0}
				<p class="text-sm text-secondary">No papers found.</p>
			{:else}
				<div class="divide-y divide-outline-dim">
					{#each profile.works as w}
						<div class="py-3">
							<a
								href="{base}/papers/{w.id}"
								class="text-sm font-bold text-on-surface hover:text-primary transition-colors"
							>
								{w.title}
							</a>
							<p class="text-xs text-secondary mt-1">
								{w.citedByCount} citations
								{#if w.publicationYear} · {w.publicationYear}{/if}
							</p>
						</div>
					{/each}
				</div>
			{/if}
		</section>
	{:else if graphAuthor}
		<header class="mb-8">
			<p class="label-caps mb-3">Author profile</p>
			<h1 class="font-display text-[clamp(1.5rem,3vw,2.5rem)] font-bold tracking-tight text-on-surface border-b-2 border-primary pb-3">{graphAuthor.label}</h1>
			<p class="mt-2 font-mono text-sm text-on-surface-variant">
				{graphAuthor.weight.toLocaleString()} papers in the corpus
				· <a href="{base}/papers?q={encodeURIComponent(graphAuthor.label)}" class="text-primary underline underline-offset-4 decoration-primary/30">Search papers →</a>
			</p>
		</header>

		{#if coauthors.length > 0}
			<section>
				<p class="label-caps mb-3">Top co-authors ({coauthors.length})</p>
				<div class="divide-y divide-outline/20 border-t border-outline/30">
					{#each coauthors as ca}
						<a
							href="{base}/authors/{encodeURIComponent(ca.name)}"
							class="group flex items-center gap-4 px-3 py-3 transition-colors hover:bg-surface-container-low"
						>
							<div class="flex-1 min-w-0">
								<div class="truncate font-mono text-sm font-bold text-on-surface group-hover:text-primary">{ca.name}</div>
							</div>
							<span class="font-mono text-xs text-on-surface-variant">{ca.weight} collaboration{ca.weight !== 1 ? "s" : ""}</span>
						</a>
					{/each}
				</div>
			</section>
		{/if}
	{/if}
</div>
