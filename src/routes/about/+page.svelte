<svelte:head>
	<title>About — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-2xl px-4 py-12 sm:px-6 lg:px-8">
	<header class="mb-8">
		<p class="kicker mb-3">Colophon</p>
		<h1 class="font-display text-4xl tracking-tight font-bold text-ink sm:text-5xl">About</h1>
	</header>

	<div class="prose prose-sm prose-ink max-w-none space-y-5 text-sm leading-relaxed">
		<p>
			<strong>arXiv Data Explorer</strong> — a search and visualization tool for the arXiv
			research corpus. Search millions of preprints, explore co-authorship and category
			networks, and discover the shape of three decades of scientific research.
		</p>

		<h2 class="font-display text-lg font-semibold text-ink">How it works</h2>
		<p>
			Paper search and details are powered by the <a href="https://www.semanticscholar.org/product/api" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2 hover:text-accent">Semantic Scholar Academic Graph API</a>
			— a free, open index of 200M+ scholarly works. No API key needed.
		</p>
		<p>
			Category networks, author rankings, and homepage statistics are precomputed from
			the arXiv metadata corpus and served as static JSON files.
		</p>

		<h2 class="font-display text-lg font-semibold text-ink">Tech stack</h2>
		<ul class="list-disc space-y-1 pl-5">
			<li><strong>Frontend:</strong> Svelte 5 + SvelteKit, TypeScript, Tailwind CSS v4</li>
			<li><strong>Visualization:</strong> D3.js (force-directed graphs)</li>
			<li><strong>Search:</strong> Semantic Scholar API (free, no key)</li>
			<li><strong>Hosting:</strong> Cloudflare Pages (static site, zero server)</li>
		</ul>

		<h2 class="font-display text-lg font-semibold text-ink">Data</h2>
		<p>
			Source: <a href="https://www.kaggle.com/datasets/Cornell-University/arxiv" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2 hover:text-accent">Kaggle arXiv Dataset</a>
			(Cornell University). Contains metadata for 2.99M arXiv papers (1991–2026).
			Precomputed network graphs and rankings are derived from this dataset.
		</p>

		<h2 class="font-display text-lg font-semibold text-ink">Source</h2>
		<p>
			Open source on <a href="https://github.com/narenprax/arxiv-data-explorer" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2 hover:text-accent">GitHub</a>.
		</p>
	</div>
</div>
