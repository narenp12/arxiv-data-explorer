<script lang="ts">
	import { onMount } from "svelte";
	import { page } from "$app/stores";
	import { replaceState } from "$app/navigation";
	import { searchPapers, searchArxivCategory, type PaperResult } from "$lib/utils/db";
	import PaperCard from "./PaperCard.svelte";
	import SearchFilters from "./SearchFilters.svelte";

	let query = $state("");
	let results: PaperResult[] = $state([]);
	let total = $state(0);
	let offset = $state(0);
	let searching = $state(false);
	let error: string | null = $state(null);
	let viaArxiv = $state(false);

	let yearRange = $state("");
	let fieldOfStudy = $state("");
	let minCites = $state("");

	const LIMIT = 30;

	onMount(() => {
		const urlQuery = $page.url.searchParams.get("q");
		const urlPage = Math.max(1, parseInt($page.url.searchParams.get("page") || "1", 10));
		yearRange = $page.url.searchParams.get("yr") || "";
		fieldOfStudy = $page.url.searchParams.get("fo") || "";
		minCites = $page.url.searchParams.get("mc") || "";
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
		if (yearRange) params.set("yr", yearRange);
		if (fieldOfStudy) params.set("fo", fieldOfStudy);
		if (minCites) params.set("mc", minCites);
		const str = params.toString();
		const url = str ? `?${str}` : window.location.pathname;
		replaceState(url, {});
	}

	function onFilterChange(filters: { yearRange: string; fieldOfStudy: string; minCites: string }) {
		yearRange = filters.yearRange;
		fieldOfStudy = filters.fieldOfStudy;
		minCites = filters.minCites;
		offset = 0;
		syncUrl(query, 0);
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
		searching = true;
		const seq = ++requestSeq;
		const catMatch = query.trim().match(/^cat:(\S+)$/i);
		try {
			let res: { results: PaperResult[]; total: number };
			if (catMatch) {
				res = await searchArxivCategory(catMatch[1], { limit: LIMIT, offset });
				if (seq !== requestSeq) return;
				viaArxiv = true;
			} else {
				res = await searchPapers(query, {
					limit: LIMIT,
					offset,
					yearRange: yearRange || undefined,
					fieldOfStudy: fieldOfStudy || undefined,
					minCites: minCites || undefined,
				});
				if (seq !== requestSeq) return;
				viaArxiv = false;
			}
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

	function scrollResultsToTop() {
		window.scrollTo({ top: 0, behavior: "smooth" });
	}

	async function nextPage() { offset += LIMIT; await doSearch(); scrollResultsToTop(); }
	async function prevPage() { offset = Math.max(0, offset - LIMIT); await doSearch(); scrollResultsToTop(); }
</script>

<div class="space-y-5">
	<div class="relative">
		<input
			type="search"
			placeholder="Search arXiv papers… (e.g. quantum computing)"
			oninput={onInput}
			onkeydown={(e) => e.key === "Enter" && doSearch()}
			value={query}
			class="w-full border-2 border-outline/30 bg-surface px-5 py-4 font-mono text-base text-on-surface transition-all placeholder:text-outline hover:border-outline/50 focus:border-primary focus:shadow-[0_0_20px_rgba(0,219,231,0.12)]"
		/>
			<button
			onclick={() => doSearch()}
			disabled={query.trim().length < 2 || searching}
			class="absolute top-1/2 right-5 -translate-y-1/2 rounded bg-primary px-4 py-1.5 font-mono text-xs font-bold text-[#0a0a0a] transition-all hover:opacity-85 disabled:opacity-30 active:translate-y-px"
		>
			{searching ? "SEARCHING" : "SEARCH"}
		</button>
	</div>

	<SearchFilters {yearRange} {fieldOfStudy} {minCites} onChange={onFilterChange} />

	{#if error}
		<div class="py-16 text-center font-mono text-sm text-warning-red">
			{error === "SEARCH_BUSY" ? "Semantic Scholar is busy right now — retrying usually works in a few seconds." : error}
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
			<p class="mt-1 font-mono text-xs text-outline">tip: cat:cs.LG lists a category's newest papers</p>
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
				<span class="ml-2 text-outline">via {viaArxiv ? "arXiv" : "Semantic Scholar"}</span>
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
					class="border border-outline/20 bg-surface-container px-5 py-2 font-mono text-xs text-on-surface-variant transition-colors hover:border-primary hover:text-primary disabled:opacity-30 disabled:hover:border-outline/20 disabled:hover:text-on-surface-variant active:translate-y-px"
				>
					← PREV
				</button>
				<button
					onclick={nextPage}
					disabled={offset + LIMIT >= total}
					class="border border-outline/20 bg-surface-container px-5 py-2 font-mono text-xs text-on-surface-variant transition-colors hover:border-primary hover:text-primary disabled:opacity-30 disabled:hover:border-outline/20 disabled:hover:text-on-surface-variant active:translate-y-px"
				>
					NEXT →
				</button>
			</div>
		{/if}
	{/if}
</div>
