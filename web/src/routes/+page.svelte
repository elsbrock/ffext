<script lang="ts">
	import ExtensionRow from '$lib/components/ExtensionRow.svelte';
	import FilterPanel from '$lib/components/FilterPanel.svelte';
	import { applyFilters, catalog, defaultFilters, type SortKey } from '$lib/catalog.svelte';
	import { Loader2, Search, SlidersHorizontal, X } from 'lucide-svelte';

	let filters = $state(defaultFilters());
	let showFilters = $state(false);
	let limit = $state(60);

	const pool = $derived(
		filters.includeDeclared ? [...catalog.verified, ...catalog.declared] : catalog.verified
	);
	const results = $derived(applyFilters(pool, filters));
	const visible = $derived(results.slice(0, limit));

	// Reset paging whenever the result set changes shape.
	$effect(() => {
		void filters;
		limit = 60;
	});

	const SORTS: { key: SortKey; label: string }[] = [
		{ key: 'score', label: 'Trust score' },
		{ key: 'users', label: 'Users' },
		{ key: 'updated', label: 'Recently updated' },
		{ key: 'rating', label: 'Rating' },
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

<svelte:head><title>ffext — open source Firefox extensions you can verify</title></svelte:head>

<main class="mx-auto max-w-7xl px-4 py-8">
	<section class="mb-8">
		<h1 class="text-3xl font-bold tracking-tight text-balance sm:text-4xl">
			Extensions you can actually check
		</h1>
		<p class="mt-3 max-w-2xl text-[var(--fg-muted)]">
			Every listing here is open source licensed. We rank by public source availability,
			permission footprint, data-collection disclosure and maintenance — not popularity.
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
