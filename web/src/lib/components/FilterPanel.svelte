<script lang="ts">
	import type { Filters } from '$lib/catalog.svelte';
	import { catalog } from '$lib/catalog.svelte';
	import { categoryLabel, licenseFamilyLabel } from '$lib/utils';
	import { Loader2 } from 'lucide-svelte';

	let { filters = $bindable() }: { filters: Filters } = $props();

	const LICENSE_FAMILIES = [
		'permissive',
		'public-domain',
		'weak-copyleft',
		'copyleft',
		'strong-copyleft'
	] as const;

	const DATA_STATES = [
		{ key: 'none', label: 'Declares no collection' },
		{ key: 'declared', label: 'Discloses what it collects' },
		{ key: 'undisclosed', label: 'Not disclosed' }
	];

	const categories = $derived(Object.keys(catalog.meta?.categories ?? {}));

	function toggle(set: Set<string>, key: string): Set<string> {
		const next = new Set(set);
		next.has(key) ? next.delete(key) : next.add(key);
		return next;
	}
</script>

{#snippet check(checked: boolean, label: string, onchange: () => void, hint?: string)}
	<label class="flex cursor-pointer items-start gap-2 py-1 text-sm text-[var(--fg-muted)] hover:text-[var(--fg)]">
		<input
			type="checkbox"
			{checked}
			{onchange}
			class="mt-0.5 size-3.5 shrink-0 accent-[var(--accent)]"
		/>
		<span>
			{label}
			{#if hint}<span class="block text-xs text-[var(--fg-subtle)]">{hint}</span>{/if}
		</span>
	</label>
{/snippet}

{#snippet group(title: string)}
	<h3 class="mb-2 text-xs font-semibold tracking-wide text-[var(--fg-subtle)] uppercase">
		{title}
	</h3>
{/snippet}

<div class="space-y-6">
	<section>
		{@render group('Source')}
		{@render check(
			filters.includeDeclared,
			'Include license-declared only',
			() => {
				filters.includeDeclared = !filters.includeDeclared;
				if (filters.includeDeclared) catalog.loadDeclared();
			},
			'Extensions with an open source license but no public repository we could find'
		)}
		{#if catalog.loadingDeclared}
			<p class="flex items-center gap-1.5 text-xs text-[var(--fg-subtle)]">
				<Loader2 class="size-3 animate-spin" /> Loading 52,699 more…
			</p>
		{/if}
	</section>

	<section>
		{@render group('Permissions')}
		{@render check(
			filters.excludeBroadHost,
			'Hide "access all websites"',
			() => (filters.excludeBroadHost = !filters.excludeBroadHost)
		)}
		{@render check(
			filters.excludeHighRisk,
			'Hide any sensitive permission',
			() => (filters.excludeHighRisk = !filters.excludeHighRisk)
		)}
	</section>

	<section>
		{@render group('Data collection')}
		{#each DATA_STATES as d (d.key)}
			{@render check(
				filters.dataCollection.has(d.key),
				d.label,
				() => (filters.dataCollection = toggle(filters.dataCollection, d.key))
			)}
		{/each}
	</section>

	<section>
		{@render group('Maintenance')}
		{@render check(
			filters.maintainedOnly,
			'Updated in the last 2 years',
			() => (filters.maintainedOnly = !filters.maintainedOnly)
		)}
	</section>

	<section>
		{@render group('Minimum trust score')}
		<div class="flex items-center gap-3">
			<input
				type="range"
				min="0"
				max="90"
				step="5"
				bind:value={filters.minScore}
				class="w-full accent-[var(--accent)]"
			/>
			<span class="tnum w-8 text-right text-sm font-medium">{filters.minScore}</span>
		</div>
	</section>

	<section>
		{@render group('License')}
		{#each LICENSE_FAMILIES as f (f)}
			{@render check(
				filters.licenseFamilies.has(f),
				licenseFamilyLabel[f],
				() => (filters.licenseFamilies = toggle(filters.licenseFamilies, f))
			)}
		{/each}
	</section>

	<section>
		{@render group('Category')}
		<div class="max-h-64 overflow-y-auto pr-1">
			{#each categories as c (c)}
				{@render check(
					filters.categories.has(c),
					categoryLabel[c] ?? c,
					() => (filters.categories = toggle(filters.categories, c))
				)}
			{/each}
		</div>
	</section>
</div>
