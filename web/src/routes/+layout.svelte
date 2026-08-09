<script lang="ts">
	import '../app.css';
	import { base } from '$app/paths';
	import { catalog } from '$lib/catalog.svelte';
	import { Moon, Shield, Sun } from 'lucide-svelte';
	import { onMount } from 'svelte';

	let { children } = $props();
	let dark = $state(true);

	onMount(() => {
		dark = document.documentElement.classList.contains('dark');
		catalog.init();
	});

	function toggleTheme() {
		dark = !dark;
		document.documentElement.classList.toggle('dark', dark);
		localStorage.setItem('theme', dark ? 'dark' : 'light');
	}
</script>

<div class="min-h-dvh">
	<header
		class="sticky top-0 z-40 border-b bg-[var(--bg)]/85 backdrop-blur supports-[backdrop-filter]:bg-[var(--bg)]/70"
	>
		<div class="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
			<a href="{base}/" class="flex items-center gap-2 font-semibold tracking-tight">
				<Shield class="size-5 text-[var(--accent)]" />
				ffext
			</a>
			<span class="hidden text-sm text-[var(--fg-subtle)] sm:inline">
				Open source Firefox extensions, ranked by what you can verify
			</span>
			<div class="ml-auto flex items-center gap-1">
				<a
					href="{base}/methodology"
					class="rounded-md px-2.5 py-1.5 text-sm text-[var(--fg-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--fg)]"
				>
					Methodology
				</a>
				<button
					onclick={toggleTheme}
					aria-label="Toggle theme"
					class="rounded-md p-2 text-[var(--fg-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--fg)]"
				>
					{#if dark}<Sun class="size-4" />{:else}<Moon class="size-4" />{/if}
				</button>
			</div>
		</div>
	</header>

	{@render children()}

	<footer class="mt-16 border-t py-8 text-center text-xs text-[var(--fg-subtle)]">
		<p>
			Data from the <a
				href="https://addons.mozilla.org"
				class="underline hover:text-[var(--fg-muted)]">addons.mozilla.org</a
			> public API. Not affiliated with Mozilla.
		</p>
		{#if catalog.meta}
			<p class="mt-1 tnum">
				{catalog.meta.listed.toLocaleString()} open source extensions · snapshot
				{catalog.meta.generated.slice(0, 10)}
			</p>
		{/if}
	</footer>
</div>
