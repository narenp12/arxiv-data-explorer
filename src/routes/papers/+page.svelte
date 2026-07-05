<script lang="ts">
	import SearchView from "$lib/components/SearchView.svelte";
</script>

<svelte:head>
	<title>Search Papers — arXiv Data Explorer</title>
</svelte:head>

<div class="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
	<h1 class="mb-6 text-3xl font-bold text-slate-900 dark:text-slate-100">Search Papers</h1>
	<SearchView />
</div>
