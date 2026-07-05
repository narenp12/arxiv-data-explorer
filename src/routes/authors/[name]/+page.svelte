<script lang="ts">
	import { page } from "$app/stores";
	import { base } from "$app/paths";
	import * as d3 from "d3";

	interface AuthNode { id: string; label: string; weight: number; }

	interface DispNode extends d3.SimulationNodeDatum { id: string; label: string; weight: number; }

	interface AuthorShardEntry { w: number; co: [string, number][]; }
	type AuthorShard = Record<string, AuthorShardEntry>;

	const SHARD_COUNT = 64;

	// Must match scripts/build_author_shards.mjs exactly.
	function fnv1a32(str: string): number {
		let h = 0x811c9dc5;
		for (let i = 0; i < str.length; i++) {
			h ^= str.charCodeAt(i);
			h = Math.imul(h, 0x01000193) >>> 0;
		}
		return h;
	}

	let author = $state<AuthNode | null>(null);
	let coauthors: { name: string; weight: number }[] = $state([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let svgEl = $state<SVGSVGElement>();
	let requestSeq = 0;

	$effect(() => {
		const name = $page.params.name ?? "";
		if (!name) { error = "No author specified"; loading = false; return; }
		loading = true;
		error = null;
		const seq = ++requestSeq;
		const shard = fnv1a32(name) % SHARD_COUNT;
		fetch(`${base}/data/authors/shard-${shard}.json`).then((r) => {
			if (!r.ok) throw new Error("Failed to load");
			return r.json() as Promise<AuthorShard>;
		}).then((data) => {
			if (seq !== requestSeq) return;
			let matchedName: string | null = null;
			let entry: AuthorShardEntry | undefined = data[name];
			if (entry) {
				matchedName = name;
			} else {
				const key = Object.keys(data).find((k) => k.toLowerCase() === name.toLowerCase());
				if (key) {
					matchedName = key;
					entry = data[key];
				}
			}
			if (!entry || !matchedName) { error = "Author not found"; return; }
			author = { id: name, label: matchedName, weight: entry.w };
			coauthors = entry.co.slice(0, 20).map(([coName, weight]) => ({ name: coName, weight }));
		}).catch((e) => { if (requestSeq === seq) error = e instanceof Error ? e.message : "Failed"; })
		.finally(() => { if (requestSeq === seq) loading = false; });
	});

	// Draw once both the data and the <svg> exist — the svg mounts only after
	// `loading` flips, so drawing from the fetch chain finds no element.
	$effect(() => {
		if (!author || !svgEl) return;
		renderMiniGraph(author.label, coauthors);
	});

	function renderMiniGraph(centerId: string, coauthorsList: { name: string; weight: number }[]) {
		if (!svgEl) return;
		const w = svgEl.clientWidth || 600;
		const h = 260;
		svgEl.setAttribute("viewBox", `0 0 ${w} ${h}`);
		d3.select(svgEl).selectAll("*").remove();

		const nodes: DispNode[] = [
			{ id: centerId, label: centerId, weight: 1 },
			...coauthorsList.map((c) => ({ id: c.name, label: c.name, weight: c.weight })),
		];
		const edges = coauthorsList.map((c) => ({ source: centerId, target: c.name, weight: c.weight }));

		const sim = d3.forceSimulation(nodes.map((n) => ({ ...n })))
			.force("link", d3.forceLink(edges).id((d: any) => d.id).distance(60).strength(0.5))
			.force("charge", d3.forceManyBody().strength(-40))
			.force("center", d3.forceCenter(w / 2, h / 2))
			.force("collision", d3.forceCollide().radius(5))
			.stop();
		const ticks = Math.ceil(Math.log(sim.alphaMin()) / Math.log(1 - sim.alphaDecay()));
		sim.tick(ticks);
		const g = d3.select(svgEl).append("g");
		g.selectAll("line").data(edges).join("line")
			.attr("stroke", "var(--outline)").attr("stroke-width", 0.5).attr("stroke-opacity", 0.4)
			.attr("x1", (d: any) => d.source.x).attr("y1", (d: any) => d.source.y)
			.attr("x2", (d: any) => d.target.x).attr("y2", (d: any) => d.target.y);
		g.selectAll("circle").data(nodes).join("circle")
			.attr("r", (d: any) => d.id === centerId ? 8 : Math.max(2, Math.min(6, Math.sqrt(d.weight) * 0.08)))
			.attr("fill", (d: any) => d.id === centerId ? "var(--primary)" : "var(--secondary)")
			.attr("fill-opacity", 0.6).attr("stroke", "var(--primary-container)").attr("stroke-width", 0.5)
			.attr("cx", (d: any) => d.x).attr("cy", (d: any) => d.y)
			.append("title").text((d: any) => { const suffix = d.id === centerId ? "" : " (" + d.weight + " collaborations)"; return d.label + suffix; });
	}
</script>

<svelte:head>
	<title>{$page.params.name ?? "Author"} — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	<a href="/authors" class="label-caps mb-6 inline-flex items-center gap-1 transition-colors hover:text-primary">← All authors</a>

	{#if loading}
		<div class="label-caps flex items-center justify-center gap-2 py-20">
			<span class="live-dot animate-pulse"></span>
			Loading…
		</div>
	{:else if error}
		<div class="py-20 text-center">
			<p class="font-display text-2xl font-bold text-on-surface">Not found</p>
			<p class="label-caps mt-2">{error}</p>
		</div>
	{:else if author}
		<header class="mb-8 border-l-4 border-primary pl-8">
			<p class="label-caps mb-3">Author profile</p>
			<h1 class="font-display text-[clamp(1.5rem,3vw,2.5rem)] font-bold tracking-tight text-on-surface">{author.label}</h1>
			<p class="mt-2 font-mono text-sm text-on-surface-variant">
				{author.weight.toLocaleString()} papers in the corpus
				· <a href="/papers?q={encodeURIComponent(author.label)}" class="text-primary underline underline-offset-4 decoration-primary/30">Search papers →</a>
			</p>
		</header>

		<div class="mb-8 overflow-hidden border border-outline/20 bg-surface-container">
			<svg bind:this={svgEl} class="h-[260px] w-full" role="img" aria-label="Co-authorship subgraph"></svg>
		</div>

		{#if coauthors.length > 0}
			<section>
				<p class="label-caps mb-3">Top co-authors ({coauthors.length})</p>
				<div class="divide-y divide-outline/20 border-t border-outline/30">
					{#each coauthors as ca}
						<a href="/authors/{encodeURIComponent(ca.name)}" class="group flex items-center gap-4 px-3 py-3 transition-colors hover:bg-surface-container-low">
							<div class="flex-1 min-w-0">
								<div class="truncate font-mono text-sm font-bold text-on-surface group-hover:text-primary">{ca.name}</div>
							</div>
							<span class="font-mono text-xs text-on-surface-variant">{ca.weight} collaboration{ca.weight !== 1 ? "s" : ""}</span>
						</a>
					{/each}
				</div>
			</section>
		{/if}
	{/if}
</div>
