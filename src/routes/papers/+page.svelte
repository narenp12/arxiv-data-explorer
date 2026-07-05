<script lang="ts">
	import SearchView from "$lib/components/SearchView.svelte";
</script>

<svelte:head>
	<title>Search Papers — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
	<header class="mb-8">
		<p class="kicker mb-3">Full-text search · Semantic Scholar API</p>
		<h1 class="font-display text-4xl tracking-tight font-bold text-ink sm:text-5xl">Search papers</h1>
	</header>
	<SearchView />
</div>
