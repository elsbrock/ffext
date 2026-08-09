<script lang="ts">
	import ExtensionRow from '$lib/components/ExtensionRow.svelte';
	import FilterPanel from '$lib/components/FilterPanel.svelte';
	import Seo from '$lib/components/Seo.svelte';
	import { applyFilters, catalog, defaultFilters, type SortKey } from '$lib/catalog.svelte';
	import { base } from '$app/paths';
	import { SITE_DESCRIPTION, SITE_URL } from '$lib/seo';
	import { filtersToQuery, filtersFromParams } from '$lib/urlstate';
	import { replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import { Check, Link2, Loader2, Search, SlidersHorizontal, X } from 'lucide-svelte';
	import { onMount, tick } from 'svelte';
	import type { Snapshot } from './$types';

	let filters = $state(defaultFilters());
	let showFilters = $state(false);
	let limit = $state(60);
	let copied = $state(false);

	// Restoring after mount rather than at init keeps the prerendered markup and
	// the hydrated markup identical; the catalogue has not loaded yet either way,
	// so there is nothing to re-filter.
	//
	// The write-back is armed a tick later still: onMount runs inside the
	// hydration flush, and calling replaceState before the router has finished
	// starting throws — which aborts the rest of the flush and leaves the filter
	// controls showing defaults while the state behind them is already restored.
	let restored = $state(false);
	let mounted = false;
	onMount(() => {
		filters = filtersFromParams(page.url.searchParams);
		if (filters.includeDeclared) catalog.loadDeclared();
		mounted = true;
		applyPendingScroll();
		const armed = setTimeout(() => (restored = true));
		return () => clearTimeout(armed);
	});

	// Coming back from a detail page, the URL alone is not enough to reproduce the
	// view: how far down the "Show more" pagination had been taken is component
	// state, and a list truncated back to 60 rows is shorter than the offset the
	// browser wants to restore, so the offset gets clamped and you land near the
	// top. The snapshot carries both the page size and the offset.
	let pendingScroll: number | null = null;

	export const snapshot: Snapshot<{ limit: number; y: number }> = {
		capture: () => ({ limit, y: window.scrollY }),
		restore: (v) => {
			limit = v.limit;
			pendingScroll = v.y;
			applyPendingScroll();
		}
	};

	// Restoring is a two-part handshake — SvelteKit calls `restore` and `onMount`
	// in an order this component should not depend on, and the offset is only
	// meaningful once both the page size and the URL's filters are applied.
	// Whichever lands second does the scrolling: after `tick` for the rows to
	// exist, then a frame later so SvelteKit's own restore does not overwrite it.
	function applyPendingScroll() {
		if (!mounted || pendingScroll === null) return;
		const y = pendingScroll;
		pendingScroll = null;
		tick().then(() => requestAnimationFrame(() => window.scrollTo(0, y)));
	}

	// Mirror the filter state into the address bar so the current view is a link.
	// replaceState, not pushState: every keystroke would otherwise be a history
	// entry and the back button would become useless.
	$effect(() => {
		const query = filtersToQuery(filters);
		if (!restored) return;
		if (query !== page.url.search) replaceState(`${page.url.pathname}${query}`, page.state);
	});

	async function copyLink() {
		try {
			await navigator.clipboard.writeText(page.url.href);
			copied = true;
			setTimeout(() => (copied = false), 1500);
		} catch {
			// Clipboard denied — the URL is already in the address bar to copy by hand.
		}
	}

	const pool = $derived(
		filters.includeDeclared ? [...catalog.verified, ...catalog.declared] : catalog.verified
	);
	const results = $derived(applyFilters(pool, filters));
	const visible = $derived(results.slice(0, limit));

	// Reset paging whenever the result set changes shape — but only for changes the
	// user made. Restoring filters from the URL also mutates `filters`, and
	// treating that as a change would throw away the page size the snapshot just
	// restored. Every filter is representable in the query string, so comparing
	// the serialised form is an exact test for "did the result set change".
	let pagedQuery = '';
	$effect(() => {
		const query = filtersToQuery(filters);
		if (!restored) {
			pagedQuery = query;
			return;
		}
		if (query === pagedQuery) return;
		pagedQuery = query;
		limit = 60;
	});

	const SORTS: { key: SortKey; label: string }[] = [
		{ key: 'score', label: 'Trust score' },
		{ key: 'users', label: 'Users' },
		{ key: 'updated', label: 'Recently updated' },
		{ key: 'rating', label: 'Best rated' },
		{ key: 'name', label: 'Name' }
	];

	const activeCount = $derived(
		filters.categories.size +
			filters.licenseFamilies.size +
			filters.dataCollection.size +
			(filters.excludeBroadHost ? 1 : 0) +
			(filters.excludeHighRisk ? 1 : 0) +
			(filters.maintainedOnly ? 1 : 0) +
			(filters.minScore > 0 ? 1 : 0)
	);
</script>

<Seo
	path="/"
	schema={{
		'@context': 'https://schema.org',
		'@graph': [
			{
				'@type': 'WebSite',
				'@id': `${SITE_URL}/#website`,
				url: `${SITE_URL}/`,
				name: 'ffext',
				description: SITE_DESCRIPTION,
				inLanguage: 'en'
			},
			{
				'@type': 'Dataset',
				'@id': `${SITE_URL}/#dataset`,
				name: 'Trust signals for open source Firefox extensions',
				description:
					'License, source availability, permission footprint, data-collection disclosure and maintenance recency for every OSI/FSF-licensed extension on addons.mozilla.org.',
				url: `${SITE_URL}/`,
				isAccessibleForFree: true,
				license: 'https://www.gnu.org/licenses/agpl-3.0.html',
				creator: { '@type': 'Person', name: 'Simon Elsbrock' },
				isBasedOn: 'https://addons.mozilla.org/'
			}
		]
	}}
/>

<main class="mx-auto max-w-7xl px-4 py-8">
	<section class="mb-8">
		<h1 class="text-3xl font-bold tracking-tight text-balance sm:text-4xl">
			Find Firefox extensions you can actually check
		</h1>
		<p class="mt-3 max-w-2xl text-[var(--fg-muted)]">
			A directory of Firefox add-ons from
			<a
				href="https://addons.mozilla.org"
				rel="noopener noreferrer"
				target="_blank"
				class="underline decoration-[var(--fg-subtle)] underline-offset-2 hover:text-[var(--fg)]"
				>addons.mozilla.org</a
			>, filtered down to the ones that are open source and ranked by evidence instead of
			popularity: is the source public, how much access does it ask for, what does it admit to
			collecting, and is anyone still maintaining it.
		</p>
		<p class="mt-2 max-w-2xl text-sm text-[var(--fg-subtle)]">
			An extension runs inside every page you visit. This tells you which ones you can verify
			before installing — <a
				href="{base}/methodology"
				class="underline decoration-[var(--fg-subtle)] underline-offset-2 hover:text-[var(--fg)]"
				>how the score works</a
			>.
		</p>
		{#if catalog.meta}
			<div class="tnum mt-5 flex flex-wrap gap-x-8 gap-y-3 text-sm">
				<div>
					<div class="text-2xl font-semibold text-[var(--color-trust-high)]">
						{catalog.meta.tiers.verified.toLocaleString()}
					</div>
					<div class="text-[var(--fg-subtle)]">with public source</div>
				</div>
				<div>
					<div class="text-2xl font-semibold">{catalog.meta.tiers.declared.toLocaleString()}</div>
					<div class="text-[var(--fg-subtle)]">license declared only</div>
				</div>
				<div>
					<div class="text-2xl font-semibold text-[var(--fg-muted)]">
						{catalog.meta.excludedNonOss.toLocaleString()}
					</div>
					<div class="text-[var(--fg-subtle)]">excluded as closed source</div>
				</div>
			</div>
		{/if}
	</section>

	<div class="mb-5 flex flex-wrap items-center gap-2">
		<div class="relative min-w-56 flex-1">
			<Search
				class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-[var(--fg-subtle)]"
			/>
			<input
				type="search"
				placeholder="Search {(pool.length || 0).toLocaleString()} extensions…"
				bind:value={filters.query}
				class="surface h-10 w-full rounded-lg pr-3 pl-9 text-sm outline-none focus:border-[var(--ring)]"
			/>
		</div>

		<select
			bind:value={filters.sort}
			aria-label="Sort by"
			class="surface h-10 rounded-lg px-3 text-sm outline-none focus:border-[var(--ring)]"
		>
			{#each SORTS as s (s.key)}<option value={s.key}>{s.label}</option>{/each}
		</select>

		<button
			onclick={() => (showFilters = !showFilters)}
			class="surface flex h-10 items-center gap-2 rounded-lg px-3 text-sm hover:bg-[var(--bg-sunken)] lg:hidden"
		>
			<SlidersHorizontal class="size-4" /> Filters
			{#if activeCount}
				<span
					class="tnum rounded bg-[var(--accent)] px-1.5 text-xs text-[var(--accent-fg)]"
					>{activeCount}</span
				>
			{/if}
		</button>

		<button
			onclick={copyLink}
			title="Copy a link to this exact search"
			class="surface flex h-10 items-center gap-2 rounded-lg px-3 text-sm hover:bg-[var(--bg-sunken)]"
		>
			{#if copied}
				<Check class="size-4 text-[var(--color-trust-high)]" /> Copied
			{:else}
				<Link2 class="size-4" /> Share
			{/if}
		</button>

		{#if activeCount}
			<button
				onclick={() => {
					const keepDeclared = filters.includeDeclared;
					filters = { ...defaultFilters(), includeDeclared: keepDeclared, query: filters.query };
				}}
				class="flex h-10 items-center gap-1 rounded-lg px-2 text-sm text-[var(--fg-muted)] hover:text-[var(--fg)]"
			>
				<X class="size-3.5" /> Clear
			</button>
		{/if}
	</div>

	<div class="grid gap-8 lg:grid-cols-[240px_1fr]">
		<aside class={showFilters ? 'block' : 'hidden lg:block'}>
			<div class="lg:sticky lg:top-20">
				<FilterPanel bind:filters />
			</div>
		</aside>

		<div>
			{#if catalog.error}
				<p class="text-[var(--color-trust-low)]">Failed to load catalogue: {catalog.error}</p>
			{:else if !catalog.ready}
				<p class="flex items-center gap-2 py-16 text-[var(--fg-muted)]">
					<Loader2 class="size-4 animate-spin" /> Loading catalogue…
				</p>
			{:else}
				<p class="tnum mb-3 text-sm text-[var(--fg-subtle)]">
					{results.length.toLocaleString()} result{results.length === 1 ? '' : 's'}
				</p>

				{#if results.length === 0}
					<div class="surface rounded-[var(--radius-card)] p-10 text-center">
						<p class="font-medium">Nothing matches those filters.</p>
						<p class="mt-1 text-sm text-[var(--fg-muted)]">
							Try relaxing the permission or score constraints
							{#if !filters.includeDeclared}, or include license-declared extensions{/if}.
						</p>
					</div>
				{:else}
					<div class="space-y-2.5">
						{#each visible as item (item.id)}
							<ExtensionRow {item} />
						{/each}
					</div>

					{#if results.length > limit}
						<button
							onclick={() => (limit += 60)}
							class="surface mt-6 w-full rounded-lg py-3 text-sm font-medium hover:bg-[var(--bg-sunken)]"
						>
							Show more ({(results.length - limit).toLocaleString()} remaining)
						</button>
					{/if}
				{/if}
			{/if}
		</div>
	</div>
</main>
