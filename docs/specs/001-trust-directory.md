# ffext — a trust-focused directory of open source Firefox extensions

Status: in progress
Date: 2026-08-09

## Intent

addons.mozilla.org (AMO) ranks extensions by popularity and editorial promotion. It
does not help you answer the question that actually matters before you grant a
program the ability to read every page you visit: **can I verify what this thing
does, and how much am I handing over?**

ffext is an alternative directory over the same corpus, built around two rules:

1. **Open source only.** Extensions whose declared license is not OSI/FSF-approved
   are excluded outright.
2. **Trust signals are first-class.** Licence, source availability, permission
   footprint, data-collection disclosure and maintenance recency are the primary
   axes — not download counts.

## Key finding that shapes the design

Crawling the full corpus (96,532 of 96,606 extensions, 99.9%) shows:

| Cohort | Count |
|---|---|
| Total Firefox extensions | 96,532 |
| OSI/FSF-licensed | 71,433 |
| …of which link a public repo | 18,742 |
| `all-rights-reserved` | 22,759 |

**36,342 extensions declare MPL-2.0 — because MPL-2.0 is the pre-selected default
in AMO's submission form.** A declared license is therefore a *weak* signal on its
own: over half of "open source" extensions on AMO have no public source anywhere.

This gap is the product. We do not collapse it — we surface it.

## Decisions & trade-offs

### Open source bar: tiered, not strict

- **Tier A — Source verified**: OSI license *and* a public repo URL (18,742).
- **Tier B — License declared**: OSI license, no discoverable source (52,691).

Alternatives considered:
- *Strict (Tier A only)* — highest confidence, but discards ~73% of the OSS pool
  including extensions whose source exists but isn't linked in AMO metadata.
- *Permissive (license field only)* — treats a form default as evidence, which
  undermines the entire premise.

Tiering keeps coverage broad while making "someone can actually audit this"
a visible, sortable, filterable property. Tier A is the default view.

### Trust score: computed, but fully itemised

A 0–100 score with every component exposed. Users can see exactly which points
were awarded and why, and can sort by any single signal instead of the aggregate.
An opaque number would be unaccountable; no number at all would make 71k
extensions impossible to rank.

| Component | Max | Rationale |
|---|---|---|
| Source availability | 30 | Auditability is the strongest signal |
| Permission footprint | 25 | Inverted risk: fewer/less-sensitive permissions score higher |
| Data collection | 15 | Explicit `none` disclosure > undisclosed |
| Maintenance | 15 | Recency of last update |
| Adoption & reputation | 15 | log-scaled users + rating, capped so popularity can't dominate |

Mozilla's `promoted` status (Recommended / Line / Spotlight) is shown as a badge,
deliberately *not* folded into the score — it is Mozilla's editorial judgment, and
this directory exists to offer an independent one.

### Permission risk model

Permissions are classified into sensitivity bands rather than merely counted. A
single `<all_urls>` host permission is a bigger deal than five benign ones.

- **High**: `<all_urls>`, `*://*/*`, `nativeMessaging`, `debugger`, `proxy`,
  `webRequest`/`webRequestBlocking`, `cookies`, `history`, `browsingData`,
  `clipboardRead`, `management`, `privacy`, `downloads`
- **Medium**: `tabs`, `bookmarks`, `notifications`, `downloads.open`,
  `contextMenus`, `geolocation`, `sessions`, `topSites`
- **Low**: `storage`, `alarms`, `activeTab`, `menus`, `theme`, `unlimitedStorage`

MV2 lists host matches under `permissions`; MV3 splits them into
`host_permissions`. Both are merged before classification.

### Data architecture: static, prebuilt

Crawl → transform → ship a compact prebuilt index; all faceted search runs
client-side. No runtime cost, deploys to any static host, instant filtering.
Refresh is a scheduled rebuild.

The full 71k OSS set is too large for a single eagerly-loaded payload, so the
index is split: a lightweight search index (fields needed for filter/sort only)
plus per-extension detail chunks fetched on demand.

## Architecture

```
scripts/crawl_amo.py     AMO API -> data/amo.sqlite      (resumable, category-sliced)
scripts/build_index.py   sqlite  -> web/static/data/*.json (filter, score, chunk)
web/                     SvelteKit 5 + Tailwind v4 + shadcn-svelte, adapter-static
```

### Crawl strategy

The AMO search API caps any single query at 600 pages × 50 = 30,000 results, but
the corpus is ~96,600. Every one of the 15 extension categories is individually
under that ceiling, so the crawler slices by category and unions on addon id.
`sort=created` is used because creation dates are immutable, keeping pagination
stable mid-crawl. Progress is stored in SQLite so the crawl is resumable.

## Implementation steps

- [x] Full-corpus crawler with category slicing and resumability
- [x] Build pipeline: OSS filter, repo extraction, trust scoring, chunked output
- [x] SvelteKit + Tailwind v4 scaffold
- [x] Browse UI: faceted filters, sorting, search
- [x] Detail pages with itemised score breakdown and permission explanations
- [x] Build verification (typecheck clean, headless render of browse + detail,
      filter counts cross-checked against the raw index)

## Payload sizes

Splitting the index by tier keeps the default view affordable; the much larger
declared-tier index is fetched only when the user opts into it.

| Artifact | Raw | gzip |
|---|---|---|
| `index-verified.json` (18,734) | 6.8 MB | 1.6 MB |
| `index-declared.json` (52,699) | 19.7 MB | 4.2 MB |
| 256 detail shards | 66 MB total | ~700 kB each |

Icon URLs are stored as just their cache key and reconstructed client-side from
the addon id, which removed ~1.7 MB from the index alone.

## Implementation notes

- The index arrays are `$state.raw`, not `$state`. Svelte 5 deep-proxies `$state`,
  which both costs a great deal over 71k records and breaks identity-keyed
  caches — an early `WeakMap` search cache silently matched nothing because the
  UI iterated proxies while the cache was keyed on the raw objects. The search
  cache is now keyed by addon id for the same reason.

## Known limitations

- Repo URLs are extracted from AMO metadata and description text; they are not
  fetched to confirm the repo exists or that it corresponds to the shipped build.
  "Source verified" means *a public repo is claimed and discoverable*, not
  reproducible-build verified. This is stated in the UI.
- 74 extensions (0.08%) were not captured, most likely uncategorised or churn
  during the crawl window.
- Custom-licensed extensions are listed only when the free-text license *name*
  matches, exactly, one entry in `CUSTOM_LICENSE_NAMES` (scripts/build_index.py).
  That recovers cases like Tridactyl, which ships Apache-2.0 under the name
  "Apache v2", without guessing at names that identify nothing — an extension
  whose license is named "Custom License" stays out even when its code is public.
  The residue is ranked by daily users by `scripts/report_exclusions.py`, which is
  the intended way to find the next alias worth adding.
- A matched name is recorded as `license.source = "custom-name"` and surfaced in
  the UI. It is not scored down: both routes are the author's own unverified
  claim, and we match only names that admit one reading.
- Neither route verifies the license *text*, which AMO stores as free-form HTML
  and we never fetch.
