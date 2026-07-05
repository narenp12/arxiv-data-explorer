<script lang="ts">
	import "../app.css";
	import { onMount } from "svelte";
	import { page } from "$app/stores";
	import { base } from "$app/paths";
	import favicon from "$lib/assets/favicon.svg";
	import ThemeToggle from "$lib/components/ThemeToggle.svelte";
	import type { NetworkStats } from "$lib/types";

	let { children } = $props();

	let stats = $state<NetworkStats | null>(null);

	onMount(async () => {
		try {
			const res = await fetch(`${base}/data/network_stats.json`);
			if (res.ok) {
				stats = await res.json();
			}
		} catch {
			stats = null;
		}
	});

	const navLinks = [
		{ href: "/", label: "Home", icon: "home" },
		{ href: "/papers", label: "Papers", icon: "papers" },
		{ href: "/authors", label: "Authors", icon: "authors" },
		{ href: "/categories", label: "Categories", icon: "categories" },
		{ href: "/trends", label: "Trends", icon: "trends" },
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

<div class="flex min-h-screen">
	<!-- Desktop sidebar -->
	<aside class="hidden w-60 flex-shrink-0 border-r border-line bg-paper md:flex md:flex-col">
		<a href="/" class="flex h-16 items-center gap-2.5 border-b border-line px-5">
			<div class="flex h-7 w-7 items-center justify-center rounded-md bg-accent">
				<span class="font-display text-[18px] leading-none text-white italic">a</span>
			</div>
			<span class="font-display text-[19px] tracking-tight text-ink">
				arXiv <span class="text-soft">explorer</span>
			</span>
		</a>

		<nav class="flex-1 space-y-0.5 px-3 py-5">
			{#each navLinks as link, i}
				<a
					href={link.href}
					class="group flex items-baseline gap-3 rounded-md px-3 py-2 text-sm transition-colors {isActive(link.href)
						? 'bg-accent/8 font-medium text-ink'
						: 'text-soft hover:bg-line/40 hover:text-ink'}"
				>
					<span
						class="font-mono text-[10px] tracking-widest {isActive(link.href)
							? 'text-accent'
							: 'text-faint group-hover:text-accent'}"
					>
						0{i + 1}
					</span>
					{link.label}
				</a>
			{/each}
		</nav>

		<div class="border-t border-line px-5 py-4">
			{#if stats}
				<p class="kicker mb-3 leading-relaxed">
					{fmt(stats.total_papers)} papers<br />indexed · 1991→2026
				</p>
			{/if}
			<div class="flex items-center justify-between text-sm text-soft">
				<span class="kicker">Theme</span>
				<ThemeToggle />
			</div>
		</div>
	</aside>

	<!-- Main content -->
	<div class="flex flex-1 flex-col pb-16 md:pb-0">
		<main class="flex-1">
			{@render children()}
		</main>
	</div>
</div>

<!-- Mobile bottom nav -->
<nav class="fixed right-0 bottom-0 left-0 z-50 border-t border-line bg-paper md:hidden">
	<div class="flex items-center justify-around px-2 py-1">
		{#each navLinks as link}
			<a
				href={link.href}
				class="flex flex-col items-center gap-0.5 px-3 py-2 text-[11px] font-medium transition-colors {isActive(link.href)
					? 'text-accent'
					: 'text-faint'}"
			>
				{#if link.icon === "home"}
					<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
						<polyline points="9 22 9 12 15 12 15 22" />
					</svg>
				{:else if link.icon === "papers"}
					<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
						<polyline points="14 2 14 8 20 8" />
						<line x1="16" y1="13" x2="8" y2="13" />
						<line x1="16" y1="17" x2="8" y2="17" />
					</svg>
				{:else if link.icon === "authors"}
					<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
						<circle cx="9" cy="7" r="4" />
						<path d="M22 21v-2a4 4 0 0 0-3-3.87" />
						<path d="M16 3.13a4 4 0 0 1 0 7.75" />
					</svg>
				{:else if link.icon === "categories"}
					<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
					</svg>
				{:else if link.icon === "trends"}
					<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
					</svg>
				{:else if link.icon === "about"}
					<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<circle cx="12" cy="12" r="10" />
						<line x1="12" y1="16" x2="12" y2="12" />
						<line x1="12" y1="8" x2="12.01" y2="8" />
					</svg>
				{/if}
				{link.label}
			</a>
		{/each}
		<div class="flex flex-col items-center gap-0.5 px-3 py-2">
			<ThemeToggle />
		</div>
	</div>
</nav>
