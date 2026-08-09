<script lang="ts">
	import { OG_IMAGE, SITE_DESCRIPTION, SITE_NAME, SITE_TITLE, absolute, jsonLd } from '$lib/seo';

	let {
		title = SITE_TITLE,
		description = SITE_DESCRIPTION,
		path = '/',
		type = 'website',
		noindex = false,
		schema = null
	}: {
		title?: string;
		description?: string;
		path?: string;
		type?: string;
		noindex?: boolean;
		schema?: unknown;
	} = $props();

	const url = $derived(absolute(path));
	// Injected as raw HTML because Svelte cannot nest a literal <script> here.
	const ld = $derived(
		schema
			? `<script type="application/ld+json">${jsonLd(schema)}<\/script>`
			: ''
	);
</script>

<svelte:head>
	<title>{title}</title>
	<meta name="description" content={description} />
	<link rel="canonical" href={url} />
	{#if noindex}
		<meta name="robots" content="noindex, follow" />
	{/if}

	<meta property="og:type" content={type} />
	<meta property="og:site_name" content={SITE_NAME} />
	<meta property="og:locale" content="en_US" />
	<meta property="og:url" content={url} />
	<meta property="og:title" content={title} />
	<meta property="og:description" content={description} />
	<meta property="og:image" content={OG_IMAGE} />
	<meta property="og:image:width" content="1200" />
	<meta property="og:image:height" content="630" />
	<meta property="og:image:alt" content="ffext — a trust-focused directory of open source Firefox extensions" />

	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content={title} />
	<meta name="twitter:description" content={description} />
	<meta name="twitter:image" content={OG_IMAGE} />

	{@html ld}
</svelte:head>
