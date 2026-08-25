<script lang="ts">
	import Seo from '$lib/components/Seo.svelte';
	import { catalog } from '$lib/catalog.svelte';
	import { REPO_URL } from '$lib/seo';
	import GithubMark from '$lib/components/GithubMark.svelte';
	import { MessagesSquare } from 'lucide-svelte';

	const meta = $derived(catalog.meta);
	const n = (v: number | undefined) => (v ?? 0).toLocaleString();

	const SECTIONS = [
		['listed', 'What gets listed'],
		['tiers', 'Source available vs. license declared'],
		['repo', 'How a repository is found'],
		['score', 'The score, component by component'],
		['sorting', 'Sorting and search'],
		['limits', 'What this cannot tell you'],
		['contact', 'Corrections and contact']
	] as const;

	const SCORE_ROWS: { component: string; max: number; rules: [string, string][] }[] = [
		{
			component: 'Source availability',
			max: 30,
			rules: [
				['Public repository linked', '30'],
				['No repository, license deliberately chosen', '6'],
				["No repository, license is AMO's MPL-2.0 default", '0']
			]
		},
		{
			component: 'Permission footprint',
			max: 25,
			rules: [
				['Starts at', '25'],
				['Requests access to all websites', '−12'],
				['Each other sensitive permission (max −9)', '−3'],
				['Each moderate permission (max −4)', '−1']
			]
		},
		{
			component: 'Data collection',
			max: 15,
			rules: [
				['Declares it collects nothing', '15'],
				['Discloses n data types', '11 − 2n, floor 3'],
				['No disclosure at all', '5']
			]
		},
		{
			component: 'Maintenance',
			max: 15,
			rules: [
				['Updated within 6 months', '15'],
				['Within a year', '12'],
				['Within 2 years', '7'],
				['2–4 years', '3'],
				['Older, or unknown', '0']
			]
		},
		{
			component: 'Adoption & reputation',
			max: 15,
			rules: [
				['Daily users, log-scaled', 'up to 9'],
				['Rating, only once 5+ ratings exist', 'up to 6']
			]
		}
	];
</script>

<Seo
	title="Methodology — how ffext scores Firefox extensions"
	description="Every rule behind the 0-100 trust score: what gets listed, how repository links are found and why that is weaker than it looks, the exact points per component, and what the data cannot tell you."
	path="/methodology"
	type="article"
/>

<main class="mx-auto max-w-3xl px-4 py-10">
	<h1 class="text-3xl font-bold tracking-tight">Methodology</h1>
	<p class="mt-3 text-[var(--fg-muted)]">
		Every number on this site comes from the rules below. They are worth reading before trusting a
		score, particularly the part about what a repository link does and does not prove.
	</p>

	<nav class="surface mt-6 rounded-[var(--radius-card)] p-4">
		<ol class="tnum grid gap-1 text-sm sm:grid-cols-2">
			{#each SECTIONS as [id, title], i (id)}
				<li>
					<a href="#{id}" class="text-[var(--fg-muted)] hover:text-[var(--fg)]">
						<span class="text-[var(--fg-subtle)]">{i + 1}.</span>
						{title}
					</a>
				</li>
			{/each}
		</ol>
	</nav>

	<div class="mt-10 space-y-12 text-[var(--fg-muted)]">
		<section id="listed" class="scroll-mt-20">
			<h2 class="mb-3 text-lg font-semibold text-[var(--fg)]">What gets listed</h2>
			<p>
				Every Firefox extension on addons.mozilla.org whose declared license is OSI- or
				FSF-approved. Extensions marked
				<code class="font-mono text-sm">all-rights-reserved</code> are excluded.
			</p>
			<p class="mt-3">
				Mozilla also lets an author skip the license dropdown and supply a custom license, which
				arrives as free text. Most of those are genuinely proprietary — <em>Norton License
					Agreement</em>, <em>Honey Terms of Use</em> — but a minority are ordinary OSS licenses
				typed by hand: Tridactyl ships Apache-2.0 under the name <em>Apache v2</em>. Those are
				recovered by matching the name, in full and exactly, against a fixed list of OSS license
				names. Exact match, never substring — <em>ISC License + CC-BY</em> is a combination,
				<em>No License</em> is the opposite of <em>Unlicense</em> — and a version is always
				required where one exists. Every name the list does not carry stays excluded; we do not
				guess, so an extension named merely <em>Custom License</em> is missing from this
				directory even when its code is on GitHub.
			</p>
			<p class="mt-3">
				A recovered license is marked as such on the extension's page, alongside the text the
				author actually wrote. It is not scored differently: both routes are the author's own
				claim about their own work, and neither is verified against the license text or the
				shipped code.
			</p>
			{#if meta}
				<div class="tnum mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
					{#each [['Crawled', meta.crawledTotal], ['Listed', meta.listed], ['Source available', meta.tiers.verified], ['Excluded, closed', meta.excludedNonOss], ['License read from a custom name', meta.licenseSources.customName], ['Custom names we could not read', meta.excludedCustomUnmatched]] as [label, value] (label)}
						<div class="surface rounded-lg p-3">
							<div class="text-xl font-semibold text-[var(--fg)]">{n(value as number)}</div>
							<div class="text-xs text-[var(--fg-subtle)]">{label}</div>
						</div>
					{/each}
				</div>
				<p class="mt-3 text-sm">
					The AMO search API refuses to page past 30,000 results for any single query, while the
					catalogue is roughly 96,600. The crawler slices by category, each one individually under
					that ceiling, and unions the results on addon id.
				</p>
				<p class="mt-3 text-sm">
					The whole corpus is re-crawled weekly and republished in one piece — there is no
					incremental update, so every number on the site comes from a single consistent
					snapshot, taken on {meta.generated.slice(0, 10)}. A rebuild that loses more than a
					tenth of the catalogue is rejected rather than published, on the assumption that the
					crawl broke rather than that AMO shrank.
				</p>
			{/if}
		</section>

		<section id="tiers" class="scroll-mt-20">
			<h2 class="mb-3 text-lg font-semibold text-[var(--fg)]">
				Source available vs. license declared
			</h2>
			<p>
				{#if meta}
					Of {n(meta.listed)} open source licensed extensions, only
					<strong class="text-[var(--fg)]">{n(meta.tiers.verified)}</strong> link a public repository.
				{/if}
				MPL-2.0 is the option Mozilla's submission form pre-selects, so a large share of "open
				source" extensions carry it because nobody changed a dropdown. A license claim with no
				published code cannot be checked by anyone, including us.
			</p>
			<p class="mt-3">
				Both tiers are listed, never as equivalents. The declared tier is hidden by default, is
				excluded from the sitemap, and an extension in it can score at most 76 out of 100.
			</p>
		</section>

		<section id="repo" class="scroll-mt-20">
			<h2 class="mb-3 text-lg font-semibold text-[var(--fg)]">How a repository is found</h2>
			<p>
				This is the weakest link in the whole scoring model, so it is worth being precise. A
				repository is a URL on one of
				{#if meta}{meta.forgeHosts.length}{/if} known public forges
				{#if meta}
					<span class="text-[var(--fg-subtle)]">({meta.forgeHosts.join(', ')})</span>
				{/if}
				found in one of two places, in this order:
			</p>
			{#if meta}
				<div class="surface mt-4 divide-y rounded-[var(--radius-card)]">
					<div class="p-4">
						<div class="flex items-baseline justify-between gap-3">
							<span class="font-medium text-[var(--fg)]">AMO metadata</span>
							<span class="tnum text-sm">{n(meta.repoSources.metadata)}</span>
						</div>
						<p class="mt-1 text-sm">
							The <code class="font-mono text-xs">homepage</code> or
							<code class="font-mono text-xs">support_url</code> field. The author put it there as the
							project's home, which is about as good as this gets.
						</p>
					</div>
					<div class="p-4">
						<div class="flex items-baseline justify-between gap-3">
							<span class="font-medium text-[var(--fg)]">Description text</span>
							<span class="tnum text-sm">{n(meta.repoSources.description)}</span>
						</div>
						<p class="mt-1 text-sm">
							A forge URL matched anywhere in the description, summary or developer comments. This
							is a guess. It can just as easily be a library the extension uses, a project it was
							forked from, or someone else's issue tracker. Detail pages label these links so you
							can judge for yourself.
						</p>
					</div>
				</div>
			{/if}
			<p class="mt-4">
				Nothing else happens. The URL is never fetched, so a repository that is deleted, renamed or
				private still counts. The owner is not correlated with the AMO author. And no check
				anywhere establishes that the code in that repository is the code inside the XPI you
				install — that would need reproducible builds, which neither AMO nor this site does.
			</p>
			<p class="mt-3">
				Self-hosted Gitea, Forgejo and cgit instances are not recognised, so the source-available
				count is an undercount rather than an overcount.
			</p>
		</section>

		<section id="score" class="scroll-mt-20">
			<h2 class="mb-3 text-lg font-semibold text-[var(--fg)]">The score, component by component</h2>
			<p class="mb-4">
				100 points across five components. Every extension's page itemises what it scored and why,
				so nothing here is a black box.
			</p>
			<div class="space-y-4">
				{#each SCORE_ROWS as row (row.component)}
					<div class="surface rounded-[var(--radius-card)] p-4">
						<div class="mb-2 flex items-baseline justify-between gap-3">
							<h3 class="font-medium text-[var(--fg)]">{row.component}</h3>
							<span class="tnum text-sm text-[var(--fg-subtle)]">{row.max} pts</span>
						</div>
						<table class="w-full text-sm">
							<tbody>
								{#each row.rules as [rule, points] (rule)}
									<tr class="border-t border-[var(--border)] first:border-0">
										<td class="py-1.5 pr-3">{rule}</td>
										<td class="tnum w-24 py-1.5 text-right whitespace-nowrap">{points}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/each}
			</div>
			<p class="mt-4">
				Popularity is capped at 9 of 100 and log-scaled, so a million users cannot carry a listing
				that fails everywhere else. Mozilla's Recommended, Line and Spotlight badges are displayed
				but deliberately excluded from the score: that is Mozilla's editorial judgment, and this
				directory exists to offer an independent one.
			</p>
		</section>

		<section id="sorting" class="scroll-mt-20">
			<h2 class="mb-3 text-lg font-semibold text-[var(--fg)]">Sorting and search</h2>
			<p>
				Sorting by rating does not use the raw average. Most extensions here are rated by a handful
				of people — thousands hold a perfect 5.0 from three ratings or fewer — so each average is
				pulled toward the corpus mean in proportion to how little evidence supports it:
			</p>
			<pre class="surface mt-3 overflow-x-auto rounded-lg p-3 font-mono text-xs">weighted = (average × count + corpus_mean × 20) / (count + 20)</pre>
			<p class="mt-3">
				Twenty is roughly the 90th percentile of rating counts. Below it an extension mostly
				inherits the corpus average, and extensions with no ratings sort last rather than tying in
				the middle.
			</p>
			<p class="mt-3">
				Search ranks by where a term matches — an exact name beats a name that merely contains the
				word, which beats a mention in the summary — with small nudges for daily users and trust
				score to order otherwise equal matches. Accents are folded, and if nothing matches exactly
				it retries allowing one typo per word.
			</p>
		</section>

		<section id="limits" class="scroll-mt-20">
			<h2 class="mb-3 text-lg font-semibold text-[var(--fg)]">What this cannot tell you</h2>
			<ul class="space-y-2">
				<li>
					<strong class="text-[var(--fg)]">Whether an extension is safe.</strong> Every signal here
					is about how much of it can be checked, by anyone, from the outside. A high score means a
					reviewer has somewhere to look. It is not a review.
				</li>
				<li>
					<strong class="text-[var(--fg)]">Whether the shipped code matches the repository.</strong>
					See above. Nothing verifies this.
				</li>
				<li>
					<strong class="text-[var(--fg)]">What the code actually does.</strong> Permission risk is derived
					from the manifest the AMO API reports, not from reading the code. An extension asking for little
					can still do a lot by loading remote code at runtime.
				</li>
				<li>
					<strong class="text-[var(--fg)]">What data is really collected.</strong> Data collection is
					self-declared by the author. An undisclosed collector looks identical to one that collects
					nothing and forgot to say so.
				</li>
				<li>
					<strong class="text-[var(--fg)]">What changed recently.</strong>
					{#if meta}
						This is a point-in-time crawl from {meta.generated.slice(0, 10)},
					{:else}
						This is a point-in-time crawl,
					{/if} re-taken weekly, not a live feed. An extension published or updated since that date
					is missing or out of date here for up to a week, and "last updated" ages against the crawl
					date rather than today.
				</li>
			</ul>
		</section>

		<section id="contact" class="scroll-mt-20">
			<h2 class="mb-3 text-lg font-semibold text-[var(--fg)]">Corrections and contact</h2>
			<p>
				A misattributed repository, a license classified wrongly, an extension that should not be
				listed: all of it is worth reporting, and the scoring weights in particular are the part
				least settled. The crawler, the scoring and this site are in one repository under AGPL-3.0,
				so you can check what any rule does before arguing with it.
			</p>
			<div class="mt-4 flex flex-wrap gap-2">
				<a
					href="{REPO_URL}/issues/new"
					rel="noopener noreferrer"
					target="_blank"
					class="surface inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium hover:bg-[var(--bg-sunken)]"
				>
					<GithubMark class="size-4" /> Open an issue
				</a>
				<a
					href="{REPO_URL}/discussions"
					rel="noopener noreferrer"
					target="_blank"
					class="surface inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-[var(--bg-sunken)]"
				>
					<MessagesSquare class="size-4" /> Discussions
				</a>
			</div>
			<p class="mt-4 text-sm text-[var(--fg-subtle)]">
				ffext is not affiliated with Mozilla. Data comes from the public addons.mozilla.org API.
			</p>
		</section>
	</div>
</main>
