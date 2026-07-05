<script lang="ts">
	import { page } from "$app/stores";
	import { getPaperDetail, type PaperDetail } from "$lib/utils/db";
	import { base } from "$app/paths";
	import { readingList } from "$lib/stores/saved.svelte";

	function toggleSave(d: PaperDetail) {
		readingList.toggle({
			id: d.id,
			title: d.title,
			authors: d.authors,
			year: d.update_date ? parseInt(d.update_date.slice(0, 4), 10) : null,
			isArxiv: true,
		});
	}

	let detail = $state<PaperDetail | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	$effect(() => {
		const id = $page.params.id ?? "";
		if (!id) {
			error = "No paper ID specified";
			loading = false;
			return;
		}
		detail = null;
		error = null;
		loading = true;
		getPaperDetail(id).then((d) => {
			detail = d;
			if (!d) error = "Paper not found in Semantic Scholar";
		}).catch((e) => {
			error = e instanceof Error ? e.message : "Failed to load paper details";
		}).finally(() => {
			loading = false;
		});
	});
</script>

<svelte:head>
	<title>{detail?.title ?? "Paper"} — arXiv Explorer</title>
	{#if detail?.abstract}
		<meta name="description" content={detail.abstract.slice(0, 160)} />
	{/if}
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	<a
		href="/papers"
		class="label-caps mb-6 inline-flex items-center gap-1 transition-colors hover:text-primary"
	>
		← Back to search
	</a>

	{#if loading}
		<div class="label-caps flex items-center justify-center gap-2 py-20">
			<span class="live-dot animate-pulse"></span>
			Loading paper details…
		</div>
	{:else if error}
		<div class="py-20 text-center">
			<p class="font-display text-2xl font-bold text-on-surface">Not found</p>
			<p class="label-caps mt-2">{error}</p>
			{#if /^\d{4}\.\d{4,5}$/.test($page.params.id ?? "") || /^[a-z-]+(\.[A-Z]{2})?\/\d{7}$/.test($page.params.id ?? "")}
				<a href={`https://arxiv.org/abs/${$page.params.id}`} target="_blank" rel="noopener noreferrer"
					class="label-caps mt-4 inline-block text-primary underline underline-offset-4 decoration-primary/30"
				>
					View on arXiv.org →
				</a>
			{/if}
		</div>
	{:else if detail}
		<article>
			<div class="mb-3 flex items-center justify-between gap-4">
				<p class="label-caps">
					{detail.id}
					{#if detail.venue}
						· {detail.venue}
					{/if}
				</p>
				<button
					onclick={() => toggleSave(detail!)}
					aria-pressed={readingList.has(detail.id)}
					class="inline-flex shrink-0 items-center gap-2 border px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-[0.15em] transition-colors {readingList.has(detail.id)
						? 'border-primary/40 text-primary'
						: 'border-outline/20 text-on-surface-variant hover:border-primary hover:text-primary'}"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill={readingList.has(detail.id) ? "currentColor" : "none"} stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z" />
					</svg>
					{readingList.has(detail.id) ? "Saved" : "Save"}
				</button>
			</div>
			<h1 class="font-display mb-6 text-[clamp(1.5rem,3vw,2.5rem)] font-bold leading-tight tracking-tight text-on-surface">
				{detail.title}
			</h1>

			<p class="mb-8 font-mono text-sm leading-relaxed text-on-surface-variant">
				{#each detail.authors.split(", ") as author, i}
					<a href="/papers?q={encodeURIComponent(author)}" class="transition-colors hover:text-primary">{author}</a>{i < detail.authors.split(", ").length - 1 ? ", " : ""}
				{/each}
			</p>

			{#if detail.abstract}
				<div class="mb-10 border border-outline/20 bg-surface-container p-6">
					<p class="label-caps mb-3">Abstract</p>
					<p class="font-body text-[15px] leading-[1.75] text-on-surface">
						{detail.abstract}
					</p>
				</div>
			{/if}

			<div class="grid grid-cols-2 gap-px bg-outline/20 sm:grid-cols-4">
				<div class="bg-surface p-5">
					<p class="label-caps mb-1">Published</p>
					<p class="font-mono text-xs text-on-surface">{detail.update_date ?? "—"}</p>
				</div>
				<div class="bg-surface p-5">
					<p class="label-caps mb-1">Citations</p>
					<p class="font-mono text-xs text-on-surface">{detail.citationCount.toLocaleString()}</p>
				</div>
				<div class="bg-surface p-5">
					<p class="label-caps mb-1">DOI</p>
					<p class="font-mono text-xs text-on-surface">
						{#if detail.doi}
							<a href="https://doi.org/{detail.doi}" target="_blank" rel="noopener noreferrer" class="text-primary underline underline-offset-4 decoration-primary/30">
								{detail.doi}
							</a>
						{:else}—{/if}
					</p>
				</div>
				<div class="bg-surface p-5">
					<p class="label-caps mb-1">Links</p>
					<p class="font-mono text-xs text-on-surface">
						<a href={detail.arxivUrl} target="_blank" rel="noopener noreferrer" class="text-primary underline underline-offset-4 decoration-primary/30">
							arXiv
						</a>
						<span class="text-outline"> · </span>
						<a href={detail.s2Url} target="_blank" rel="noopener noreferrer" class="text-primary underline underline-offset-4 decoration-primary/30">
							Semantic Scholar
						</a>
					</p>
				</div>
			</div>
		</article>
	{/if}
</div>
