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
	}
</script>

<svelte:head>
	<title>Takeoffs — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
	<header class="mb-8 flex flex-wrap items-end justify-between gap-4">
		<div>
			<p class="kicker mb-3">Growth rates · {data?.categories.length ?? "?"} categories</p>
			<h1 class="font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">Takeoffs</h1>
		</div>
		<select
			bind:value={domainFilter}
			class="rounded-lg border border-line bg-panel px-3 py-2 font-mono text-xs text-ink focus:border-accent focus:outline-none"
		>
			<option value="all">All domains</option>
			{#each domains as d}
				<option value={d}>{d}</option>
			{/each}
		</select>
	</header>

	{#if loading}
		<div class="kicker animate-pulse py-16 text-center">Loading…</div>
	{:else if error}
		<div class="py-16 text-center text-sm text-accent">{error}</div>
	{:else}
		<div class="overflow-x-auto rounded-xl border border-line">
			<table class="w-full text-left text-sm">
				<thead>
					<tr class="border-b border-line bg-panel">
						<th onclick={() => toggleSort("id")} class="kicker cursor-pointer px-4 py-3">
							Category {sortField === "id" ? (sortDir === "desc" ? "↓" : "↑") : ""}
						</th>
						<th onclick={() => toggleSort("trend")} class="kicker cursor-pointer px-4 py-3">
							Growth/month {sortField === "trend" ? (sortDir === "desc" ? "↓" : "↑") : ""}
						</th>
						<th class="kicker px-4 py-3">95% CI</th>
						<th class="kicker px-4 py-3">Domain</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-line">
					{#each sorted as cat}
						<tr class="transition-colors hover:bg-accent/4">
							<td class="px-4 py-3">
								<a href="/trends/{cat.id}" class="font-mono text-accent underline underline-offset-2">{cat.id}</a>
							</td>
							<td class="px-4 py-3">
								<div class="flex items-center gap-2">
									<div class="h-2 w-20 overflow-hidden rounded-full bg-line">
										<div
											class="h-full rounded-full"
											style="width: {Math.min(100, Math.abs(cat.trend) * 3000)}%;
												background: {cat.trend > 0 ? '#22c55e' : '#ef4444'}"
										></div>
									</div>
									<span class="font-mono text-xs" class:text-green-600={cat.trend > 0} class:text-red-600={cat.trend < 0}>
										{cat.trend > 0 ? "+" : ""}{(cat.trend * 100).toFixed(2)}%
									</span>
								</div>
							</td>
							<td class="px-4 py-3 font-mono text-xs text-faint">
								[{(cat.trend_ci[0] * 100).toFixed(2)}, {(cat.trend_ci[1] * 100).toFixed(2)}]
							</td>
							<td class="px-4 py-3 font-mono text-xs text-soft">{domainMap[cat.id] ?? "—"}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
