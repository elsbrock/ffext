# ffext

**[ffext.iodev.org](https://ffext.iodev.org)** — an alternative directory for Firefox extensions,
focused on **trust** rather than popularity.

Only open source licensed extensions are listed, and they are ranked by what can actually be
checked: public source availability, permission footprint, data-collection disclosure and
maintenance recency.

## Why

`addons.mozilla.org` ranks by popularity and editorial promotion. Neither answers the question
that matters before you grant a program the ability to read every page you visit.

Crawling the full corpus surfaces the problem clearly:

| | |
|---|---|
| Firefox extensions crawled | 96,532 (99.9% of the catalogue) |
| OSI/FSF licensed | 71,433 |
| …that link a public repository | 18,734 |
| Excluded as closed source | 25,099 |

**36,342 declare MPL-2.0 — because it is the pre-selected default in AMO's submission form.**
A declared license is therefore a weak signal on its own: over half of "open source" extensions
on AMO have no public source anywhere. ffext lists both, in separate tiers, and never presents
them as equivalent.

## Layout

```
scripts/crawl_amo.py     AMO API  -> data/amo.sqlite         (resumable, category-sliced)
scripts/build_index.py   sqlite   -> web/static/data/*.json   (filter, score, shard)
                                  -> web/static/sitemap.xml
scripts/make_og_image.py          -> web/static/og.png        (social card)
web/                     SvelteKit 5 + Tailwind v4, adapter-static
worker/                  Cloudflare Worker: SPA fallback in front of the assets
docs/specs/              design docs — read these first
```

## Usage

```sh
python3 scripts/crawl_amo.py      # ~3,000 requests, resumable, ~10 min
python3 scripts/build_index.py    # writes the static index and the sitemap

cd web
npm install
npm run dev                       # or: npm run build && npx vite preview
```

## Deploying

```sh
npm install
npm run deploy                    # builds web/, then wrangler deploy
```

`ffext.iodev.org` is attached to the Worker declaratively, from a separate infra
repository — not by `wrangler.jsonc`.

## Sharing a view

Search text, sort, tier, categories, license families, data-collection state,
the permission and maintenance toggles and the minimum trust score all live in
the query string, so any view is a link:

```
/?q=dark&lic=permissive&nobroad=1&min=80&sort=name
```

Only non-default values are written, so the unfiltered directory stays at `/`.

## How the crawl reaches the whole corpus

The AMO search API caps any single query at 600 pages × 50 = 30,000 results, but the corpus is
~96,600. Each of the 15 extension categories is individually under that ceiling, so the crawler
slices by category and unions on addon id. `sort=created` is used because creation dates are
immutable, which keeps pagination stable mid-crawl.

## Limits

Repository links come from AMO metadata and description text; they are not fetched. "Source
available" means *a public repo is claimed and discoverable* — not that the published code
matches the shipped build. Nothing here is reproducible-build verified. See
[the methodology page](web/src/routes/methodology/+page.svelte) and
[docs/specs/001-trust-directory.md](docs/specs/001-trust-directory.md).

Data from the addons.mozilla.org public API. Not affiliated with Mozilla.

## License

[AGPL-3.0-or-later](LICENSE). Running a modified version as a network service obliges you to
offer that modified source to its users.
