/**
 * Static-asset worker with an explicit SPA fallback, fronting the index in R2.
 *
 * Cloudflare's built-in `single-page-application` not-found handling always
 * serves /index.html, but index.html here is the prerendered landing page.
 * Client-side routes (/ext/<id>) need the route-less shell instead, so asset
 * misses fall through to this worker, which serves 200.html with a 200 status —
 * a 404 would keep those pages out of the index.
 *
 * The crawled index is not part of the asset bundle. It is rebuilt weekly by
 * .github/workflows/refresh-index.yml and written to R2, so a code deploy and a
 * data refresh never touch each other: pushing a commit cannot blank the
 * directory, and refreshing the corpus does not rebuild the site. The paths it
 * owns are listed in `run_worker_first` in wrangler.jsonc, which routes them
 * here ahead of the asset layer — otherwise a stray bundled copy would shadow
 * R2 and serve a stale index that nothing updates.
 */

interface Env {
	ASSETS: Fetcher;
	INDEX: R2Bucket;
}

const SHELL = '/200.html';

/** Paths served from R2. Mirrored by `run_worker_first` in wrangler.jsonc. */
const isIndexPath = (p: string) => p.startsWith('/data/') || p === '/sitemap.xml';

const contentType = (p: string) =>
	p.endsWith('.json') ? 'application/json; charset=utf-8' : 'application/xml; charset=utf-8';

async function serveIndex(request: Request, env: Env, pathname: string): Promise<Response> {
	if (request.method !== 'GET' && request.method !== 'HEAD') {
		return new Response('Method not allowed', { status: 405, headers: { allow: 'GET, HEAD' } });
	}

	const key = pathname.slice(1); // "data/meta.json", "sitemap.xml"
	// onlyIf carries If-None-Match/If-Modified-Since, so an unchanged object costs
	// a 304 rather than re-sending 7 MB of index on every navigation.
	const object = await env.INDEX.get(key, {
		onlyIf: request.headers,
		range: request.headers
	});

	// Before the bucket is first populated — and for anyone deploying a bundle
	// that still carries a local web/static/data — fall back to the asset layer
	// rather than 404ing the whole directory. R2 wins whenever it has the object,
	// so this cannot pin the site to a stale bundled copy.
	if (object === null) {
		return env.ASSETS.fetch(request);
	}

	const headers = new Headers({
		'content-type': contentType(pathname),
		etag: object.httpEtag,
		// The corpus is rebuilt weekly; an hour of staleness is cheaper than
		// re-fetching a multi-megabyte index on every cold navigation.
		'cache-control': 'public, max-age=3600'
	});

	// A miss on onlyIf yields an R2Object with no body: the client is current.
	if (!('body' in object) || object.body === null) {
		return new Response(null, { status: 304, headers });
	}

	headers.set('accept-ranges', 'bytes');

	// R2 reports a `range` on every hit, covering the whole object when none was
	// asked for — so the request header, not the response, decides whether this is
	// partial content. Answering an ordinary GET with a 206 would be a protocol
	// violation, and search engines fetching /sitemap.xml would be the first to
	// find out.
	const partial = request.headers.has('range') && object.range && 'offset' in object.range;
	if (!partial) {
		headers.set('content-length', String(object.size));
		return new Response(request.method === 'HEAD' ? null : object.body, { status: 200, headers });
	}

	const { offset = 0, length = object.size - offset } = object.range as {
		offset?: number;
		length?: number;
	};
	headers.set('content-range', `bytes ${offset}-${offset + length - 1}/${object.size}`);

	return new Response(request.method === 'HEAD' ? null : object.body, { status: 206, headers });
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const url = new URL(request.url);

		if (isIndexPath(url.pathname)) {
			return serveIndex(request, env, url.pathname);
		}

		// A missing asset is a missing asset: only extensionless paths can be
		// client-side routes. Deliberately not keyed on the Accept header — plenty
		// of crawlers ask for */* and would be handed a 404 for a real page.
		const last = url.pathname.split('/').pop() ?? '';
		if (last.includes('.')) {
			return new Response('Not found', { status: 404 });
		}

		const shell = await env.ASSETS.fetch(new URL(SHELL, url.origin));
		return new Response(shell.body, {
			status: 200,
			headers: {
				'content-type': 'text/html; charset=utf-8',
				'cache-control': 'no-cache'
			}
		});
	}
};
