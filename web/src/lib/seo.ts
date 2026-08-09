/** Canonical origin. Every absolute URL emitted for crawlers derives from this,
 *  so a domain move is a one-line change. */
export const SITE_URL = 'https://ffext.iodev.org';
export const SITE_NAME = 'ffext';

export const SITE_TITLE = 'ffext — open source Firefox extensions you can verify';

/** Kept free of counts on purpose: the corpus is re-crawled, and a description
 *  that quotes a number goes stale the moment the index is rebuilt. */
export const SITE_DESCRIPTION =
	'Open source Firefox extensions ranked by what you can verify: public source, permission footprint, data collection and maintenance — not download counts.';

export const OG_IMAGE = `${SITE_URL}/og.png`;

/** The directory's own source. A site that ranks extensions on whether their
 *  code is public has to have public code. */
export const REPO_URL = 'https://github.com/elsbrock/ffext';

/** For corrections that do not belong in a public issue. Plus-addressed so mail
 *  about this site can be filtered from everything else. */
export const CONTACT_EMAIL = 'simon+ffext@iodev.org';

/** Absolute URL for a route path. */
export function absolute(path: string): string {
	if (!path || path === '/') return `${SITE_URL}/`;
	return `${SITE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

/** Serialise JSON-LD for inline injection. `<` is escaped so a hostile value
 *  can never close the surrounding script element. */
export function jsonLd(data: unknown): string {
	return JSON.stringify(data).replace(/</g, '\\u003c');
}
