<script lang="ts">
	import { onMount } from "svelte";

	let dark = $state(false);

	onMount(() => {
		const saved = localStorage.getItem("theme");
		if (saved) {
			dark = saved === "dark";
		} else {
			dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
		}
		apply(dark);
	});

	function toggle() {
		dark = !dark;
		apply(dark);
	}

	function apply(d: boolean) {
		document.documentElement.classList.toggle("dark", d);
		localStorage.setItem("theme", d ? "dark" : "light");
	}
</script>

<button
	onclick={toggle}
	class="flex h-9 w-9 items-center justify-center rounded-full text-soft transition-colors hover:bg-line/50 hover:text-accent"
	aria-label="Toggle theme"
>
	{#if dark}
		<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<circle cx="12" cy="12" r="4" />
			<path d="M12 2v2" />
			<path d="M12 20v2" />
			<path d="m4.93 4.93 1.41 1.41" />
			<path d="m17.66 17.66 1.41 1.41" />
			<path d="M2 12h2" />
			<path d="M20 12h2" />
			<path d="m6.34 17.66-1.41 1.41" />
			<path d="m19.07 4.93-1.41 1.41" />
		</svg>
	{:else}
		<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
		</svg>
	{/if}
</button>
