<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";

	interface Category { id: string; trend: number; trend_ci: [number, number]; }
	interface CausalData { edges: any[]; categories: Category[]; }

	let data = $state<CausalData | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let sortField = $state<"trend" | "id">("trend");
	let sortDir = $state<"asc" | "desc">("desc");
	let domainFilter = $state("all");
	let domains = $state<string[]>([]);
	let domainMap = $state<Record<string, string>>({});
	let offset = $state(0);
	const PAGE_SIZE = 50;

	onMount(async () => {
		try {
			const [causalRes, hierarchyRes] = await Promise.all([
				fetch(`${base}/data/causal_edges.json`),
				fetch(`${base}/data/category_hierarchy.json`),
			]);
			if (!causalRes.ok || !hierarchyRes.ok) throw new Error("Failed");
			const causal: CausalData = await causalRes.json();
			const hierarchy = await hierarchyRes.json();
			const dm: Record<string, string> = {};
			for (const d of hierarchy.domains ?? []) {
				for (const sub of d.subcategories ?? []) {
					dm[sub.id] = d.id;
				}
			}
			domainMap = dm;
			domains = [...new Set(Object.values(dm))];
			data = causal;
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed";
		} finally {
			loading = false;
		}
	});

	let sorted = $derived.by(() => {
		if (!data) return [];
		let cats = data.categories;
		if (domainFilter !== "all") {
			cats = cats.filter((c) => domainMap[c.id] === domainFilter);
		}
		return [...cats].sort((a, b) => {
			const mul = sortDir === "desc" ? -1 : 1;
			if (sortField === "trend") return mul * (a.trend - b.trend);
			return mul * a.id.localeCompare(b.id);
		});
	});

	function toggleSort(field: "trend" | "id") {
		if (sortField === field) sortDir = sortDir === "desc" ? "asc" : "desc";
		else { sortField = field; sortDir = "desc"; }
		offset = 0;
	}

</script>

<svelte:head>
	<title>Takeoffs — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-5xl px-4 py-14 sm:px-6 lg:px-8">
	<header class="mb-10 flex flex-wrap items-end justify-between gap-4 border-l-4 border-primary pl-8">
		<div>
			<p class="label-caps mb-3">Growth rates · {data?.categories.length ?? "?"} categories</p>
			<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface">Takeoffs</h1>
		</div>
		<select
			value={domainFilter}
			onchange={(e) => { domainFilter = (e.target as HTMLSelectElement).value; offset = 0; }}
			class="border border-outline/20 bg-surface-container px-3 py-2 font-mono text-xs text-on-surface transition-colors focus:border-primary focus:outline-none"
		>
			<option value="all">All domains</option>
			{#each domains as d}
				<option value={d}>{d}</option>
			{/each}
		</select>
	</header>

	{#if loading}
		<div class="label-caps flex items-center justify-center gap-2 py-16">
			<span class="live-dot animate-pulse"></span>
			Loading…
		</div>
	{:else if error}
		<div class="py-16 text-center font-mono text-sm text-warning-red">{error}</div>
	{:else}
		<div class="overflow-x-auto border border-outline/20">
			<table class="w-full text-left font-mono text-sm">
				<thead>
					<tr class="border-b border-outline/20 bg-surface-container">
						<th onclick={() => toggleSort("id")} class="label-caps cursor-pointer px-4 py-3">
							Category {sortField === "id" ? (sortDir === "desc" ? "↓" : "↑") : ""}
						</th>
						<th onclick={() => toggleSort("trend")} class="label-caps cursor-pointer px-4 py-3">
							Growth/month {sortField === "trend" ? (sortDir === "desc" ? "↓" : "↑") : ""}
						</th>
						<th class="label-caps px-4 py-3">95% CI</th>
						<th class="label-caps px-4 py-3">Domain</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-outline/20">
					{#each sorted.slice(offset, offset + PAGE_SIZE) as cat}
						<tr class="transition-colors hover:bg-surface-container-low">
							<td class="px-4 py-3">
								<a href="/trends/{cat.id}" class="font-bold text-primary underline underline-offset-4 decoration-primary/30">{cat.id}</a>
							</td>
							<td class="px-4 py-3">
								<div class="flex items-center gap-2">
									<div class="h-2 w-20 overflow-hidden bg-surface-container-high">
										<div
											class="h-full"
											style="width: {Math.min(100, Math.abs(cat.trend) * 3000)}%;
												background: {cat.trend > 0 ? 'var(--signal-green)' : 'var(--warning-red)'}"
										></div>
									</div>
									<span class="font-mono text-xs" class:text-signal-green={cat.trend > 0} class:text-warning-red={cat.trend < 0}>
										{cat.trend > 0 ? "+" : ""}{(cat.trend * 100).toFixed(2)}%
									</span>
								</div>
							</td>
							<td class="px-4 py-3 font-mono text-xs text-outline">
								[{(cat.trend_ci[0] * 100).toFixed(2)}, {(cat.trend_ci[1] * 100).toFixed(2)}]
							</td>
							<td class="px-4 py-3 font-mono text-xs text-on-surface-variant">{domainMap[cat.id] ?? "—"}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		{#if sorted.length > PAGE_SIZE}
			<div class="flex items-center justify-between border-t border-outline/20 px-4 py-3 font-mono text-xs text-on-surface-variant">
				<span>{sorted.length} categories total</span>
				<div class="flex items-center gap-3">
					<span class="label-caps">p. {Math.floor(offset / PAGE_SIZE) + 1} / {Math.ceil(sorted.length / PAGE_SIZE)}</span>
					<button onclick={() => { offset = Math.max(0, offset - PAGE_SIZE); }}
						disabled={offset <= 0}
						class="border border-outline/20 bg-surface-container px-4 py-1.5 transition-colors hover:border-primary hover:text-primary disabled:opacity-30 disabled:hover:border-outline/20 disabled:hover:text-on-surface-variant">← PREV</button>
					<button onclick={() => { offset = Math.min(sorted.length - 1, offset + PAGE_SIZE); }}
						disabled={offset + PAGE_SIZE >= sorted.length}
						class="border border-outline/20 bg-surface-container px-4 py-1.5 transition-colors hover:border-primary hover:text-primary disabled:opacity-30 disabled:hover:border-outline/20 disabled:hover:text-on-surface-variant">NEXT →</button>
				</div>
			</div>
		{/if}
	{/if}
</div>
