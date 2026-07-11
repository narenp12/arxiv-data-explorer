<script lang="ts">
	import { goto } from "$app/navigation";
	import { base } from "$app/paths";
	import { searchPapers, type PaperResult } from "$lib/utils/db/search";
	import { loadAuthorSearch, searchAuthors, isReady } from "$lib/authors/wasm-search";

	interface AuthorItem { name: string; papers: number; }
	interface CatItem { id: string; label: string; papers: number; domain: string; }
	interface ConceptItem { id: string; label: string; }

	let query = $state("");
	let focused = $state(false);
	let searching = $state(false);
	let inputEl: HTMLInputElement;

	let authors: AuthorItem[] = $state([]);
	let categories: CatItem[] = $state([]);
	let concepts: ConceptItem[] = $state([]);
	let dataLoaded = false;

	let paperResults: PaperResult[] = $state([]);
	let authorResults: AuthorItem[] = $state([]);
	let categoryResults: CatItem[] = $state([]);
	let conceptResults: ConceptItem[] = $state([]);

	let debounceTimer: ReturnType<typeof setTimeout>;
	let requestSeq = 0;
	let selectedIndex = $state(0);
	let wasmLoaded = $state(false);
	let wasmLoading = $state(false);
	let paperTotal = $state(0);
	let catTotal = $state(0);
	let concTotal = $state(0);

	async function ensureData() {
		if (dataLoaded) return;
		dataLoaded = true;
		try {
			const [authRes, catRes] = await Promise.all([
				fetch(`${base}/data/author_rankings.json`),
				fetch(`${base}/data/category_hierarchy.json`),
			]);
			if (authRes.ok) authors = await authRes.json();
			if (catRes.ok) {
				const hier = await catRes.json();
				const flat: CatItem[] = [];
				for (const d of hier.domains ?? []) {
					flat.push({ id: d.id, label: d.label, papers: d.papers, domain: d.id });
					for (const sub of d.subcategories ?? []) {
						flat.push({ id: sub.id, label: sub.label, papers: sub.papers, domain: d.id });
					}
				}
				categories = flat;
				concepts = flat.filter((c) => c.id.includes(".")).map((c) => ({ id: c.id, label: c.label }));
			}
		} catch { /* data unavailable */ }
	}

	async function onFocus() {
		focused = true;
		ensureData();
		if (!wasmLoading && !wasmLoaded) {
			wasmLoading = true;
			try {
				await loadAuthorSearch();
				wasmLoaded = true;
				if (query.trim().length >= 2) doSearch();
			} catch {
				// fall back to includes() filtering
			}
			wasmLoading = false;
		}
	}

	function onBlur() {
		setTimeout(() => {
			focused = false;
		}, 200);
	}

	function clearResults() {
		paperResults = [];
		paperTotal = 0;
		authorResults = [];
		categoryResults = [];
		catTotal = 0;
		conceptResults = [];
		concTotal = 0;
		selectedIndex = 0;
	}

	function onInput(e: Event) {
		const val = (e.target as HTMLInputElement).value;
		query = val;
		clearTimeout(debounceTimer);
		if (val.trim().length < 2) {
			requestSeq++;
			clearResults();
			searching = false;
			return;
		}
		selectedIndex = 0;
		searching = true;
		debounceTimer = setTimeout(() => doSearch(), 300);
	}

	async function doSearch() {
		const seq = ++requestSeq;
		const q = query.trim().toLowerCase();

		// Authors: WASM if ready, else includes() fallback
		if (isReady()) {
			const wResults = searchAuthors(q, 5);
			authorResults = wResults.map(r => ({ name: r.name, papers: r.weight }));
		} else {
			authorResults = authors
				.filter(a => a.name.toLowerCase().includes(q))
				.slice(0, 5);
		}

		// Categories: ranked scoring
		const scoredCats = categories
			.map(c => ({ item: c, score: scoreCategory(c, q) }))
			.filter(x => x.score > 0)
			.sort((a, b) => b.score - a.score || b.item.papers - a.item.papers);
		catTotal = scoredCats.length;
		categoryResults = scoredCats.slice(0, 5).map(x => x.item);

		// Concepts: same as categories
		const scoredConcs = concepts
			.map(c => ({ item: c, score: scoreCategory(c, q) }))
			.filter(x => x.score > 0)
			.sort((a, b) => b.score - a.score);
		concTotal = scoredConcs.length;
		conceptResults = scoredConcs.slice(0, 5).map(x => x.item);

		if (seq !== requestSeq) return;

		// Papers: increased limit
		try {
			const res = await searchPapers(q, { limit: 8 });
			if (seq !== requestSeq) return;
			paperResults = res.results;
			paperTotal = res.total;
		} catch { /* paper search unavailable */ }

		searching = false;
	}

	function scoreCategory(item: { label: string; id: string }, q: string): number {
		const l = item.label.toLowerCase();
		const i = item.id.toLowerCase();
		const query = q.toLowerCase();
		if (l === query || i === query) return 100;
		if (l.startsWith(query) || i.startsWith(query)) return 80;
		if (l.split(/\s+/).some(w => w.startsWith(query))) return 60;
		if (l.includes(query) || i.includes(query)) return 40;
		return 0;
	}

	function go(href: string) {
		focused = false;
		query = "";
		clearResults();
		goto(href);
	}

	let flatItems = $derived.by(() => {
		const items: { href: string; label: string; group: string }[] = [];
		for (const p of paperResults) items.push({ href: `/papers/${encodeURIComponent(p.id)}`, label: p.title, group: "Papers" });
		for (const a of authorResults) items.push({ href: `/authors/${encodeURIComponent(a.name)}`, label: a.name, group: "Authors" });
		for (const c of categoryResults) items.push({ href: `/trends/${c.id}`, label: c.label, group: "Categories" });
		for (const c of conceptResults) items.push({ href: `/trends/${c.id}`, label: c.label, group: "Trends" });
		return items;
	});

	let isEmpty = $derived(
		!searching && flatItems.length === 0
	);

	let selOffset = $derived.by(() => {
		return {
			papers: 0,
			authors: paperResults.length,
			categories: paperResults.length + authorResults.length,
			concepts: paperResults.length + authorResults.length + categoryResults.length,
		};
	});

	function onKeydown(e: KeyboardEvent) {
		if (!focused) return;
		if (e.key === "Escape") {
			e.preventDefault();
			focused = false;
			inputEl?.blur();
			query = "";
			clearResults();
			return;
		}
		if (flatItems.length === 0) return;
		if (e.key === "ArrowDown") {
			e.preventDefault();
			selectedIndex = Math.min(selectedIndex + 1, flatItems.length - 1);
		} else if (e.key === "ArrowUp") {
			e.preventDefault();
			selectedIndex = Math.max(selectedIndex - 1, 0);
		} else if (e.key === "Enter" && flatItems[selectedIndex]) {
			e.preventDefault();
			go(flatItems[selectedIndex].href);
		}
	}
</script>

<div class="relative flex-1 max-w-xs focus-within:max-w-sm transition-all">
	<div class="relative flex items-center">
		<svg class="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-outline" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
		<input
			bind:this={inputEl}
			type="search"
			placeholder="Search…"
			value={query}
			oninput={onInput}
			onfocus={onFocus}
			onblur={onBlur}
			onkeydown={onKeydown}
			class="w-full rounded-md border border-outline/20 bg-surface-container py-1.5 pl-7 pr-2 font-mono text-xs text-on-surface placeholder:text-outline/60 transition-all focus:border-primary focus:shadow-[0_0_12px_rgba(0,219,231,0.1)] focus:outline-none [&::-webkit-search-cancel-button]:hidden"
		/>
	</div>

	{#if focused && query.trim().length >= 2}
		<div class="absolute left-1/2 top-full z-50 mt-2 min-w-[420px] -translate-x-1/2 max-h-[70vh] overflow-y-auto rounded-xl border border-outline/20 bg-surface-container shadow-elevated" role="listbox">
			{#if searching}
				<div class="px-4 py-6 text-center font-mono text-xs text-outline">Searching…</div>
			{:else if isEmpty}
				<div class="px-4 py-6 text-center font-mono text-xs text-outline">No results for &#8220;{query}&#8221;</div>
			{:else}
				{#if paperResults.length > 0}
					<div class="px-3 pt-2.5 pb-1">
						<p class="label-caps mb-1 text-[10px] text-primary">Papers</p>
						{#each paperResults as paper, i}
							<button
								role="option"
								aria-selected={selectedIndex === selOffset.papers + i}
								onclick={() => go(`/papers/${encodeURIComponent(paper.id)}`)}
								onmouseenter={() => (selectedIndex = selOffset.papers + i)}
								class="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors {selectedIndex === selOffset.papers + i ? 'bg-surface-container-high' : 'hover:bg-surface-container-high'}"
							>
								<div class="min-w-0 flex-1">
									<p class="truncate font-mono text-xs font-bold text-on-surface">{paper.title}</p>
									<p class="truncate font-mono text-[10px] text-outline">{paper.authors}</p>
								</div>
								<div class="shrink-0 text-right">
									<span class="font-mono text-[10px] text-outline">{paper.year ?? "—"}</span>
									{#if paper.citationCount > 0}
										<p class="font-mono text-[10px] text-outline/60">{paper.citationCount} cites</p>
									{/if}
								</div>
							</button>
						{/each}
						{#if paperTotal > paperResults.length}
							<button
								onclick={() => go(`/papers?q=${encodeURIComponent(query)}`)}
								class="flex w-full items-center justify-center gap-1 rounded-md px-2 py-1.5 text-[10px] font-mono text-primary transition-colors hover:bg-surface-container-high"
							>
								View all {paperTotal} results →
							</button>
						{/if}
					</div>
				{/if}

				{#if authorResults.length > 0}
					<div class="border-t border-outline/10 px-3 pt-2 pb-1">
						<p class="label-caps mb-1 text-[10px] text-primary">Authors</p>
						{#each authorResults as auth, i}
							<button
								role="option"
								aria-selected={selectedIndex === selOffset.authors + i}
								onclick={() => go(`/authors/${encodeURIComponent(auth.name)}`)}
								onmouseenter={() => (selectedIndex = selOffset.authors + i)}
								class="flex w-full items-center justify-between rounded-md px-2 py-1.5 transition-colors {selectedIndex === selOffset.authors + i ? 'bg-surface-container-high' : 'hover:bg-surface-container-high'}"
							>
								<span class="truncate font-mono text-xs text-on-surface">{auth.name}</span>
								<span class="shrink-0 font-mono text-[10px] text-outline">{auth.papers.toLocaleString()} papers</span>
							</button>
						{/each}
						<button
							onclick={() => go(`/authors?q=${encodeURIComponent(query)}`)}
							class="flex w-full items-center justify-center gap-1 rounded-md px-2 py-1.5 text-[10px] font-mono text-primary transition-colors hover:bg-surface-container-high"
						>
							View all results →
						</button>
					</div>
				{/if}

				{#if categoryResults.length > 0}
					<div class="border-t border-outline/10 px-3 pt-2 pb-1">
						<p class="label-caps mb-1 text-[10px] text-primary">Categories</p>
						{#each categoryResults as cat, i}
							<button
								role="option"
								aria-selected={selectedIndex === selOffset.categories + i}
								onclick={() => go(`/trends/${cat.id}`)}
								onmouseenter={() => (selectedIndex = selOffset.categories + i)}
								class="flex w-full items-center justify-between rounded-md px-2 py-1.5 transition-colors {selectedIndex === selOffset.categories + i ? 'bg-surface-container-high' : 'hover:bg-surface-container-high'}"
							>
								<div class="min-w-0 flex-1">
									<span class="truncate font-mono text-xs text-on-surface">{cat.label}</span>
									<p class="truncate font-mono text-[10px] text-outline">{cat.domain}</p>
								</div>
								<span class="shrink-0 font-mono text-[10px] text-outline">{cat.papers.toLocaleString()} papers</span>
							</button>
						{/each}
						{#if catTotal > categoryResults.length}
							<button
								onclick={() => go(`/trends?q=${encodeURIComponent(query)}`)}
								class="flex w-full items-center justify-center gap-1 rounded-md px-2 py-1.5 text-[10px] font-mono text-primary transition-colors hover:bg-surface-container-high"
							>
								View all {catTotal} results →
							</button>
						{/if}
					</div>
				{/if}

				{#if conceptResults.length > 0}
					<div class="border-t border-outline/10 px-3 pt-2 pb-2">
						<p class="label-caps mb-1 text-[10px] text-primary">Trends</p>
						{#each conceptResults as conc, i}
							<button
								role="option"
								aria-selected={selectedIndex === selOffset.concepts + i}
								onclick={() => go(`/trends/${conc.id}`)}
								onmouseenter={() => (selectedIndex = selOffset.concepts + i)}
								class="flex w-full items-center rounded-md px-2 py-1.5 font-mono text-xs text-on-surface transition-colors {selectedIndex === selOffset.concepts + i ? 'bg-surface-container-high' : 'hover:bg-surface-container-high'}"
							>
								{conc.label}
							</button>
						{/each}
						{#if concTotal > conceptResults.length}
							<button
								onclick={() => go(`/trends?q=${encodeURIComponent(query)}`)}
								class="flex w-full items-center justify-center gap-1 rounded-md px-2 py-1.5 text-[10px] font-mono text-primary transition-colors hover:bg-surface-container-high"
							>
								View all {concTotal} results →
							</button>
						{/if}
					</div>
				{/if}
			{/if}
		</div>
	{/if}
</div>
