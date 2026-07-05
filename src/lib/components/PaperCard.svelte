<script lang="ts">
	import type { PaperResult } from "$lib/utils/db";

	let { paper }: { paper: PaperResult } = $props();
</script>

<a
	href="/papers/{paper.id}"
	class="block rounded-lg border border-slate-200 bg-white p-4 transition-colors hover:border-blue-300 dark:border-slate-800 dark:bg-slate-950 dark:hover:border-blue-700"
>
	<div class="mb-1 text-xs text-slate-500 dark:text-slate-400">
		{paper.id}
	</div>
	<div class="mb-1 text-sm font-medium leading-snug text-slate-900 dark:text-slate-100">
		{paper.title}
	</div>
	<div class="truncate text-xs text-slate-400">
		{paper.authors}
	</div>
</a>
