/**
 * Static-asset worker with an explicit SPA fallback.
 *
 * Cloudflare's built-in `single-page-application` not-found handling always
 * serves /index.html, but index.html here is the prerendered landing page.
 * Client-side routes (/ext/<id>) need the route-less shell instead, so asset
 * misses fall through to this worker, which serves 200.html with a 200 status —
 * a 404 would keep those pages out of the index.
 */

interface Env {
	ASSETS: Fetcher;
}

const SHELL = '/200.html';

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const url = new URL(request.url);

		// A missing asset is a missing asset: only extensionless paths can be
		// client-side routes. Deliberately not keyed on the Accept header — plenty
		// of crawlers ask for */* and would be handed a 404 for a real page.
		const last = url.pathname.split('/').pop() ?? '';
		if (last.includes('.') || url.pathname.startsWith('/data/')) {
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
