<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";

	interface Subcategory {
		id: string;
		label: string;
		papers: number;
	}

	interface Domain {
		id: string;
		label: string;
		color: string;
		papers: number;
		subcategories: Subcategory[];
	}

	interface HierarchyData {
		domains: Domain[];
		total_papers: number;
		total_categories: number;
	}

	let data = $state<HierarchyData | null>(null);
	let expanded = $state<Set<string>>(new Set());
	let loading = $state(true);

	onMount(async () => {
		try {
			const res = await fetch(`${base}/data/category_hierarchy.json`);
			if (res.ok) data = await res.json();
		} catch {
			// leave null
		} finally {
			loading = false;
		}
	});

	function toggle(id: string) {
		const next = new Set(expanded);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		expanded = next;
	}

	function maxPapers(): number {
		if (!data) return 1;
		return Math.max(...data.domains.map((d) => d.papers), 1);
	}
</script>

<svelte:head>
	<title>Categories — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
	<header class="mb-8">
		<p class="kicker mb-3">Taxonomy of the corpus</p>
		<h1 class="font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">Categories</h1>
		<p class="mt-2 max-w-xl text-sm leading-relaxed text-soft">
			{data
				? `${data.domains.length} domains · ${data.total_categories} categories · ${data.total_papers.toLocaleString()} papers`
				: "Loading…"}
		</p>
	</header>

	{#if loading}
		<div class="kicker animate-pulse py-16 text-center">Loading…</div>
	{:else if data}
		<div class="space-y-3">
			{#each data.domains as domain}
				<div class="rounded-xl border border-line bg-panel">
					<button
						onclick={() => toggle(domain.id)}
						class="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-accent/4"
					>
						<div class="h-3 w-3 shrink-0 rounded-full" style="background: {domain.color}"></div>
						<div class="flex-1 min-w-0">
							<div class="text-sm font-medium text-ink">{domain.label}</div>
							<div class="font-mono text-[11px] text-faint">{domain.id}</div>
						</div>
						<div class="flex items-baseline gap-4">
							<span class="font-mono text-xs text-soft">{domain.papers.toLocaleString()}</span>
							<div class="h-1.5 w-24 overflow-hidden rounded-full bg-line">
								<div class="h-full rounded-full" style="width: {(domain.papers / maxPapers() * 100)}%; background: {domain.color}"></div>
							</div>
							<span class="font-mono text-[11px] text-faint transition-transform {expanded.has(domain.id) ? 'rotate-90' : ''}">›</span>
						</div>
					</button>

					{#if expanded.has(domain.id) && domain.subcategories.length > 0}
						<div class="border-t border-line px-5 py-3">
							<div class="grid grid-cols-1 gap-1 sm:grid-cols-2">
								{#each domain.subcategories as cat}
									<a
										href="/papers?q=cat:{encodeURIComponent(cat.id)}"
										class="flex items-center justify-between rounded-md px-3 py-1.5 transition-colors hover:bg-accent/4"
									>
										<span class="font-mono text-xs text-ink">{cat.label}</span>
										<span class="font-mono text-[11px] text-faint">{cat.papers.toLocaleString()}</span>
									</a>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>
