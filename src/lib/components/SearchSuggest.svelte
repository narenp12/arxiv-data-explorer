<script lang="ts">
	import { onMount } from "svelte";
	import { SuggestShard, type SuggestResults } from "$lib/utils/db";

	let shard: SuggestShard;
	let query = $state("");
	let focused = $state(false);
	let selectedIndex = $state(0);
	let loading = $state(false);
	let results: SuggestResults = $state({ papers: [], authors: [], categories: [] });
	let inputEl: HTMLInputElement;

	let debounceTimer: ReturnType<typeof setTimeout>;

	onMount(() => {
		shard = new SuggestShard();
		requestIdleCallback(() => shard.prefetch(), { timeout: 5000 });
	});

	function detectLetter(q: string): string {
		const c = q.trim().toLowerCase().normalize("NFD")[0] ?? "";
		return /^[a-z]$/.test(c) ? c : "other";
	}

	function onFocus() {
		focused = true;
		if (query.trim().length >= 1) refresh();
	}

	function onBlur() {
		setTimeout(() => { focused = false; }, 200);
	}

	function onInput(e: Event) {
		const val = (e.target as HTMLInputElement).value;
		query = val;
		clearTimeout(debounceTimer);

		if (val.trim().length < 1) {
			results = { papers: [], authors: [], categories: [] };
			loading = false;
			return;
		}

		loading = true;

		const letter = detectLetter(val);
		shard.load(letter);

		debounceTimer = setTimeout(() => {
			results = shard.search(val);
			loading = false;
			selectedIndex = flatItems.length - 1;
		}, 300);
	}

	function refresh() {
		if (query.trim().length < 1) return;
		const letter = detectLetter(query);
		shard.load(letter);
		loading = true;
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			results = shard.search(query);
			loading = false;
		}, 300);
	}

	let flatItems = $derived.by(() => {
		const items: { id: string; label: string; sublabel: string; group: string; action: () => void }[] = [];
		for (const p of results.papers) {
			items.push({
				id: p.id,
				label: p.title,
				sublabel: "",
				group: "Papers",
				action: () => {
					submitQuery(p.id);
				},
			});
		}
		for (const a of results.authors) {
			items.push({
				id: a.name,
				label: a.name,
				sublabel: "",
				group: "Authors",
				action: () => {},
			});
		}
		for (const c of results.categories) {
			items.push({
				id: c.code,
				label: `${c.code} — ${c.desc}`,
				sublabel: "",
				group: "Categories",
				action: () => {},
			});
		}
		if (query.trim().length >= 2) {
			items.push({
				id: "_search",
				label: `Search arXiv for "${query}"`,
				sublabel: "",
				group: "_action",
				action: () => submitQuery(query),
			});
		}
		return items;
	});

	function submitQuery(q: string) {
		focused = false;
		query = q;
		results = { papers: [], authors: [], categories: [] };
		window.dispatchEvent(new CustomEvent("arxiv-search", { detail: { query: q } }));
	}

	function dispatchSearch() {
		if (query.trim().length >= 2) {
			submitQuery(query);
		}
	}

	function onKeydown(e: KeyboardEvent) {
		if (!focused) return;
		if (e.key === "Escape") {
			e.preventDefault();
			focused = false;
			inputEl?.blur();
			return;
		}
		if (e.key === "Tab" && e.shiftKey) {
			return;
		}
		if (flatItems.length === 0) return;
		if (e.key === "ArrowDown") {
			e.preventDefault();
			selectedIndex = Math.min(selectedIndex + 1, flatItems.length - 1);
		} else if (e.key === "ArrowUp") {
			e.preventDefault();
			selectedIndex = Math.max(selectedIndex - 1, 0);
		} else if (e.key === "Enter") {
			e.preventDefault();
			if (flatItems[selectedIndex]) {
				flatItems[selectedIndex].action();
			}
		}
	}

	function onItemClick(i: number) {
		if (flatItems[i]) {
			flatItems[i].action();
		}
	}
</script>

<div class="relative flex-1">
	<div class="relative flex items-center">
		<svg class="pointer-events-none absolute left-5 h-4 w-4 text-outline" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
		<input
			bind:this={inputEl}
			type="search"
			placeholder="Search arXiv papers…"
			aria-label="Search arXiv papers"
			aria-expanded={focused && (flatItems.length > 0 || loading)}
			aria-controls="suggest-listbox"
			aria-activedescendant={selectedIndex >= 0 && flatItems[selectedIndex] ? `suggest-${selectedIndex}` : undefined}
			role="combobox"
			autocomplete="off"
			value={query}
			oninput={onInput}
			onfocus={onFocus}
			onblur={onBlur}
			onkeydown={onKeydown}
			class="w-full border-2 border-outline/30 bg-surface pl-12 pr-24 py-4 font-mono text-base text-on-surface transition-all placeholder:text-outline hover:border-outline/50 focus:border-primary focus:shadow-[0_0_20px_rgba(0,219,231,0.12)] focus:outline-none"
		/>
		<button
			onclick={dispatchSearch}
			disabled={query.trim().length < 2}
			class="absolute top-1/2 right-5 -translate-y-1/2 rounded bg-primary px-4 py-1.5 font-mono text-xs font-bold text-[#0a0a0a] transition-all hover:opacity-85 disabled:opacity-30 active:translate-y-px"
		>
			SEARCH
		</button>
	</div>

	{#if focused && (flatItems.length > 0 || loading)}
		<div
			id="suggest-listbox"
			class="absolute left-0 top-full z-50 mt-2 w-full max-h-[70vh] overflow-y-auto rounded-xl border border-outline/20 bg-surface-container shadow-elevated"
			role="listbox"
		>
			{#if loading && results.papers.length === 0}
				<div class="px-4 py-6 text-center font-mono text-xs text-outline">Searching…</div>
			{:else}
				{#each flatItems as item, i (item.id)}
					{#if item.group !== "_action" && (i === 0 || flatItems[i - 1].group !== item.group)}
						<div class="px-3 pt-2.5 pb-1">
							<p class="label-caps mb-1 text-[10px] text-primary">{item.group}</p>
						</div>
					{/if}
					<button
						role="option"
						aria-selected={selectedIndex === i}
						id="suggest-{i}"
						onclick={() => onItemClick(i)}
						onmouseenter={() => (selectedIndex = i)}
						class="flex w-full items-start gap-2 rounded-md px-3 py-1.5 text-left transition-colors {selectedIndex === i ? 'bg-surface-container-high' : 'hover:bg-surface-container-high'}"
					>
						<span class="truncate font-mono text-xs {item.group === '_action' ? 'text-primary' : 'text-on-surface'}">{item.label}</span>
					</button>
				{/each}
			{/if}
		</div>
	{/if}
</div>