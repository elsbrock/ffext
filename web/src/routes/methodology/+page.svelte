<script lang="ts">
	import { catalog } from '$lib/catalog.svelte';
</script>

<svelte:head><title>Methodology — ffext</title></svelte:head>

<main class="mx-auto max-w-3xl px-4 py-10">
	<h1 class="text-3xl font-bold tracking-tight">Methodology</h1>

	<div class="mt-8 space-y-8 text-[var(--fg-muted)]">
		<section>
			<h2 class="mb-2 text-lg font-semibold text-[var(--fg)]">What gets listed</h2>
			<p>
				Every Firefox extension on addons.mozilla.org whose declared license is OSI- or
				FSF-approved. Extensions marked <code class="font-mono text-sm">all-rights-reserved</code>
				or carrying a free-text custom license are excluded — a custom license field cannot be
				reliably classified, so we do not guess.
			</p>
		</section>

		<section>
			<h2 class="mb-2 text-lg font-semibold text-[var(--fg)]">
				Why "source available" is a separate tier
			</h2>
			<p>
				{#if catalog.meta}
					Of {catalog.meta.listed.toLocaleString()} open source licensed extensions, only
					<strong class="text-[var(--fg)]"
						>{catalog.meta.tiers.verified.toLocaleString()}</strong
					> link a public repository.
				{/if}
				MPL-2.0 is the pre-selected default in Mozilla's submission form, which means a large
				share of "open source" extensions have that license simply because nobody changed the
				dropdown. A license claim with no published code cannot be checked by anyone. We list
				both, but we never present them as equivalent.
			</p>
		</section>

		<section>
			<h2 class="mb-2 text-lg font-semibold text-[var(--fg)]">The score</h2>
			<p class="mb-3">
				100 points across five components, every one itemised on each extension's page:
			</p>
			<ul class="space-y-1.5">
				<li><strong class="text-[var(--fg)]">Source availability (30)</strong> — is there a public repository?</li>
				<li><strong class="text-[var(--fg)]">Permission footprint (25)</strong> — inverted risk; broad host access is penalised heavily.</li>
				<li><strong class="text-[var(--fg)]">Data collection (15)</strong> — an explicit "collects nothing" beats saying nothing at all.</li>
				<li><strong class="text-[var(--fg)]">Maintenance (15)</strong> — how recently it was updated.</li>
				<li><strong class="text-[var(--fg)]">Adoption &amp; reputation (15)</strong> — log-scaled users plus rating, capped so popularity cannot dominate.</li>
			</ul>
			<p class="mt-3">
				Mozilla's own Recommended/Line/Spotlight status is shown as a badge but deliberately kept
				out of the score. That is Mozilla's editorial judgment; this directory exists to offer an
				independent one.
			</p>
		</section>

		<section>
			<h2 class="mb-2 text-lg font-semibold text-[var(--fg)]">Limits you should know</h2>
			<ul class="space-y-1.5">
				<li>
					Repository links are taken from AMO metadata and description text. We do not fetch them,
					so "source available" means <em>a public repo is claimed and discoverable</em> — not that
					the published code matches the shipped build. Nothing here is reproducible-build verified.
				</li>
				<li>
					Permission risk is derived from the manifest the AMO API reports, not from reading the
					extension's code. A narrow permission set is not proof of good behaviour.
				</li>
				<li>
					The snapshot is a point-in-time crawl{#if catalog.meta}
						({catalog.meta.generated.slice(0, 10)}){/if}, not a live feed.
				</li>
			</ul>
		</section>

		<section>
			<h2 class="mb-2 text-lg font-semibold text-[var(--fg)]">How the data is collected</h2>
			<p>
				The AMO search API caps any single query at 30,000 results while the corpus is roughly
				96,600, so the crawler slices by category — each is individually under the ceiling — and
				unions the results on addon id. This snapshot captured
				{#if catalog.meta}{catalog.meta.crawledTotal.toLocaleString()}{/if} extensions, about 99.9% of
				the catalogue.
			</p>
		</section>
	</div>
</main>
