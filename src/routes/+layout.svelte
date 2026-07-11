<script lang="ts">
	import "../app.css";
	import "@fontsource-variable/playfair-display/index.css";
	import "@fontsource/space-mono/400.css";
	import "@fontsource/space-mono/700.css";
	import { page } from "$app/stores";
	import { base } from "$app/paths";
	import favicon from "$lib/assets/favicon.svg";
	import ThemeToggle from "$lib/components/ThemeToggle.svelte";
	import CommandPalette from "$lib/components/CommandPalette.svelte";
	import UnifiedSearch from "$lib/components/UnifiedSearch.svelte";

	let { children } = $props();

	// icon = inner SVG markup, rendered inside a common 24×24 stroke frame
	const navLinks = [
		{ href: `${base}/`, label: "Home", mobile: true, icon: '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" />' },
		{ href: `${base}/papers`, label: "Papers", mobile: true, icon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />' },
		{ href: `${base}/authors`, label: "Authors", mobile: true, icon: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />' },
		// mobile: false — the 375px bottom bar fits 5 links + theme toggle; more overflows unreachably
		{ href: `${base}/categories`, label: "Categories", mobile: false, icon: '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />' },
		{ href: `${base}/trends`, label: "Trends", mobile: true, icon: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />' },
		{ href: `${base}/takeoffs`, label: "Takeoffs", mobile: false, icon: '<line x1="12" y1="20" x2="12" y2="10" /><line x1="18" y1="20" x2="18" y2="4" /><line x1="6" y1="20" x2="6" y2="16" />' },
		{ href: `${base}/saved`, label: "Saved", mobile: true, icon: '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z" />' },
		{ href: `${base}/about`, label: "About", mobile: false, icon: '<circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />' },
	];

	let isActive = $derived((href: string) => {
		const path = $page.url.pathname;
		if (href === `${base}/`) return path === href || path === base;
		return path === href || path.startsWith(href + "/");
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<meta property="og:image" content="https://arxiv.observatory.art/og-image.png" />
	<meta property="og:title" content="arXiv Data Explorer — optical laboratory" />
	<meta property="og:description" content="Search millions of arXiv papers and explore category networks, co-authorship graphs, and causal research trends." />
</svelte:head>

<a
	href="{base}/#main"
	class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:bg-primary focus:px-4 focus:py-2 focus:font-mono focus:text-xs focus:font-bold focus:text-surface"
>
	Skip to content
</a>

<CommandPalette />

<!-- Desktop floating nav — instrument bar -->
<nav class="fixed top-4 left-1/2 z-40 hidden -translate-x-1/2 items-center gap-1 rounded-xl border border-outline/15 bg-surface/80 px-3 py-1.5 backdrop-blur-xl md:flex max-w-6xl w-[calc(100vw-2rem)] h-12">
	<a href="{base}/" aria-label="Home" class="flex h-7 w-7 shrink-0 items-center justify-center border border-primary/40 text-primary">
		<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" class="h-4 w-4" fill="currentColor" aria-hidden="true">
			<path d="M240 64C213.5 64 192 85.5 192 112L192 320C192 346.5 213.5 368 240 368L304 368C330.5 368 352 346.5 352 320L352 256L384 256C454.7 256 512 313.3 512 384C512 454.7 454.7 512 384 512L96 512C78.3 512 64 526.3 64 544C64 561.7 78.3 576 96 576L544 576C561.7 576 576 561.7 576 544C576 526.3 561.7 512 544 512L527.1 512C557.5 478 576 433.2 576 384C576 278 490 192 384 192L352 192L352 112C352 85.5 330.5 64 304 64L240 64zM184 416C170.7 416 160 426.7 160 440C160 453.3 170.7 464 184 464L360 464C373.3 464 384 453.3 384 440C384 426.7 373.3 416 360 416L184 416z" />
		</svg>
	</a>

	<div class="mx-1 h-4 w-px bg-outline/20"></div>

	<div class="flex items-center gap-0.5">
		{#each navLinks as link}
			<a
				href={link.href}
				class="flex items-center gap-1.5 rounded-md px-2 py-1.5 transition-colors {isActive(link.href)
					? 'bg-primary/10 text-primary'
					: 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'}"
				aria-current={isActive(link.href) ? "page" : undefined}
			>
				<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					{@html link.icon}
				</svg>
				<span class="label-caps text-[10px] max-lg:hidden">{link.label}</span>
			</a>
		{/each}
	</div>

	<UnifiedSearch />

	<ThemeToggle />
</nav>

<!-- Main content area -->
<div class="flex flex-1 flex-col pb-16 md:pb-0 md:pt-20">

	<main id="main" class="relative z-10 flex-1">
		{@render children()}
	</main>

	<!-- Footer -->
	<footer class="border-t border-outline/15 px-6 py-6 md:px-8">
		<div class="mx-auto flex max-w-6xl flex-wrap items-baseline justify-between gap-4 font-mono text-[11px] text-label">
			<a
				href="https://github.com/narenprax/arxiv-data-explorer"
				target="_blank"
				rel="noopener noreferrer"
				class="transition-colors hover:text-primary"
			>
				Source on GitHub ↗
			</a>
			<span>
				Data: <a href="https://api.semanticscholar.org/" target="_blank" rel="noopener noreferrer" class="transition-colors hover:text-primary">Semantic Scholar</a>
				· <a href="https://arxiv.org/" target="_blank" rel="noopener noreferrer" class="transition-colors hover:text-primary">arXiv</a>
				· <a href="{base}/about" class="transition-colors hover:text-primary">Colophon</a>
			</span>
		</div>
	</footer>
</div>

<!-- Mobile bottom nav — collapsed instrument panel -->
<nav class="fixed right-0 bottom-0 left-0 z-50 border-t border-outline/20 bg-surface/90 backdrop-blur-2xl md:hidden">
	<div class="flex items-center justify-around px-2 py-1">
		{#each navLinks.filter((l) => l.mobile) as link}
			<a
				href={link.href}
				class="flex flex-col items-center gap-0.5 px-2 py-2 transition-colors {isActive(link.href) ? 'text-primary' : 'text-on-surface-variant'}"
				aria-current={isActive(link.href) ? "page" : undefined}
			>
				<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					{@html link.icon}
				</svg>
				<span class="label-caps text-[9px]">{link.label}</span>
			</a>
		{/each}
		<div class="flex flex-col items-center gap-0.5 px-2 py-2">
			<ThemeToggle />
		</div>
	</div>
</nav>
