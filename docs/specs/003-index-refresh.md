# 003 — Keeping the index fresh

Status: implemented
Date: 2026-08-25

## Intent

Republish the corpus on a schedule, and stop a code deploy and a data refresh
from being the same event.

## The problem

[002](002-deploy-and-discovery.md) put the index in the asset bundle:
`build_index.py` writes `web/static/data/*.json` and `web/static/sitemap.xml`,
`vite build` copies them into `web/build`, and `wrangler deploy` uploads the lot.
That worked while deploys were manual, from a working copy that happened to hold
a crawl.

It stops working the moment deployment is automatic on push to `master`. `data/`
and `web/static/data/` are gitignored, so a build from a clean checkout has no
corpus in it — and the build *succeeds anyway*, emitting a `web/build` with no
`data/` directory and no `sitemap.xml`. Deploying that replaces the live assets
with a bundle that has no index, and the Worker's 404-on-miss rule turns the
whole directory into an empty page. A commit touching only CSS could do it.

The underlying mistake is that the index was treated as a build artifact of the
site when it is really an input to it, on its own clock: the site changes when
someone writes code, the corpus changes when AMO does.

## Decision

Separate the two paths.

```
push to master  ->  build web/ -> wrangler deploy   (code, no index)
weekly cron     ->  crawl -> build -> verify -> R2  (index, no code)
```

`/data/*` and `/sitemap.xml` are served from an R2 bucket bound as `INDEX`,
listed in `run_worker_first` so they reach the Worker *ahead* of the asset layer.
That ordering is the point: were the asset layer to win, a deploy that happened
to carry a stale local `web/static/data` would shadow R2 and pin the site to an
index nothing updates. On an R2 miss the Worker falls back to the asset layer, so
an unpopulated bucket degrades to the old behaviour instead of 404ing.

Conditional requests are passed through to R2 (`onlyIf`, `range`), so a returning
visitor revalidates the 7 MB index with a 304 rather than downloading it again.

### Weekly, and whole

The whole corpus is re-crawled each time rather than updated incrementally. AMO
exposes no "changed since" filter, the crawl is only ~3,000 requests, and a
single consistent snapshot is what makes the maintenance-recency component
meaningful: `ageDays` is measured against the newest `last_updated` in the data,
so a corpus assembled from several dates would score against a date that never
existed.

This also rules out caching `data/amo.sqlite` between runs. The crawler's resume
state lives in the same file as the data — `done_pages` makes it skip any page it
has already fetched — so a restored database would skip the entire crawl and
republish last week's corpus as if it were new. The job crawls from empty every
time, deliberately.

### Refusing a bad build

The job is unattended and overwrites what the entire site reads, so the failure
that matters is the quiet one: an API change that empties a field the filters key
on, a crawl that stopped a third of the way through, a sharding bug that drops
detail records. Each produces a *valid* index that is merely much smaller, which
nobody notices until the directory looks thin.

`verify_index.py` therefore checks structure (every shard parses, every listed
extension has a detail record in the shard that can serve it, the sitemap exists)
and then compares the build against the currently published `meta.json`. A drop
of more than 10% in `crawledTotal` or `listed` fails the job before anything is
uploaded, on the assumption that the crawl broke rather than that AMO shrank.
`--max-drop` raises the bar for a change that is genuinely that large.

`meta.json` is uploaded last. It is the manifest every client reads first, so
until it names the new build the site keeps describing the previous one.

## Consequences

- The R2 bucket must be populated before a Worker that reads from it is
  deployed. Bootstrap order: create the bucket, run the workflow, then deploy.
- Publishing needs R2 S3-compatible credentials (`R2_ACCESS_KEY_ID`,
  `R2_SECRET_ACCESS_KEY`) rather than a Cloudflare API token, because the upload
  is an `aws s3 sync` of ~260 objects and one `wrangler r2 object put` per file
  would take longer than the crawl.
- The upload is not atomic. Two concurrent runs would interleave shards from
  different snapshots, so the workflow holds a concurrency group.
- `npm run dev` still reads `web/static/data`, so a local crawl is all that local
  development needs.

## Implementation steps

- [x] `worker/index.ts` serves `/data/*` and `/sitemap.xml` from R2, with an
      asset fallback and conditional-request pass-through
- [x] `r2_buckets` binding and `run_worker_first` in `wrangler.jsonc`
- [x] `scripts/verify_index.py`
- [x] `.github/workflows/refresh-index.yml`, weekly plus `workflow_dispatch`
- [x] Weekly cadence stated on the methodology page
- [ ] `ffext-index` bucket created in the infra repo
- [ ] `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` added as repository secrets
