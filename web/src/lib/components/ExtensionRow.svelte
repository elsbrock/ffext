<script lang="ts">
	import { base } from '$app/paths';
	import Badge from './Badge.svelte';
	import ScoreBadge from './ScoreBadge.svelte';
	import type { IndexItem } from '$lib/types';
	import { formatAge, formatUsers, iconUrl, licenseFamilyLabel } from '$lib/utils';
	import { GitBranch, Globe, ShieldCheck, ShieldAlert, Star, Users } from 'lucide-svelte';

	let { item }: { item: IndexItem } = $props();
	const icon = $derived(iconUrl(item));
</script>

<a
	href="{base}/ext/{item.id}"
	class="surface group grid grid-cols-[auto_1fr_auto] items-start gap-x-4 gap-y-2 rounded-[var(--radius-card)] p-4 transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--bg-sunken)]"
>
	<div
		class="grid size-11 shrink-0 place-items-center overflow-hidden rounded-lg bg-[var(--bg-sunken)]"
	>
		{#if icon}
			<img src={icon} alt="" class="size-11 object-contain" loading="lazy" decoding="async" />
		{:else}
			<Globe class="size-5 text-[var(--fg-subtle)]" />
		{/if}
	</div>

	<div class="min-w-0">
		<div class="flex flex-wrap items-center gap-2">
			<h3 class="truncate font-semibold group-hover:text-[var(--accent)]">{item.n}</h3>
			{#if item.t === 'verified'}
				<Badge variant="high" title="A public source repository is linked">
					<GitBranch class="size-3" /> Source
				</Badge>
			{/if}
			{#if item.pr.includes('recommended')}
				<Badge variant="accent" title="Mozilla Recommended">Recommended</Badge>
			{/if}
		</div>

		<p class="mt-1 line-clamp-2 text-sm text-[var(--fg-muted)]">{item.d}</p>

		<div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--fg-subtle)]">
			<span class="font-mono" title={licenseFamilyLabel[item.lf]}>{item.l}</span>
			<span class="tnum inline-flex items-center gap-1">
				<Users class="size-3" />{formatUsers(item.u)}
			</span>
			{#if item.rc > 0}
				<!-- The count is shown next to the average because the average alone is
				     not comparable: most extensions here are rated by a handful of people. -->
				<span
					class="tnum inline-flex items-center gap-1"
					title="{item.r.toFixed(1)} out of 5 from {item.rc.toLocaleString()} rating{item.rc ===
					1
						? ''
						: 's'}"
				>
					<Star class="size-3" />{item.r.toFixed(1)}
					<span class="text-[var(--fg-subtle)]">({formatUsers(item.rc)})</span>
				</span>
			{/if}
			<span class="tnum">{formatAge(item.ag)}</span>
			{#if item.bh}
				<span class="inline-flex items-center gap-1 text-[var(--color-trust-low)]">
					<ShieldAlert class="size-3" /> All sites
				</span>
			{:else if item.hp === 0}
				<span class="inline-flex items-center gap-1 text-[var(--color-trust-high)]">
					<ShieldCheck class="size-3" /> Narrow access
				</span>
			{/if}
			{#if item.dc === 'none'}
				<span class="text-[var(--color-trust-high)]">No data collected</span>
			{/if}
		</div>
	</div>

	<ScoreBadge score={item.sc} />
</a>
