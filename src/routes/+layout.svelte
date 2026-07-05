<script lang="ts">
	import "../app.css";
	import { page } from "$app/stores";
	import { base } from "$app/paths";
	import favicon from "$lib/assets/favicon.svg";
	import ThemeToggle from "$lib/components/ThemeToggle.svelte";

	let { children } = $props();

	const navLinks = [
		{ href: "/", label: "Home", icon: "home" },
		{ href: "/papers", label: "Papers", icon: "papers" },
		{ href: "/authors", label: "Authors", icon: "authors" },
		{ href: "/categories", label: "Categories", icon: "categories" },
		{ href: "/trends", label: "Trends", icon: "trends" },
		{ href: "/takeoffs", label: "Takeoffs", icon: "chart" },
		{ href: "/about", label: "About", icon: "about" },
	];

	let isActive = $derived((href: string) => {
		return $page.url.pathname === href || ($page.url.pathname === base && href === "/");
	});

	function fmt(n: number): string {
		if (n >= 1_000_000) return (n / 1_000_000).toFixed(2).replace(/\.?0+$/, "") + "M";
		if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
		return n.toLocaleString();
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<!-- Desktop sidebar — fixed navigation -->
<aside class="fixed top-0 left-0 z-40 hidden h-full w-14 flex-col border-r border-outline/15 bg-surface md:flex">
	<div class="flex flex-1 flex-col items-center py-5">
		<a href="/" class="mb-8 flex h-8 w-8 items-center justify-center border border-primary/40">
			<span class="font-display text-base leading-none text-primary italic">a</span>
		</a>

		<nav class="flex flex-col items-center gap-5">
			{#each navLinks as link, i}
				<a
					href={link.href}
					class="group flex flex-col items-center gap-1"
				>
					<div
						class="flex h-9 w-9 items-center justify-center text-on-surface-variant transition-colors {isActive(link.href)
							? 'text-primary'
							: 'hover:text-on-surface'}"
					>
						{#if link.icon === "home"}
							<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
								<polyline points="9 22 9 12 15 12 15 22" />
							</svg>
						{:else if link.icon === "papers"}
							<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
								<polyline points="14 2 14 8 20 8" />
							</svg>
						{:else if link.icon === "authors"}
							<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
								<circle cx="9" cy="7" r="4" />
								<path d="M22 21v-2a4 4 0 0 0-3-3.87" />
								<path d="M16 3.13a4 4 0 0 1 0 7.75" />
							</svg>
						{:else if link.icon === "categories"}
							<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
							</svg>
						{:else if link.icon === "trends"}
							<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
							</svg>
						{:else if link.icon === "chart"}
							<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<line x1="12" y1="20" x2="12" y2="10" /><line x1="18" y1="20" x2="18" y2="4" /><line x1="6" y1="20" x2="6" y2="16" />
							</svg>
						{:else if link.icon === "about"}
							<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<circle cx="12" cy="12" r="10" />
								<line x1="12" y1="16" x2="12" y2="12" />
								<line x1="12" y1="8" x2="12.01" y2="8" />
							</svg>
						{/if}
					</div>
					<span class="label-caps text-[8px] {isActive(link.href) ? 'text-primary' : 'text-on-surface-variant'}">{link.label}</span>
				</a>
			{/each}
		</nav>
	</div>
</aside>

<!-- Main content area -->
<div class="md:ml-14 flex flex-1 flex-col pb-16 md:pb-0">

	<main class="relative z-10 flex-1">
		{@render children()}
	</main>
</div>

<!-- Mobile bottom nav — collapsed instrument panel -->
<nav class="fixed right-0 bottom-0 left-0 z-50 border-t border-outline/20 bg-surface/90 backdrop-blur-2xl md:hidden">
	<div class="flex items-center justify-around px-2 py-1">
		{#each navLinks as link}
			<a
				href={link.href}
				class="flex flex-col items-center gap-0.5 px-3 py-2 transition-colors {isActive(link.href) ? 'text-primary' : 'text-outline-variant'}"
			>
				{#if link.icon === "home"}
					<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
						<polyline points="9 22 9 12 15 12 15 22" />
					</svg>
				{:else if link.icon === "papers"}
					<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
						<polyline points="14 2 14 8 20 8" />
					</svg>
				{:else if link.icon === "authors"}
					<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
						<circle cx="9" cy="7" r="4" />
						<path d="M22 21v-2a4 4 0 0 0-3-3.87" />
						<path d="M16 3.13a4 4 0 0 1 0 7.75" />
					</svg>
				{:else if link.icon === "categories"}
					<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
					</svg>
				{:else if link.icon === "trends"}
					<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
					</svg>
				{:else if link.icon === "chart"}
					<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<line x1="12" y1="20" x2="12" y2="10" /><line x1="18" y1="20" x2="18" y2="4" /><line x1="6" y1="20" x2="6" y2="16" />
					</svg>
				{:else if link.icon === "about"}
					<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<circle cx="12" cy="12" r="10" />
						<line x1="12" y1="16" x2="12" y2="12" />
						<line x1="12" y1="8" x2="12.01" y2="8" />
					</svg>
				{/if}
				<span class="label-caps text-[9px]">{link.label}</span>
			</a>
		{/each}
		<div class="flex flex-col items-center gap-0.5 px-3 py-2">
			<ThemeToggle />
		</div>
	</div>
</nav>
