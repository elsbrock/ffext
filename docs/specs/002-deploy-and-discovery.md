# 002 — Deployment, discoverability and shareable views

Status: implemented
Date: 2026-08-09

## Intent

Get ffext onto `ffext.iodev.org` as a public site, make it findable by search
engines and presentable when linked, and make any particular view of the
catalogue — a search, a set of filters, a sort — a URL someone can send to
someone else.

[001](001-trust-directory.md) deliberately chose a client-rendered SPA: 71k
extensions cannot be prerendered, and the faceted search is a client-side pass
over a prebuilt index. That decision is kept. Everything below works around it
rather than reversing it.

## Architecture

```
web/build/            adapter-static output: prerendered pages + 200.html shell
worker/index.ts       serves 200.html for client-side routes
wrangler.jsonc        Worker "ffext", static assets, deployed with `wrangler deploy`
terraform/cloudflare/ (infra repo) attaches ffext.iodev.org to the Worker
```

### Hosting: a Worker with static assets

The site is a Worker with an `assets` binding rather than a pure asset upload.
Requests hit the asset layer first; only a miss reaches the Worker.

Cloudflare's built-in `single-page-application` not-found handling always serves
`/index.html`, and that is the wrong file here: `index.html` is the *prerendered
landing page*, complete with its own `<title>`, canonical URL and JSON-LD.
Serving it for `/ext/2689239` would hand that page the homepage's canonical and
put SvelteKit into a hydration mismatch. So the adapter emits the route-less
shell as `200.html`, `not_found_handling` is `none`, and the Worker returns the
shell with a 200 status — a 404 would keep every detail page out of the index.

The Worker distinguishes a client-side route from a genuinely missing file by
whether the last path segment has an extension, not by the `Accept` header:
plenty of crawlers request `*/*`.

### SEO under a client-rendered catalogue

| Concern | Approach |
|---|---|
| Landing pages | `/` and `/methodology` opt back into `ssr` + `prerender`, so their head and prose exist without JavaScript |
| Head tags | One `Seo.svelte` owns title, description, canonical, Open Graph, Twitter and JSON-LD, so every route emits exactly one of each |
| Detail pages | Client-rendered; their head is populated once the shard loads. Rendering crawlers see it, non-rendering unfurlers do not |
| Structured data | `WebSite` + `Dataset` on `/`, `SoftwareApplication` (with `aggregateRating` where ratings exist) per extension |
| Sitemap | `build_index.py` emits `sitemap.xml` for the two static pages plus the 18,734 source-verified extensions |
| Social card | `scripts/make_og_image.py` draws a static 1200×630 PNG; scrapers do not accept SVG |

Only the verified tier is in the sitemap. The declared tier is nearly three
times larger and is by construction the cohort we can say the least about —
pointing crawlers at 52k of those pages spends crawl budget on the weakest
content in the corpus.

Detail pages having no server-rendered head is an accepted cost of the SPA
decision, not an oversight. Prerendering 18.7k pages to fix it is the available
remedy if search coverage turns out to be poor.

### Shareable views

Every filter is representable in the query string, and only non-default values
are written, so the unfiltered site stays at a bare `/`:

| Param | Meaning |
|---|---|
| `q` | search text |
| `sort` | `score` (default), `users`, `updated`, `rating`, `name` |
| `tier=all` | include the license-declared tier |
| `cat`, `lic`, `dc` | comma-separated category / license family / data-collection selections |
| `nobroad`, `norisk`, `maintained` | risk and maintenance toggles |
| `min` | minimum trust score, clamped to 0–100 on read |

State is restored in `onMount` rather than at component init, so prerendered and
hydrated markup match. The write-back is armed one tick later still: `onMount`
runs inside the hydration flush, and calling `replaceState` before the router has
finished starting throws — which aborts the remainder of the flush and leaves the
filter controls rendering defaults while the state behind them is already
restored. That failure is silent in the UI, which is what makes it worth a
comment in the source.

`replaceState`, not `pushState`: a history entry per keystroke would make the
back button useless.

The canonical URL for the landing page is always `/`, whatever the query string.
Filtered views are for sharing, not for occupying the index.

## Implementation steps

- [x] AGPL-3.0, public repository at github.com/elsbrock/ffext
- [x] `Seo.svelte`, per-route metadata, JSON-LD, `robots.txt`, generated `sitemap.xml`
- [x] Prerendered `/` and `/methodology`; `200.html` shell for client-side routes
- [x] Static Open Graph card
- [x] Filter state in the query string, with a Share button
- [x] Worker + `wrangler.jsonc`; `ffext.iodev.org` attached from the infra repo
