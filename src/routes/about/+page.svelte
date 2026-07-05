<svelte:head>
	<title>About — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-3xl px-4 py-14 sm:px-6 lg:px-8">
	<header class="mb-10 border-l-4 border-primary pl-8">
		<p class="label-caps mb-3">Colophon</p>
		<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface">About</h1>
	</header>

	<div class="space-y-6 font-mono text-sm leading-relaxed text-on-surface-variant">
		<p>
			<strong class="text-on-surface">arXiv Data Explorer</strong> — a search and visualization instrument for the arXiv
			research corpus. Search millions of preprints, explore co-authorship and category
			networks, and discover the topology of three decades of scientific research.
		</p>

		<h2 class="font-display text-xl font-bold tracking-tight text-on-surface">How it works</h2>
		<p>
			Paper search and details are powered by the <a href="https://www.semanticscholar.org/product/api" target="_blank" rel="noopener noreferrer" class="text-primary underline underline-offset-4 decoration-primary/30 hover:decoration-primary">Semantic Scholar Academic Graph API</a>
			— a free, open index of 200M+ scholarly works. No API key needed.
		</p>
		<p>
			Category networks, author rankings, and homepage statistics are precomputed from
			the arXiv metadata corpus and served as static JSON files.
		</p>

		<h2 class="font-display text-xl font-bold tracking-tight text-on-surface">Tech stack</h2>
		<ul class="space-y-1 pl-5" style="list-style-type: '→ ';">
			<li><strong class="text-primary">Frontend:</strong> Svelte 5 + SvelteKit, TypeScript, Tailwind CSS v4</li>
			<li><strong class="text-primary">Visualization:</strong> D3.js (force-directed graphs)</li>
			<li><strong class="text-primary">Search:</strong> Semantic Scholar API (free, no key)</li>
			<li><strong class="text-primary">Hosting:</strong> Cloudflare Pages (static site, zero server)</li>
		</ul>

		<h2 class="font-display text-xl font-bold tracking-tight text-on-surface">Data</h2>
		<p>
			Source: <a href="https://www.kaggle.com/datasets/Cornell-University/arxiv" target="_blank" rel="noopener noreferrer" class="text-primary underline underline-offset-4 decoration-primary/30 hover:decoration-primary">Kaggle arXiv Dataset</a>
			(Cornell University). Contains metadata for 2.99M arXiv papers (1991–{new Date().getFullYear()}).
			Precomputed network graphs and rankings are derived from this dataset.
		</p>

		<h2 class="font-display text-xl font-bold tracking-tight text-on-surface">Source</h2>
		<p>
			Open source on <a href="https://github.com/narenprax/arxiv-data-explorer" target="_blank" rel="noopener noreferrer" class="text-primary underline underline-offset-4 decoration-primary/30 hover:decoration-primary">GitHub</a>.
		</p>
	</div>
</div>
