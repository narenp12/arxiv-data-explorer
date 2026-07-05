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
		{ href: "/about", label: "About", icon: "about" },
	];

	let isActive = $derived((href: string) => {
		return $page.url.pathname === href || ($page.url.pathname === base && href === "/");
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="flex min-h-screen">
	<!-- Desktop sidebar -->
	<aside class="hidden w-64 flex-shrink-0 border-r border-slate-200 bg-white md:flex md:flex-col dark:border-slate-800 dark:bg-slate-950">
		<div class="flex h-16 items-center gap-3 border-b border-slate-200 px-6 dark:border-slate-800">
			<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white text-sm font-bold">
				A
			</div>
			<span class="text-sm font-semibold text-slate-900 dark:text-slate-100">
				arXiv Data Explorer
			</span>
		</div>

		<nav class="flex-1 space-y-1 px-3 py-4">
			{#each navLinks as link}
				<a
					href={link.href}
					class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors {isActive(link.href)
						? 'bg-blue-50 text-blue-600 dark:bg-blue-950 dark:text-blue-400'
						: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100'}"
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
							<line x1="16" y1="13" x2="8" y2="13" />
							<line x1="16" y1="17" x2="8" y2="17" />
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
					{:else if link.icon === "about"}
						<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<circle cx="12" cy="12" r="10" />
							<line x1="12" y1="16" x2="12" y2="12" />
							<line x1="12" y1="8" x2="12.01" y2="8" />
						</svg>
					{/if}
					{link.label}
				</a>
			{/each}
		</nav>

		<div class="border-t border-slate-200 px-3 py-3 dark:border-slate-800">
			<div class="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-slate-500 dark:text-slate-400">
				<span>Theme</span>
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
<nav class="fixed bottom-0 left-0 right-0 z-50 border-t border-slate-200 bg-white md:hidden dark:border-slate-800 dark:bg-slate-950">
	<div class="flex items-center justify-around px-2 py-1">
		{#each navLinks as link}
			<a
				href={link.href}
				class="flex flex-col items-center gap-0.5 px-3 py-2 text-xs font-medium transition-colors {isActive(link.href)
					? 'text-blue-600 dark:text-blue-400'
					: 'text-slate-500 dark:text-slate-400'}"
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
