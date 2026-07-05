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
	let yearFrom = $state("");
	let yearTo = $state("");

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
		const currentYear = new Date().getFullYear();
		const yr = yearFrom && yearTo ? `${yearFrom}-${yearTo}` : yearFrom || yearTo ? `${yearFrom || "1991"}-${yearTo || String(currentYear)}` : undefined;
		try {
			const res = await searchPapers(query, {
				limit: LIMIT,
				offset,
				yearRange: yr,
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
			placeholder="Search arXiv papers… (e.g. quantum computing)"
			oninput={onInput}
			value={query}
			class="w-full border-2 border-outline/30 bg-surface px-5 py-4 font-mono text-base text-on-surface transition-all placeholder:text-outline hover:border-outline/50 focus:border-primary focus:outline-none focus:shadow-[0_0_20px_rgba(0,219,231,0.12)]"
		/>
		{#if searching}
			<div class="label-caps absolute top-1/2 right-5 -translate-y-1/2 flex items-center gap-1.5">
				<span class="h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_6px_var(--primary)]"></span>
				SEARCHING
			</div>
		{/if}
	</div>

	<div class="flex items-center gap-2 font-mono text-xs text-on-surface-variant">
		<label class="label-caps" for="year-from">Year</label>
		<input
			id="year-from"
			type="number" placeholder="From" min="1991" max={new Date().getFullYear()}
			bind:value={yearFrom}
			oninput={() => { offset = 0; clearTimeout(debounceTimer); if (query.trim().length >= 2) { searching = true; debounceTimer = setTimeout(() => doSearch(), 300); } }}
			class="w-20 border border-outline/20 bg-surface-container px-2 py-1.5 text-on-surface transition-colors focus:border-primary focus:outline-none placeholder:text-outline"
		/>
		<span class="text-outline">–</span>
		<input
			type="number" placeholder="To" min="1991" max={new Date().getFullYear()}
			bind:value={yearTo}
			oninput={() => { offset = 0; clearTimeout(debounceTimer); if (query.trim().length >= 2) { searching = true; debounceTimer = setTimeout(() => doSearch(), 300); } }}
			class="w-20 border border-outline/20 bg-surface-container px-2 py-1.5 text-on-surface transition-colors focus:border-primary focus:outline-none placeholder:text-outline"
		/>
	</div>

	{#if error}
		<div class="py-16 text-center font-mono text-sm text-warning-red">
			{error}
			<button
				onclick={() => doSearch()}
				class="ml-2 text-primary underline underline-offset-4 decoration-primary/30"
			>
				Retry
			</button>
		</div>
	{:else if query.trim().length === 0}
		<div class="py-16 text-center">
			<p class="font-mono text-sm text-outline">TYPE AT LEAST 2 CHARACTERS TO SCAN</p>
		</div>
	{:else if !searching && results.length === 0}
		<div class="py-16 text-center">
			<p class="font-mono text-sm text-outline">No results for <span class="text-on-surface">“{query}”</span></p>
		</div>
	{:else}
		<div class="flex items-baseline justify-between border-b border-outline/20 pb-2">
			<div class="font-mono text-xs text-on-surface-variant">
				<span class="text-primary font-bold">{total.toLocaleString()}</span>
				result{total !== 1 ? "s" : ""} · “{query}”
				<span class="ml-2 text-outline">via Semantic Scholar</span>
			</div>
			{#if total > LIMIT}
				<div class="label-caps">
					p. {Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)}
				</div>
			{/if}
		</div>

		<div class="!mt-0">
			{#each results as paper, i (paper.id || i)}
				<PaperCard {paper} />
			{/each}
		</div>

		{#if total > LIMIT}
			<div class="flex justify-center gap-2 pt-4">
				<button
					onclick={prevPage}
					disabled={offset <= 0}
					class="border border-outline/20 bg-surface-container px-5 py-2 font-mono text-xs text-on-surface-variant transition-colors hover:border-primary hover:text-primary disabled:opacity-30 disabled:hover:border-outline/20 disabled:hover:text-on-surface-variant"
				>
					← PREV
				</button>
				<button
					onclick={nextPage}
					disabled={offset + LIMIT >= total}
					class="border border-outline/20 bg-surface-container px-5 py-2 font-mono text-xs text-on-surface-variant transition-colors hover:border-primary hover:text-primary disabled:opacity-30 disabled:hover:border-outline/20 disabled:hover:text-on-surface-variant"
				>
					NEXT →
				</button>
			</div>
		{/if}
	{/if}
</div>
