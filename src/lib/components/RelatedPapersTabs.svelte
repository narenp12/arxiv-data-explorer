<script lang="ts">
	import { base } from "$app/paths";
	import { fetchReferences, fetchCitations, fetchRelatedWorks } from "$lib/utils/openalex";
	import type { WorkSummary } from "$lib/types";

	let { openalexWorkId, arxivId }: { openalexWorkId: string | null; arxivId: string } = $props();

	type TabId = "references" | "citations" | "similar";
	let activeTab = $state<TabId | null>(null);
	let references = $state<WorkSummary[]>([]);
	let citations = $state<WorkSummary[]>([]);
	let similar = $state<WorkSummary[]>([]);
	let loading = $state(false);

	interface Tab {
		id: TabId;
		label: string;
		count: number;
		data: WorkSummary[];
	}
	const TABS: Tab[] = $derived([
		{ id: "references", label: "References", count: references.length, data: references },
		{ id: "citations", label: "Citations", count: citations.length, data: citations },
		{ id: "similar", label: "Similar", count: similar.length, data: similar },
	]);

	async function switchTab(tab: TabId) {
		if (activeTab === tab) return;
		activeTab = tab;
		loading = true;
		try {
			let results: WorkSummary[] = [];
			const id = openalexWorkId ?? arxivId;
			if (!id) return;
			if (tab === "references") results = await fetchReferences(id);
			else if (tab === "citations") results = await fetchCitations(id);
			else if (tab === "similar") results = await fetchRelatedWorks(id);
			if (tab === "references") references = results;
			else if (tab === "citations") citations = results;
			else if (tab === "similar") similar = results;
		} finally {
			loading = false;
		}
	}
</script>

<div class="mt-8">
	<div class="flex gap-0 border-b border-outline-dim" role="tablist">
		{#each TABS as tab}
			<button
				role="tab"
				aria-selected={activeTab === tab.id}
				onclick={() => switchTab(tab.id)}
				class="px-4 py-2 text-sm transition-colors
					{activeTab === tab.id
						? 'text-primary border-b-2 border-primary font-bold'
						: 'text-secondary hover:text-on-surface hover:bg-surface-container'}"
			>
				{tab.label} ({tab.count})
			</button>
		{/each}
	</div>

	<div role="tabpanel" class="pt-4">
		{#if !activeTab}
			<p class="text-xs text-secondary py-4">Select a tab to load related papers.</p>
		{:else if loading}
			<div class="flex items-center gap-2 text-secondary py-4">
				<span class="inline-block w-2 h-2 rounded-full bg-primary animate-pulse"></span>
				<span class="text-sm">Loading…</span>
			</div>
		{:else}
			{@const currentData = TABS.find((t) => t.id === activeTab)?.data ?? []}
			{#if currentData.length === 0}
				<p class="text-sm text-secondary py-4">No results found.</p>
			{:else}
				<div class="divide-y divide-outline-dim">
					{#each currentData as item}
						<div class="py-3">
							{#if item.arxivId}
								<a
									href="{base}/papers/{item.arxivId}"
									class="text-sm font-bold text-on-surface hover:text-primary transition-colors"
								>
									{item.title}
								</a>
							{:else}
								<a
									href={item.openalexUrl}
									target="_blank"
									rel="noopener noreferrer"
									class="text-sm font-bold text-on-surface hover:text-primary transition-colors"
								>
									{item.title}
								</a>
							{/if}
							<p class="text-xs text-secondary mt-1">
								{item.authors.slice(0, 3).map((a) => a.name).join(", ")}
								{#if item.publicationYear} · {item.publicationYear}{/if}
								· {item.citedByCount} citations
								{#if !item.arxivId}
									<span class="text-outline"> · openalex.org ↗</span>
								{/if}
							</p>
						</div>
					{/each}
				</div>
			{/if}
		{/if}
	</div>
</div>
