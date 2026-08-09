import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
export default {
	preprocess: vitePreprocess(),
	kit: {
		// The SPA shell is 200.html, not index.html: index.html is now the
		// prerendered landing page, and serving that as the fallback would hand
		// every /ext/<id> request the homepage's canonical URL and a hydration
		// mismatch. worker/index.ts serves 200.html for unprerendered routes.
		adapter: adapter({ fallback: '200.html' }),
		prerender: { entries: ['*'] }
	}
};
