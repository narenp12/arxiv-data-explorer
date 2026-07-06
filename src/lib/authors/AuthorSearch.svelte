<script lang="ts">
  import { onMount } from "svelte";
  import { loadAuthorSearch, searchAuthors, getStats } from "./wasm-search";

  let query = $state("");
  let results = $state<{ name: string; weight: number; coauthors: number; rank: number | null }[]>([]);
  let loading = $state(true);
  let stats = $state({ totalAuthors: 0, withRankings: 0 });
  let debounceTimer: ReturnType<typeof setTimeout>;

  onMount(async () => {
    await loadAuthorSearch();
    stats = getStats();
    loading = false;
  });

  function onInput(e: Event) {
    const target = e.target as HTMLInputElement;
    query = target.value;
    clearTimeout(debounceTimer);
    if (query.length < 2) {
      results = [];
      return;
    }
    debounceTimer = setTimeout(() => {
      results = searchAuthors(query);
    }, 150);
  }
</script>

<div class="author-search">
  {#if loading}
    <p class="loading">Loading author index…</p>
  {:else}
    <p class="stats">{stats.totalAuthors} authors indexed</p>
    <input
      type="search"
      placeholder="Search authors…"
      value={query}
      oninput={onInput}
      class="search-input"
    />
    {#if results.length > 0}
      <ul class="results">
        {#each results as r}
          <li>
            <a href="/authors/{encodeURIComponent(r.name)}">{r.name}</a>
            <span class="meta">{r.weight} papers, {r.coauthors} coauthors</span>
            {#if r.rank !== null}
              <span class="rank">#{r.rank + 1}</span>
            {/if}
          </li>
        {/each}
      </ul>
    {:else if query.length >= 2}
      <p class="no-results">No authors found</p>
    {/if}
  {/if}
</div>

<style>
  .author-search { font-family: var(--font-mono); }
  .search-input { width: 100%; padding: 0.5rem; }
  .results { list-style: none; padding: 0; }
  .results li { padding: 0.25rem 0; display: flex; gap: 1rem; }
  .meta { color: var(--color-muted); font-size: 0.875rem; }
  .rank { color: var(--color-accent); font-weight: bold; }
</style>
