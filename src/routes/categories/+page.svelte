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
		} catch { /* categories load non-critical */ } finally {
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

<div class="mx-auto max-w-5xl px-4 py-14 sm:px-6 lg:px-8">
	<header class="mb-10">
		<p class="label-caps mb-3">Taxonomy of the corpus</p>
		<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface border-b-2 border-primary pb-3">Categories</h1>
		<p class="mt-2 max-w-xl font-mono text-sm text-on-surface-variant">
			{data
				? `${data.domains.length} domains · ${data.total_categories} categories · ${data.total_papers.toLocaleString()} papers`
				: "Loading…"}
		</p>
	</header>

	{#if loading}
		<div class="label-caps flex items-center justify-center gap-2 py-16">
Loading…
		</div>
	{:else if data}
		<div class="space-y-px">
			{#each data.domains as domain}
				<div class="border border-outline/20 bg-surface-container">
					<button
						onclick={() => toggle(domain.id)}
						class="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-surface-container-low"
					>
						<div class="h-3 w-3 shrink-0" style="background: {domain.color}"></div>
						<div class="flex-1 min-w-0">
							<div class="font-mono text-sm font-bold text-on-surface">{domain.label}</div>
							<div class="font-mono text-[11px] text-outline">{domain.id}</div>
						</div>
						<div class="flex items-baseline gap-4">
							<span class="font-mono text-xs text-on-surface-variant">{domain.papers.toLocaleString()}</span>
							<div class="h-1.5 w-24 overflow-hidden bg-surface-container-high">
								<div class="h-full" style="width: {(domain.papers / maxPapers() * 100)}%; background: {domain.color}"></div>
							</div>
							<span class="font-mono text-[11px] text-outline transition-transform {expanded.has(domain.id) ? 'rotate-90' : ''}">›</span>
						</div>
					</button>

					{#if expanded.has(domain.id) && domain.subcategories.length > 0}
						<div class="border-t border-outline/20 px-5 py-3">
							<div class="grid grid-cols-1 gap-px sm:grid-cols-2">
								{#each domain.subcategories as cat}
									<a
										href="{base}/papers?q=cat:{encodeURIComponent(cat.id)}"
										class="flex items-center justify-between px-3 py-1.5 transition-colors hover:bg-surface-container-low"
									>
										<span class="font-mono text-xs text-on-surface">{cat.label}</span>
										<span class="font-mono text-[11px] text-outline">{cat.papers.toLocaleString()}</span>
									</a>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{:else}
		<div class="flex flex-col items-center justify-center gap-3 py-16">
			<p class="font-mono text-sm text-warning-red">Failed to load category data.</p>
			<p class="font-mono text-xs text-outline">The taxonomy file may be missing or corrupt.</p>
		</div>
	{/if}
</div>
