<script lang="ts">
	import SearchView from "$lib/components/SearchView.svelte";
</script>

<svelte:head>
	<title>Search Papers — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
	<header class="mb-10 border-l-4 border-primary pl-8">
		<p class="label-caps mb-3">Full-text search · Semantic Scholar API</p>
		<h1 class="font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight text-on-surface">Search papers</h1>
	</header>
	<SearchView />
</div>
