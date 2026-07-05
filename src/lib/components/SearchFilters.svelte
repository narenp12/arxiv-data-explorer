<script lang="ts">
	let { yearRange = "", fieldOfStudy = "", minCites = "", onChange }: {
		yearRange?: string;
		fieldOfStudy?: string;
		minCites?: string;
		onChange?: (filters: { yearRange: string; fieldOfStudy: string; minCites: string }) => void;
	} = $props();

	const S2_FIELDS = [
		{ value: "", label: "All fields" },
		{ value: "Computer Science", label: "Computer Science" },
		{ value: "Medicine", label: "Medicine" },
		{ value: "Biology", label: "Biology" },
		{ value: "Physics", label: "Physics" },
		{ value: "Mathematics", label: "Mathematics" },
		{ value: "Engineering", label: "Engineering" },
		{ value: "Psychology", label: "Psychology" },
		{ value: "Chemistry", label: "Chemistry" },
		{ value: "Materials Science", label: "Materials Science" },
		{ value: "Geology", label: "Geology" },
		{ value: "Environmental Science", label: "Environmental Science" },
		{ value: "Agricultural Science", label: "Agricultural Science" },
		{ value: "Economics", label: "Economics" },
		{ value: "Sociology", label: "Sociology" },
		{ value: "Political Science", label: "Political Science" },
		{ value: "Philosophy", label: "Philosophy" },
		{ value: "History", label: "History" },
		{ value: "Art", label: "Art" },
	];

	function dispatch() {
		onChange?.({ yearRange, fieldOfStudy, minCites });
	}
</script>

<div class="flex flex-wrap gap-3 items-end mb-4">
	<div class="flex flex-col gap-1">
		<label class="label-caps text-xs text-secondary" for="year-range">Year range</label>
		<input
			id="year-range"
			type="text"
			bind:value={yearRange}
			placeholder="e.g. 2020-2024"
			oninput={dispatch}
			class="w-36 rounded border border-outline bg-surface-container px-2.5 py-1.5 text-sm text-on-surface placeholder:text-outline focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors"
		/>
	</div>
	<div class="flex flex-col gap-1">
		<label class="label-caps text-xs text-secondary" for="field-of-study">Field of study</label>
		<select
			id="field-of-study"
			bind:value={fieldOfStudy}
			onchange={dispatch}
			class="w-44 rounded border border-outline bg-surface-container px-2.5 py-1.5 text-sm text-on-surface focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors"
		>
			{#each S2_FIELDS as f}
				<option value={f.value}>{f.label}</option>
			{/each}
		</select>
	</div>
	<div class="flex flex-col gap-1">
		<label class="label-caps text-xs text-secondary" for="min-cites">Min citations</label>
		<input
			id="min-cites"
			type="number"
			min="0"
			bind:value={minCites}
			placeholder="0"
			oninput={dispatch}
			class="w-24 rounded border border-outline bg-surface-container px-2.5 py-1.5 text-sm text-on-surface placeholder:text-outline focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors"
		/>
	</div>
</div>
