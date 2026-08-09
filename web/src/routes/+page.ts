// The landing page is the one route crawlers and social unfurlers hit first, so
// it is rendered to real HTML at build time. The catalogue itself still loads
// client-side — SSR here exists to emit the document head, not the 71k rows.
export const ssr = true;
export const prerender = true;
