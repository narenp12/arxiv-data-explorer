<script lang="ts">
	import { page } from "$app/stores";
	import { getPaperDetail, type PaperDetail } from "$lib/utils/db";

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
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
	<a
		href="/papers"
		class="kicker mb-6 inline-flex items-center gap-1 transition-colors hover:text-accent"
	>
		← Back to search
	</a>

	{#if loading}
		<div class="kicker animate-pulse py-20 text-center">Loading paper details…</div>
	{:else if error}
		<div class="py-20 text-center">
			<p class="mb-2 font-display text-2xl font-bold text-ink">Not found</p>
			<p class="kicker">{error}</p>
			<a href={id ? `https://arxiv.org/abs/${id}` : ""} target="_blank" rel="noopener noreferrer"
				class="kicker mt-4 inline-block underline underline-offset-2 transition-colors hover:text-accent"
			>
				View on arXiv.org →
			</a>
		</div>
	{:else if detail}
		<article>
			<p class="kicker mb-3">
				{detail.id}
				{#if detail.venue}
					· {detail.venue}
				{/if}
			</p>
			<h1 class="font-display mb-6 text-3xl font-bold leading-tight tracking-tight text-ink sm:text-4xl">
				{detail.title}
			</h1>

			<p class="mb-8 text-base leading-relaxed text-soft">
				{detail.authors}
			</p>

			{#if detail.abstract}
				<div class="mb-10 rounded-xl border border-line bg-panel p-6">
					<p class="kicker mb-3">Abstract</p>
					<p class="text-sm leading-[1.75] text-ink">
						{detail.abstract}
					</p>
				</div>
			{/if}

			<div class="grid grid-cols-2 gap-6 border-t border-line pt-6 text-sm sm:grid-cols-4">
				<div>
					<p class="kicker mb-1">Published</p>
					<p class="font-mono text-xs text-ink">{detail.update_date ?? "—"}</p>
				</div>
				<div>
					<p class="kicker mb-1">Citations</p>
					<p class="font-mono text-xs text-ink">{detail.citationCount.toLocaleString()}</p>
				</div>
				<div>
					<p class="kicker mb-1">DOI</p>
					<p class="font-mono text-xs text-ink">
						{#if detail.doi}
							<a href="https://doi.org/{detail.doi}" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2 transition-colors hover:text-accent">
								{detail.doi}
							</a>
						{:else}—{/if}
					</p>
				</div>
				<div>
					<p class="kicker mb-1">Links</p>
					<p class="font-mono text-xs text-ink">
						<a href={detail.arxivUrl} target="_blank" rel="noopener noreferrer" class="underline underline-offset-2 transition-colors hover:text-accent">
							arXiv
						</a>
						<span class="text-faint"> · </span>
						<a href={detail.s2Url} target="_blank" rel="noopener noreferrer" class="underline underline-offset-2 transition-colors hover:text-accent">
							Semantic Scholar
						</a>
					</p>
				</div>
			</div>
		</article>
	{/if}
</div>
