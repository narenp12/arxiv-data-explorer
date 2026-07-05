<script lang="ts">
	import { page } from "$app/stores";
</script>

<svelte:head>
	<title>{$page.status} — arXiv Explorer</title>
</svelte:head>

<div
	class="dot-matrix flex min-h-[70vh] items-center justify-center px-4"
	style="mask-image: radial-gradient(120% 120% at 20% 0%, black 40%, transparent 85%); -webkit-mask-image: radial-gradient(120% 120% at 20% 0%, black 40%, transparent 85%);"
>
	<div class="max-w-md border-l-4 border-warning-red bg-surface pl-8">
		<p class="label-caps mb-3">Signal lost · {$page.status}</p>
		<h1 class="font-display text-[clamp(2.5rem,6vw,4rem)] leading-none font-bold tracking-tight text-on-surface">
			{$page.status === 404 ? "Page not found" : "Something broke"}
		</h1>
		<p class="mt-4 font-mono text-sm leading-relaxed text-on-surface-variant">
			{$page.status === 404
				? "This coordinate doesn't exist in the corpus. The paper, author, or category you're after may have moved."
				: ($page.error?.message ?? "An unexpected error occurred.")}
		</p>
		<div class="mt-8 flex flex-wrap gap-4">
			<a
				href="/"
				class="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 font-mono text-xs font-bold text-surface transition-all hover:opacity-85 active:translate-y-px"
			>
				← BACK TO BASE
			</a>
			<a href="/papers" class="self-center font-mono text-xs font-bold text-on-surface-variant transition-colors hover:text-primary">
				SEARCH PAPERS
			</a>
		</div>
	</div>
</div>
