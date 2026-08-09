// The catalogue is a client-side faceted search over a prebuilt index, and the
// 71k detail routes cannot reasonably be prerendered — so this ships as an SPA
// with a static fallback.
export const ssr = false;
export const prerender = false;
