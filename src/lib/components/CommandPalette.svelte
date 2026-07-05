<script lang="ts">
	import { goto } from "$app/navigation";
	import { base } from "$app/paths";

	interface Item {
		label: string;
		hint: string;
		href: string;
	}

	let open = $state(false);
	let query = $state("");
	let selected = $state(0);
	let inputEl = $state<HTMLInputElement>();
	let items = $state<Item[]>([]);
	let loaded = false;

	const pages: Item[] = [
		{ label: "Papers", hint: "search", href: "/papers" },
		{ label: "Authors", hint: "networks", href: "/authors" },
		{ label: "Categories", hint: "taxonomy", href: "/categories" },
		{ label: "Trends", hint: "causal graph", href: "/trends" },
		{ label: "Compare categories", hint: "overlay", href: "/trends/compare" },
		{ label: "Takeoffs", hint: "growth table", href: "/takeoffs" },
		{ label: "Saved papers", hint: "reading list", href: "/saved" },
		{ label: "About", hint: "colophon", href: "/about" },
	];

	async function loadIndex() {
		if (loaded) return;
		loaded = true;
		try {
			const [hierRes, authRes] = await Promise.all([
				fetch(`${base}/data/category_hierarchy.json`),
				fetch(`${base}/data/author_rankings.json`),
			]);
			const cats: Item[] = [];
			if (hierRes.ok) {
				const hier = await hierRes.json();
				for (const d of hier.domains ?? []) {
					for (const sub of d.subcategories ?? []) {
						cats.push({ label: sub.label, hint: sub.id, href: `/trends/${sub.id}` });
					}
				}
			}
			const auths: Item[] = [];
			if (authRes.ok) {
				const rankings = await authRes.json();
				for (const a of rankings) {
					auths.push({ label: a.name, hint: `${a.papers.toLocaleString()} papers`, href: `/authors/${encodeURIComponent(a.name)}` });
				}
			}
			items = [...pages, ...cats, ...auths];
		} catch {
			items = pages;
		}
	}

	let filtered = $derived.by(() => {
		const q = query.trim().toLowerCase();
		const pool = items.length ? items : pages;
		if (!q) return pool.slice(0, 12);
		return pool
			.map((it) => {
				const label = it.label.toLowerCase();
				const hint = it.hint.toLowerCase();
				let score = -1;
				if (label.startsWith(q)) score = 0;
				else if (label.includes(q)) score = 1;
				else if (hint.includes(q)) score = 2;
				return { it, score };
			})
			.filter((r) => r.score >= 0)
			.sort((a, b) => a.score - b.score || a.it.label.length - b.it.label.length)
			.slice(0, 12)
			.map((r) => r.it);
	});

	function onKeydown(e: KeyboardEvent) {
		if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
			e.preventDefault();
			open = !open;
			if (open) {
				query = "";
				selected = 0;
				loadIndex();
				setTimeout(() => inputEl?.focus(), 0);
			}
			return;
		}
		if (!open) return;
		if (e.key === "Escape") {
			open = false;
		} else if (e.key === "ArrowDown") {
			e.preventDefault();
			selected = Math.min(selected + 1, filtered.length - 1);
		} else if (e.key === "ArrowUp") {
			e.preventDefault();
			selected = Math.max(selected - 1, 0);
		} else if (e.key === "Enter" && filtered[selected]) {
			e.preventDefault();
			go(filtered[selected]);
		}
	}

	function go(item: Item) {
		open = false;
		goto(item.href);
	}
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
	<div
		class="fixed inset-0 z-[70] bg-surface/60 backdrop-blur-sm"
		onclick={() => (open = false)}
		role="presentation"
	></div>
	<div
		class="fixed top-[15vh] left-1/2 z-[71] w-[min(560px,calc(100vw-2rem))] -translate-x-1/2 border border-outline/30 bg-surface-container" style="box-shadow: var(--shadow-elevated)"
		role="dialog"
		aria-modal="true"
		aria-label="Command palette"
	>
		<div class="flex items-center gap-3 border-b border-outline/20 px-4">
			<span class="label-caps text-primary">⌘K</span>
			<input
				bind:this={inputEl}
				bind:value={query}
				oninput={() => (selected = 0)}
				placeholder="Jump to category, author, page…"
				class="w-full bg-transparent py-3.5 font-mono text-sm text-on-surface placeholder:text-outline focus:outline-none"
			/>
		</div>
		<ul class="max-h-[50vh] overflow-y-auto py-1">
			{#each filtered as item, i}
				<li>
					<button
						onclick={() => go(item)}
						onmouseenter={() => (selected = i)}
						class="flex w-full items-baseline justify-between px-4 py-2 text-left font-mono text-sm transition-colors {i === selected
							? 'bg-surface-container-high text-primary'
							: 'text-on-surface'}"
					>
						<span class="truncate font-bold">{item.label}</span>
						<span class="ml-4 shrink-0 font-mono text-[11px] text-on-surface-variant">{item.hint}</span>
					</button>
				</li>
			{:else}
				<li class="px-4 py-6 text-center font-mono text-xs text-on-surface-variant">No matches</li>
			{/each}
		</ul>
	</div>
{/if}
