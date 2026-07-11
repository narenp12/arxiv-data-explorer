<script lang="ts">
	import { onMount } from "svelte";
	import { page } from "$app/stores";
	import { replaceState } from "$app/navigation";
	import { searchPapers, searchArxiv, searchArxivCategory, sanitiseYearRange, sanitiseFieldOfStudy, sanitiseMinCites, type PaperResult } from "$lib/utils/db";
	import PaperCard from "./PaperCard.svelte";
	import SearchFilters from "./SearchFilters.svelte";
	import SearchSuggest from "./SearchSuggest.svelte";

	type Tab = "s2" | "arxiv";
	let activeTab = $state<Tab>("s2");

	let query = $state("");
	let results: PaperResult[] = $state([]);
	let total = $state(0);
	let offset = $state(0);
	let searching = $state(false);
	let error: string | null = $state(null);

	let yearRange = $state("");
	let fieldOfStudy = $state("");
	let minCites = $state("");

	const LIMIT = 30;

	onMount(() => {
		const urlQuery = $page.url.searchParams.get("q");
		const tabParam = $page.url.searchParams.get("source");
		if (tabParam === "arxiv") activeTab = "arxiv";
		const urlPage = Math.max(1, parseInt($page.url.searchParams.get("page") || "1", 10));
		yearRange = sanitiseYearRange($page.url.searchParams.get("yr") || "");
		fieldOfStudy = sanitiseFieldOfStudy($page.url.searchParams.get("fo") || "");
		minCites = sanitiseMinCites($page.url.searchParams.get("mc") || "");
		if (urlQuery) {
			query = urlQuery;
			if (urlQuery.trim().length >= 2) {
				offset = (urlPage - 1) * LIMIT;
				doSearch();
			}
		}
		const handler = ((e: CustomEvent) => {
			query = e.detail.query;
			offset = 0;
			doSearch();
		}) as EventListener;
		window.addEventListener("arxiv-search", handler);
		return () => window.removeEventListener("arxiv-search", handler);
	});

	function syncUrl(q: string, off: number) {
		const pageNum = Math.floor(off / LIMIT) + 1;
		const params = new URLSearchParams();
		if (q) params.set("q", q);
		if (pageNum > 1) params.set("page", String(pageNum));
		if (yearRange) params.set("yr", yearRange);
		if (fieldOfStudy) params.set("fo", fieldOfStudy);
		if (minCites) params.set("mc", minCites);
		if (activeTab === "arxiv") params.set("source", "arxiv");
		const str = params.toString();
		const url = str ? `?${str}` : window.location.pathname;
		replaceState(url, {});
	}

	function switchTab(tab: Tab) {
		activeTab = tab;
		error = null;
		if (results.length > 0) syncUrl(query, offset);
	}

	function onFilterChange(filters: { yearRange: string; fieldOfStudy: string; minCites: string }) {
		yearRange = filters.yearRange;
		fieldOfStudy = filters.fieldOfStudy;
		minCites = filters.minCites;
		offset = 0;
		syncUrl(query, 0);
		if (query.trim().length >= 2) doSearch();
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
		try {
			let res: { results: PaperResult[]; total: number };
			if (activeTab === "arxiv") {
				const catMatch = query.trim().match(/^cat:(\S+)$/i);
				if (catMatch) {
					res = await searchArxivCategory(catMatch[1], { limit: LIMIT, offset });
				} else {
					res = await searchArxiv(query, { limit: LIMIT, offset });
				}
				if (seq !== requestSeq) return;
			} else {
				const catMatch = query.trim().match(/^cat:(\S+)$/i);
				if (catMatch) {
					res = await searchArxivCategory(catMatch[1], { limit: LIMIT, offset });
				} else {
					res = await searchPapers(query, {
						limit: LIMIT,
						offset,
						yearRange: yearRange || undefined,
						fieldOfStudy: fieldOfStudy || undefined,
						minCites: minCites || undefined,
					});
				}
				if (seq !== requestSeq) return;
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
	<div class="flex border-b border-outline/20">
		<button
			role="tab"
			aria-selected={activeTab === "s2"}
			onclick={() => switchTab("s2")}
			class="px-5 py-2.5 font-mono text-xs transition-colors {activeTab === 's2' ? 'border-b-2 border-primary text-primary font-bold' : 'text-outline hover:text-on-surface-variant'}"
		>
			Semantic Scholar
		</button>
		<button
			role="tab"
			aria-selected={activeTab === "arxiv"}
			onclick={() => switchTab("arxiv")}
			class="px-5 py-2.5 font-mono text-xs transition-colors {activeTab === 'arxiv' ? 'border-b-2 border-primary text-primary font-bold' : 'text-outline hover:text-on-surface-variant'}"
		>
			arXiv
		</button>
	</div>

	{#if activeTab === "arxiv"}
		<SearchSuggest />
		<div class="font-mono text-[10px] text-outline/60 -mt-3">
			Auto-suggest from local paper index · Search via arXiv API
		</div>
	{:else}
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
	{/if}

	{#if activeTab === "s2"}
		<SearchFilters {yearRange} {fieldOfStudy} {minCites} onChange={onFilterChange} />
	{/if}

	{#if error}
		<div class="py-16 text-center font-mono text-sm text-warning-red">
			{error === "SEARCH_BUSY" ? "Semantic Scholar is busy right now — retrying usually works in a few seconds." : error === "ARXIV_BUSY" ? "arXiv is busy right now — retrying usually works in a few seconds." : error}
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
				<span class="ml-2 text-outline">via {activeTab === "arxiv" ? "arXiv" : "Semantic Scholar"}</span>
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