<script lang="ts">
	import { onMount } from "svelte";
	import { page } from "$app/stores";
	import { replaceState } from "$app/navigation";
	import {
		loadDb, searchPapers, loadedRanges,
		type PaperResult, type YearRange,
	} from "$lib/utils/db";
	import PaperCard from "./PaperCard.svelte";

	const ALL_RANGES: YearRange[] = [
		"1991-1999", "2000-2009",
		"2010-2014", "2015-2019",
		"2020-2026",
	];

	let query = $state("");
	let results: PaperResult[] = $state([]);
	let total = $state(0);
	let offset = $state(0);
	let loading = $state(true);
	let loadProgress = $state(0);
	let searching = $state(false);
	let dbReady = $state(false);
	let error: string | null = $state(null);
	let selectedRange: YearRange | "all" = $state("all");

	onMount(async () => {
		const urlQuery = $page.url.searchParams.get("q");
		const urlPage = parseInt($page.url.searchParams.get("page") || "1", 10);
		if (urlQuery) query = urlQuery;

		for (const range of ALL_RANGES) {
			try {
				await loadDb(range);
				loadProgress++;
				await new Promise(r => setTimeout(r, 0));
			} catch (e) {
				error = e instanceof Error ? e.message : `Failed to load ${range}`;
				break;
			}
		}

		dbReady = true;
		loading = false;

		if (urlQuery && urlQuery.trim().length >= 2) {
			doSearch((urlPage - 1) * 30);
		}
	});

	function syncUrl(q: string, pageNum: number) {
		const params = new URLSearchParams();
		if (q) params.set("q", q);
		if (pageNum > 1) params.set("page", String(pageNum));
		const str = params.toString();
		const url = str ? `?${str}` : window.location.pathname;
		replaceState(url, {});
	}

	function activeRanges(): YearRange[] {
		return selectedRange === "all" ? ALL_RANGES : [selectedRange];
	}

	let debounceTimer: ReturnType<typeof setTimeout>;
	function onInput(e: Event) {
		const val = (e.target as HTMLInputElement).value;
		query = val;
		clearTimeout(debounceTimer);
		if (val.trim().length < 2) {
			results = [];
			total = 0;
			offset = 0;
			syncUrl("", 1);
			return;
		}
		searching = true;
		debounceTimer = setTimeout(() => {
			doSearch(0);
		}, 300);
	}

	function doSearch(newOffset: number) {
		try {
			const ranges = activeRanges().filter(r => loadedRanges().includes(r));
			const res = searchPapers(query, ranges, 30, newOffset);
			results = res.results;
			total = res.total;
			offset = newOffset;
			syncUrl(query, Math.floor(newOffset / 30) + 1);
		} catch (e) {
			error = e instanceof Error ? e.message : "Search failed";
		} finally {
			searching = false;
		}
	}

	function nextPage() {
		doSearch(offset + 30);
	}
	function prevPage() {
		doSearch(Math.max(0, offset - 30));
	}
</script>

<div class="space-y-4">
	<div class="relative">
		<input
			type="search"
			placeholder="Search papers… (e.g. quantum computing)"
			oninput={onInput}
			value={query}
			class="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm transition-colors focus:border-blue-400 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:focus:border-blue-500"
			disabled={!dbReady && !error}
		/>
		{#if searching}
			<div class="absolute right-3 top-3 animate-pulse text-sm text-slate-400">
				searching…
			</div>
		{/if}
	</div>

	<div class="flex flex-wrap items-center gap-2 text-xs">
		<span class="text-slate-500">Year range:</span>
		{#each ["all", ...ALL_RANGES] as range}
			<button
				onclick={() => { selectedRange = range as YearRange | "all"; doSearch(0); }}
				class="rounded-full px-3 py-1 transition-colors {selectedRange === range
					? 'bg-blue-500 text-white'
					: 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400'}"
			>
				{range === "all" ? "All" : range}
			</button>
		{/each}
	</div>

	{#if loading}
		<div class="animate-pulse py-12 text-center text-slate-500">
			Loading search index ({loadProgress}/{ALL_RANGES.length})…
		</div>
	{:else if error}
		<div class="py-12 text-center text-red-400">
			{error}
			<button
				onclick={() => location.reload()}
				class="ml-2 underline"
			>
				Retry
			</button>
		</div>
	{:else if query.trim().length === 0}
		<div class="py-12 text-center text-slate-500">
			Type at least 2 characters to search
		</div>
	{:else if results.length === 0 && !searching}
		<div class="py-12 text-center text-slate-500">
			No results for "{query}"
		</div>
	{:else}
		<div class="mb-2 text-xs text-slate-500 dark:text-slate-400">
			{total.toLocaleString()} result{total !== 1 ? "s" : ""} for "{query}"
			{#if total > 30}
				· page {Math.floor(offset / 30) + 1} of {Math.ceil(total / 30)}
			{/if}
		</div>

		<div class="space-y-2">
			{#each results as paper (paper.id)}
				<PaperCard {paper} />
			{/each}
		</div>

		{#if total > 30}
			<div class="flex justify-center gap-2 pt-4">
				<button
					onclick={prevPage}
					disabled={offset === 0}
					class="rounded bg-slate-100 px-4 py-2 text-sm transition-colors hover:bg-slate-200 disabled:opacity-30 dark:bg-slate-800 dark:hover:bg-slate-700"
				>
					Previous
				</button>
				<button
					onclick={nextPage}
					disabled={offset + 30 >= total}
					class="rounded bg-slate-100 px-4 py-2 text-sm transition-colors hover:bg-slate-200 disabled:opacity-30 dark:bg-slate-800 dark:hover:bg-slate-700"
				>
					Next
				</button>
			</div>
		{/if}
	{/if}
</div>
