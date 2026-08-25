# ffext

**[ffext.iodev.org](https://ffext.iodev.org)** — an alternative directory for Firefox extensions,
focused on **trust** rather than popularity.

Only open source licensed extensions are listed, and they are ranked by what can actually be
checked: public source availability, permission footprint, data-collection disclosure and
maintenance recency.

## Why

`addons.mozilla.org` ranks by popularity and editorial promotion. Neither answers the question
that matters before you grant a program the ability to read every page you visit.

Crawling the full corpus surfaces the problem clearly (figures from the 2026-08-09 crawl;
the site always shows the current ones):

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
scripts/report_exclusions.py      -> what was left out, and why
scripts/verify_index.py           -> refuses to publish a broken or shrunken index
scripts/make_og_image.py          -> web/static/og.png        (social card)
web/                     SvelteKit 5 + Tailwind v4, adapter-static
worker/                  Cloudflare Worker: SPA fallback in front of the assets
docs/specs/              design docs — read these first
```

## Usage

```sh
python3 scripts/crawl_amo.py         # ~3,000 requests, resumable, ~10 min
python3 scripts/report_exclusions.py # review what the filters dropped
python3 scripts/build_index.py       # writes the static index and the sitemap

cd web
npm install
npm run dev                          # or: npm run build && npx vite preview
```

`report_exclusions.py` also answers the most common question about a missing
extension, live and without a crawl:

```sh
python3 scripts/report_exclusions.py tridactyl-vim
```

## Deploying

Code and data are deployed by two separate paths, on purpose.

**Code** ships on push to `master`, which builds `web/` and deploys the Worker.
It carries no index: `data/` and `web/static/data/` are gitignored, so a build
from a clean checkout has no corpus in it, and a push must not be able to
publish an empty directory.

**Data** is published by `.github/workflows/refresh-index.yml`, weekly and on
demand. It crawls, builds, verifies, and writes the JSON shards and the sitemap
to the R2 bucket bound as `INDEX`. `run_worker_first` in `wrangler.jsonc` routes
`/data/*` and `/sitemap.xml` to the Worker ahead of the asset layer, so R2 is
always what the site reads.

```sh
npm install
npm run deploy                    # builds web/, then wrangler deploy
```

`ffext.iodev.org` and the `ffext-index` bucket are attached declaratively from a
separate infra repository — not by `wrangler.jsonc`.

The refresh job needs `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` as repository
secrets: an R2 API token with Object Read & Write on that bucket. Populate the
bucket before deploying a Worker that reads from it — an empty bucket falls back
to the asset layer, which in a CI build holds no index at all.

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
matches the shipped build. Nothing here is reproducible-build verified.

Authors may also bypass AMO's license dropdown and type a license name themselves. Those are
matched against a fixed list of OSS license names, exactly and in full, so an extension whose
license is named only "Custom License" is absent even when its code is public — and the license
*text* is never parsed. `scripts/report_exclusions.py` ranks what that leaves out, by users. See
[the methodology page](web/src/routes/methodology/+page.svelte) and
[docs/specs/001-trust-directory.md](docs/specs/001-trust-directory.md).

Data from the addons.mozilla.org public API. Not affiliated with Mozilla.

## License

[AGPL-3.0-or-later](LICENSE). Running a modified version as a network service obliges you to
offer that modified source to its users.
