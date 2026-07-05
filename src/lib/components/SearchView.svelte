<script lang="ts">
	import { onMount } from "svelte";
	import { page } from "$app/stores";
	import { replaceState } from "$app/navigation";
	import { searchPapers, type PaperResult } from "$lib/utils/db";
	import PaperCard from "./PaperCard.svelte";

	let query = $state("");
	let results: PaperResult[] = $state([]);
	let total = $state(0);
	let offset = $state(0);
	let searching = $state(false);
	let error: string | null = $state(null);

	const LIMIT = 30;

	onMount(() => {
		const urlQuery = $page.url.searchParams.get("q");
		const urlPage = Math.max(1, parseInt($page.url.searchParams.get("page") || "1", 10));
		if (urlQuery) {
			query = urlQuery;
			if (urlQuery.trim().length >= 2) {
				offset = (urlPage - 1) * LIMIT;
				doSearch();
			}
		}
	});

	function syncUrl(q: string, off: number) {
		const pageNum = Math.floor(off / LIMIT) + 1;
		const params = new URLSearchParams();
		if (q) params.set("q", q);
		if (pageNum > 1) params.set("page", String(pageNum));
		const str = params.toString();
		const url = str ? `?${str}` : window.location.pathname;
		replaceState(url, {});
	}

	let debounceTimer: ReturnType<typeof setTimeout>;
	let requestSeq = 0;
	function onInput(e: Event) {
		const val = (e.target as HTMLInputElement).value;
		query = val;
		clearTimeout(debounceTimer);
		if (val.trim().length < 2) {
			results = [];
			total = 0;
			offset = 0;
			syncUrl("", 0);
			return;
		}
		searching = true;
		offset = 0;
		debounceTimer = setTimeout(() => doSearch(), 300);
	}

	async function doSearch() {
		error = null;
		const seq = ++requestSeq;
		try {
			const res = await searchPapers(query, {
				limit: LIMIT,
				offset,
			});
			if (seq !== requestSeq) return;
			results = res.results;
			total = res.total;
			syncUrl(query, offset);
		} catch (e) {
			if (seq !== requestSeq) return;
			error = e instanceof Error ? e.message : "Search failed";
		} finally {
			if (seq === requestSeq) searching = false;
		}
	}

	function nextPage() { offset += LIMIT; doSearch(); }
	function prevPage() { offset = Math.max(0, offset - LIMIT); doSearch(); }
</script>

<div class="space-y-5">
	<div class="relative">
		<input
			type="search"
			placeholder="Search papers… (e.g. quantum computing)"
			oninput={onInput}
			value={query}
			class="w-full rounded-xl border border-line bg-panel px-5 py-3.5 text-base text-ink transition-colors placeholder:text-faint focus:border-accent focus:outline-none"
		/>
		{#if searching}
			<div class="kicker absolute top-4 right-4 animate-pulse">
				searching…
			</div>
		{/if}
	</div>

	{#if error}
		<div class="py-16 text-center text-sm text-accent">
			{error}
			<button
				onclick={() => doSearch()}
				class="ml-2 underline underline-offset-2"
			>
				Retry
			</button>
		</div>
	{:else if query.trim().length === 0}
		<div class="py-16 text-center">
			<p class="font-sans text-base text-faint">Type at least 2 characters to search</p>
		</div>
	{:else if !searching && results.length === 0}
		<div class="py-16 text-center">
			<p class="font-sans text-base text-faint">No results for “{query}”</p>
		</div>
	{:else}
		<div class="flex items-baseline justify-between border-b border-line pb-2">
			<div class="font-mono text-xs text-soft">
				<span class="text-accent">{total.toLocaleString()}</span>
				result{total !== 1 ? "s" : ""} · “{query}”
				<span class="ml-2 text-faint">via Semantic Scholar</span>
			</div>
			{#if total > LIMIT}
				<div class="kicker">
					p. {Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)}
				</div>
			{/if}
		</div>

		<div class="!mt-0">
			{#each results as paper (paper.id)}
				<PaperCard {paper} />
			{/each}
		</div>

		{#if total > LIMIT}
			<div class="flex justify-center gap-2 pt-4">
				<button
					onclick={prevPage}
					disabled={offset <= 0}
					class="rounded-full border border-line px-5 py-2 font-mono text-xs text-soft transition-colors hover:border-faint hover:text-ink disabled:opacity-30 disabled:hover:border-line disabled:hover:text-soft"
				>
					← Prev
				</button>
				<button
					onclick={nextPage}
					disabled={offset + LIMIT >= total}
					class="rounded-full border border-line px-5 py-2 font-mono text-xs text-soft transition-colors hover:border-faint hover:text-ink disabled:opacity-30 disabled:hover:border-line disabled:hover:text-soft"
				>
					Next →
				</button>
			</div>
		{/if}
	{/if}
</div>
