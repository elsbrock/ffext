<script lang="ts">
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import { base } from '$app/paths';
	import Badge from '$lib/components/Badge.svelte';
	import ScoreBadge from '$lib/components/ScoreBadge.svelte';
	import Seo from '$lib/components/Seo.svelte';
	import { SITE_DESCRIPTION, SITE_TITLE, SITE_URL } from '$lib/seo';
	import { catalog } from '$lib/catalog.svelte';
	import type { ExtensionDetail } from '$lib/types';
	import {
		bandClasses,
		categoryLabel,
		cn,
		dataCollectionLabel,
		formatAge,
		formatBytes,
		extIdFromParam,
		extPath,
		licenseFamilyLabel,
		sameLink,
		scoreBand
	} from '$lib/utils';
	import {
		AlertTriangle,
		ArrowLeft,
		ExternalLink,
		GitBranch,
		Globe,
		Loader2,
		ShieldCheck
	} from 'lucide-svelte';

	let ext = $state<ExtensionDetail | null>(null);
	let loading = $state(true);
	let notFound = $state(false);

	$effect(() => {
		const id = extIdFromParam(page.params.id ?? '');
		loading = true;
		notFound = false;
		let cancelled = false;
		catalog
			.detail(id)
			.then((d) => {
				if (cancelled) return;
				ext = d;
				notFound = !d;
			})
			.catch(() => !cancelled && (notFound = true))
			.finally(() => !cancelled && (loading = false));
		return () => {
			cancelled = true;
		};
	});

	const COMPONENT_ORDER = [
		['source', 'Source availability'],
		['permissions', 'Permission footprint'],
		['dataCollection', 'Data collection'],
		['maintenance', 'Maintenance'],
		['adoption', 'Adoption & reputation']
	] as const;

	// Meta descriptions are truncated on a word boundary; a mid-word cut reads as
	// broken to anyone seeing it in a search result.
	function clamp(s: string, max = 155): string {
		const t = s.replace(/\s+/g, ' ').trim();
		if (t.length <= max) return t;
		const cut = t.slice(0, max - 1);
		return `${cut.slice(0, cut.lastIndexOf(' ')) || cut}…`;
	}

	const metaDescription = $derived(
		ext
			? clamp(
					`${ext.summary || ext.name} — ${ext.license.name}, trust score ${ext.score}/100 on ffext.`
				)
			: SITE_DESCRIPTION
	);

	// The slug is decoration on top of the id, so several paths resolve to this
	// same page — /ext/123, an outdated slug, a truncated copy-paste. One of them
	// is canonical, and both crawlers and the address bar should see that one.
	const canonicalPath = $derived(ext ? extPath(ext.id, ext.slug) : `/ext/${page.params.id}`);

	$effect(() => {
		if (!ext) return;
		if (page.url.pathname === `${base}${canonicalPath}`) return;
		replaceState(`${base}${canonicalPath}${page.url.search}`, page.state);
	});

	const schema = $derived(
		ext
			? {
					'@context': 'https://schema.org',
					'@type': 'SoftwareApplication',
					name: ext.name,
					description: ext.summary || undefined,
					url: `${SITE_URL}${extPath(ext.id, ext.slug)}`,
					applicationCategory: 'BrowserApplication',
					operatingSystem: 'Firefox',
					softwareVersion: ext.version || undefined,
					dateModified: ext.lastUpdated || undefined,
					license: ext.license.url || undefined,
					sameAs: [ext.amoUrl, ext.repo?.url, ext.homepage].filter(Boolean),
					author: ext.authors.length
						? ext.authors.map((a) => ({ '@type': 'Person', name: a.name }))
						: undefined,
					offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
					aggregateRating:
						ext.ratings.count && ext.ratings.average
							? {
									'@type': 'AggregateRating',
									ratingValue: ext.ratings.average,
									ratingCount: ext.ratings.count,
									bestRating: 5,
									worstRating: 1
								}
							: undefined
				}
			: null
	);
</script>

<Seo
	title={ext ? `${ext.name} — trust profile on ffext` : SITE_TITLE}
	description={metaDescription}
	path={canonicalPath}
	{schema}
	noindex={notFound}
/>

<main class="mx-auto max-w-5xl px-4 py-8">
	<a
		href="{base}/"
		class="mb-6 inline-flex items-center gap-1.5 text-sm text-[var(--fg-muted)] hover:text-[var(--fg)]"
	>
		<ArrowLeft class="size-4" /> Back to directory
	</a>

	{#if loading}
		<p class="flex items-center gap-2 py-16 text-[var(--fg-muted)]">
			<Loader2 class="size-4 animate-spin" /> Loading…
		</p>
	{:else if notFound || !ext}
		<p class="py-16 text-[var(--fg-muted)]">Extension not found in this catalogue.</p>
	{:else}
		<header class="flex flex-wrap items-start gap-5">
			<div
				class="grid size-16 shrink-0 place-items-center overflow-hidden rounded-xl bg-[var(--bg-sunken)]"
			>
				{#if ext.icon}
					<img src={ext.icon} alt="" class="size-16 object-contain" />
				{:else}
					<Globe class="size-7 text-[var(--fg-subtle)]" />
				{/if}
			</div>

			<div class="min-w-0 flex-1">
				<h1 class="text-2xl font-bold tracking-tight">{ext.name}</h1>
				<p class="mt-1 text-sm text-[var(--fg-muted)]">
					by {ext.authors.map((a) => a.name).join(', ') || 'unknown'}
					{#if ext.version}· v{ext.version}{/if}
				</p>
				<div class="mt-3 flex flex-wrap gap-1.5">
					{#if ext.tier === 'verified'}
						<Badge variant="high"><GitBranch class="size-3" /> Source available</Badge>
					{:else}
						<Badge variant="mid">License declared, no public source</Badge>
					{/if}
					<Badge variant="outline" title={licenseFamilyLabel[ext.license.family]}>
						{ext.license.name}
					</Badge>
					{#each ext.promoted as p (p)}
						<Badge variant="accent">Mozilla {p}</Badge>
					{/each}
					{#each ext.categories as c (c)}
						<Badge>{categoryLabel[c] ?? c}</Badge>
					{/each}
				</div>
			</div>

			<div class="flex flex-col items-center gap-1">
				<ScoreBadge score={ext.score} size="lg" />
				<span class="text-xs text-[var(--fg-subtle)]">trust score</span>
			</div>
		</header>

		{#if ext.summary}
			<p class="mt-6 text-[var(--fg-muted)]">{ext.summary}</p>
		{/if}

		<div class="mt-6 flex flex-wrap gap-2">
			{#if ext.repo}
				<a
					href={ext.repo.url}
					rel="noopener noreferrer"
					target="_blank"
					class="surface inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium hover:bg-[var(--bg-sunken)]"
				>
					<GitBranch class="size-4" /> {ext.repo.owner}/{ext.repo.name}
					<ExternalLink class="size-3 text-[var(--fg-subtle)]" />
				</a>
			{/if}
			{#if ext.repo?.source === 'description'}
				<!-- Found by scanning free text rather than in a metadata field, so it
				     may well be a library or a fork parent. Saying so beats presenting
				     a guess with the same confidence as a declared project home. -->
				<span
					class="inline-flex items-center gap-1.5 self-center text-xs text-[var(--fg-subtle)]"
					title="This link was matched in the extension's description text, not in AMO's homepage or support fields. It may not be this extension's own repository."
				>
					<AlertTriangle class="size-3.5" /> repo link taken from the description
				</span>
			{/if}
			<a
				href={ext.amoUrl}
				rel="noopener noreferrer"
				target="_blank"
				class="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-[var(--accent-fg)] hover:opacity-90"
			>
				Install from AMO <ExternalLink class="size-3" />
			</a>
			{#if ext.homepage && !sameLink(ext.homepage, ext.repo?.url)}
				<a
					href={ext.homepage}
					rel="noopener noreferrer"
					target="_blank"
					class="surface inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-[var(--bg-sunken)]"
				>
					Homepage <ExternalLink class="size-3 text-[var(--fg-subtle)]" />
				</a>
			{/if}
		</div>

		<!-- Score breakdown: the whole point of the directory is that this is inspectable. -->
		<section class="mt-10">
			<h2 class="mb-3 text-lg font-semibold">How this score was calculated</h2>
			<div class="surface divide-y rounded-[var(--radius-card)]">
				{#each COMPONENT_ORDER as [key, title] (key)}
					{@const c = ext.components[key]}
					{#if c}
						{@const pct = Math.round((c.points / c.max) * 100)}
						<div class="flex items-center gap-4 p-4">
							<div class="min-w-0 flex-1">
								<div class="flex items-baseline justify-between gap-3">
									<span class="font-medium">{title}</span>
									<span class="tnum text-sm text-[var(--fg-subtle)]">{c.points}/{c.max}</span>
								</div>
								<p class="mt-0.5 text-sm text-[var(--fg-muted)]">{c.label}</p>
								<div class="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--bg-sunken)]">
									<div
										class={cn(
											'h-full rounded-full',
											pct >= 75
												? 'bg-[var(--color-trust-high)]'
												: pct >= 40
													? 'bg-[var(--color-trust-mid)]'
													: 'bg-[var(--color-trust-low)]'
										)}
										style="width: {pct}%"
									></div>
								</div>
							</div>
						</div>
					{/if}
				{/each}
			</div>
			{#if ext.license.isAmoDefault && !ext.repo}
				<p
					class={cn(
						'mt-3 flex gap-2 rounded-lg border p-3 text-sm',
						bandClasses[scoreBand(20)]
					)}
				>
					<AlertTriangle class="mt-0.5 size-4 shrink-0" />
					<span>
						MPL-2.0 is the pre-selected default in Mozilla's submission form, and no public
						repository was found. Treat the license claim as unverified.
					</span>
				</p>
			{/if}
		</section>

		<section class="mt-10 grid gap-6 md:grid-cols-2">
			<div>
				<h2 class="mb-3 text-lg font-semibold">Permissions</h2>
				{#if ext.permissions.broadHostAccess}
					<p
						class="mb-3 flex gap-2 rounded-lg border border-[var(--color-trust-low)]/35 bg-[var(--color-trust-low)]/10 p-3 text-sm text-[var(--color-trust-low)]"
					>
						<AlertTriangle class="mt-0.5 size-4 shrink-0" />
						This extension can read and change data on every site you visit.
					</p>
				{/if}

				{#each [['high', 'Sensitive'], ['medium', 'Moderate'], ['low', 'Low risk']] as [level, label] (level)}
					{@const list = ext.permissions[level as 'high' | 'medium' | 'low']}
					{#if list.length}
						<h3 class="mt-3 mb-1.5 text-xs font-semibold tracking-wide text-[var(--fg-subtle)] uppercase">
							{label}
						</h3>
						<ul class="space-y-1.5">
							{#each list as p (p)}
								<li class="text-sm">
									<code
										class={cn(
											'rounded px-1 py-0.5 font-mono text-xs',
											level === 'high'
												? 'bg-[var(--color-trust-low)]/10 text-[var(--color-trust-low)]'
												: 'bg-[var(--bg-sunken)] text-[var(--fg-muted)]'
										)}>{p}</code
									>
									{#if ext.permissionHelp[p]}
										<span class="ml-1 text-[var(--fg-muted)]">— {ext.permissionHelp[p]}</span>
									{/if}
								</li>
							{/each}
						</ul>
					{/if}
				{/each}

				{#if !ext.permissions.high.length && !ext.permissions.medium.length && !ext.permissions.low.length}
					<p class="flex items-center gap-2 text-sm text-[var(--color-trust-high)]">
						<ShieldCheck class="size-4" /> Requests no special permissions.
					</p>
				{/if}
			</div>

			<div>
				<h2 class="mb-3 text-lg font-semibold">Facts</h2>
				<dl class="surface tnum divide-y rounded-[var(--radius-card)] text-sm">
					{#snippet fact(k: string, v: string)}
						<div class="flex justify-between gap-4 px-4 py-2.5">
							<dt class="text-[var(--fg-muted)]">{k}</dt>
							<dd class="text-right font-medium">{v}</dd>
						</div>
					{/snippet}
					{@render fact('Data collection', dataCollectionLabel[ext.dataCollection.state])}
					{@render fact('Daily users', ext.users.toLocaleString())}
					{@render fact(
						'Rating',
						ext.ratings.count
							? `${(ext.ratings.average ?? 0).toFixed(1)} / 5 (${ext.ratings.count.toLocaleString()})`
							: 'unrated'
					)}
					{@render fact('Last updated', formatAge(ext.ageDays))}
					{@render fact('First published', ext.created?.slice(0, 10) ?? '—')}
					{@render fact('Package size', formatBytes(ext.xpiSize))}
					{@render fact('Privacy policy', ext.hasPrivacyPolicy ? 'yes' : 'none')}
					{#if ext.dataCollection.required.length}
						{@render fact('Collects', ext.dataCollection.required.join(', '))}
					{/if}
				</dl>
			</div>
		</section>

		{#if ext.description}
			<section class="mt-10">
				<h2 class="mb-3 text-lg font-semibold">Description</h2>
				<p class="text-sm whitespace-pre-line text-[var(--fg-muted)]">{ext.description}</p>
			</section>
		{/if}
	{/if}
</main>
