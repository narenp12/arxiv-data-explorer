<script lang="ts">
	import "../app.css";
	import "@fontsource-variable/playfair-display/index.css";
	import "@fontsource-variable/geist/index.css";
	import "@fontsource/space-mono/400.css";
	import "@fontsource/space-mono/700.css";
	import { page } from "$app/stores";
	import { base } from "$app/paths";
	import favicon from "$lib/assets/favicon.svg";
	import ThemeToggle from "$lib/components/ThemeToggle.svelte";
	import CommandPalette from "$lib/components/CommandPalette.svelte";

	let { children } = $props();

	// icon = inner SVG markup, rendered inside a common 24×24 stroke frame
	const navLinks = [
		{ href: "/", label: "Home", mobile: true, icon: '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" />' },
		{ href: "/papers", label: "Papers", mobile: true, icon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />' },
		{ href: "/authors", label: "Authors", mobile: true, icon: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />' },
		{ href: "/categories", label: "Categories", mobile: true, icon: '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />' },
		{ href: "/trends", label: "Trends", mobile: true, icon: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />' },
		{ href: "/takeoffs", label: "Takeoffs", mobile: true, icon: '<line x1="12" y1="20" x2="12" y2="10" /><line x1="18" y1="20" x2="18" y2="4" /><line x1="6" y1="20" x2="6" y2="16" />' },
		{ href: "/saved", label: "Saved", mobile: true, icon: '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z" />' },
		{ href: "/about", label: "About", mobile: false, icon: '<circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />' },
	];

	let isActive = $derived((href: string) => {
		const path = $page.url.pathname;
		if (href === "/") return path === "/" || path === base;
		return path === href || path.startsWith(href + "/");
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<a
	href="#main"
	class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:bg-primary focus:px-4 focus:py-2 focus:font-mono focus:text-xs focus:font-bold focus:text-surface"
>
	Skip to content
</a>

<CommandPalette />

<!-- Desktop sidebar — fixed navigation -->
<aside class="fixed top-0 left-0 z-40 hidden h-full w-14 flex-col border-r border-outline/15 bg-surface md:flex">
	<div class="flex flex-1 flex-col items-center py-5">
		<a href="/" class="mb-8 flex h-8 w-8 items-center justify-center border border-primary/40">
			<span class="font-display text-base leading-none text-primary italic">a</span>
		</a>

		<nav class="flex flex-col items-center gap-5">
			{#each navLinks as link}
				<a
					href={link.href}
					class="group flex flex-col items-center gap-1"
					aria-current={isActive(link.href) ? "page" : undefined}
				>
					<div
						class="flex h-9 w-9 items-center justify-center text-on-surface-variant transition-colors {isActive(link.href)
							? 'text-primary'
							: 'hover:text-on-surface'}"
					>
						<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							{@html link.icon}
						</svg>
					</div>
					<span class="label-caps text-[8px] {isActive(link.href) ? 'text-primary' : 'text-on-surface-variant'}">{link.label}</span>
				</a>
			{/each}
		</nav>

		<div class="mt-auto">
			<ThemeToggle />
		</div>
	</div>
</aside>

<!-- Main content area -->
<div class="md:ml-14 flex flex-1 flex-col pb-16 md:pb-0">

	<main id="main" class="relative z-10 flex-1">
		{@render children()}
	</main>
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
