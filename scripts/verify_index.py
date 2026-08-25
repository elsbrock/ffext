#!/usr/bin/env python3
"""Check a freshly built index before it is published.

The refresh job is unattended and overwrites what the whole site reads, so the
failure it has to catch is the quiet one: an AMO API change that empties a field
the filters key on, a crawl that stopped a third of the way through, a sharding
bug that drops detail records. All of those produce a *valid* index that is
simply much smaller — which is invisible until someone notices the directory
looks thin.

So this compares the build against what is already live and refuses a large
unexplained shrink, on top of the structural checks.

    ./scripts/verify_index.py                 # verify, comparing against the live site
    ./scripts/verify_index.py --skip-live     # first publish, nothing to compare against
    ./scripts/verify_index.py --max-drop 25   # a deliberate, larger change

Exits non-zero on failure, so the workflow stops before uploading.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_index import SITE_URL, STATIC, OUT  # noqa: E402

SHARDS = 256
UA = "ffext-directory/0.1 (open-source extension directory; +https://github.com/elsbrock/ffext)"

# Compared against the live index. A refresh that loses more than this share of
# any of them is treated as a broken build rather than a real change in AMO.
GUARDED = ("crawledTotal", "listed")


class Failed(Exception):
    pass


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        raise Failed(f"missing: {os.path.relpath(path)}")
    except json.JSONDecodeError as e:
        raise Failed(f"invalid JSON in {os.path.relpath(path)}: {e}")


def check_structure():
    """The index is internally consistent and complete."""
    meta = load(os.path.join(OUT, "meta.json"))
    verified = load(os.path.join(OUT, "index-verified.json"))
    declared = load(os.path.join(OUT, "index-declared.json"))

    if not verified:
        raise Failed("index-verified.json is empty")
    if meta.get("shardCount") != SHARDS:
        raise Failed(f"meta.shardCount is {meta.get('shardCount')}, expected {SHARDS}")

    listed = len(verified) + len(declared)
    if listed != meta.get("listed"):
        raise Failed(f"meta.listed is {meta.get('listed')} but the indexes hold {listed}")

    details = {}
    for k in range(SHARDS):
        shard = load(os.path.join(OUT, "ext", f"{k}.json"))
        for eid in shard:
            if int(eid) % SHARDS != k:
                raise Failed(f"extension {eid} is in shard {k}, which cannot serve it")
        details.update(shard)

    if len(details) != listed:
        raise Failed(f"{listed} extensions listed but {len(details)} detail records")

    orphans = [i["id"] for i in verified + declared if str(i["id"]) not in details]
    if orphans:
        raise Failed(f"{len(orphans)} listed extensions have no detail record, "
                     f"e.g. {orphans[:5]}")

    sitemap = os.path.join(STATIC, "sitemap.xml")
    if not os.path.exists(sitemap):
        raise Failed("missing: web/static/sitemap.xml")
    with open(sitemap) as f:
        head = f.read(64)
    if not head.startswith("<?xml"):
        raise Failed("sitemap.xml does not start with an XML declaration")

    print(f"structure ok — {listed:,} listed, {len(details):,} detail records, "
          f"{SHARDS} shards, sitemap present")
    return meta


def check_against_live(meta, max_drop):
    """Refuse a large unexplained shrink against the currently published index."""
    url = f"{SITE_URL}/data/meta.json"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            live = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"nothing published at {url} yet — skipping the comparison")
            return
        raise Failed(f"could not read {url}: HTTP {e.code}")
    except Exception as e:
        raise Failed(f"could not read {url}: {e}")

    print(f"live index generated {live.get('generated', '?')[:10]}, "
          f"this build {meta.get('generated', '?')[:10]}")

    problems = []
    for key in GUARDED:
        was, now = live.get(key), meta.get(key)
        if not isinstance(was, int) or not was:
            continue
        drop = (was - now) / was * 100
        arrow = "+" if now >= was else ""
        print(f"  {key:<14} {was:>8,} -> {now:>8,}  ({arrow}{now - was:,})")
        if drop > max_drop:
            problems.append(f"{key} fell {drop:.1f}% ({was:,} -> {now:,})")

    if problems:
        raise Failed("index shrank more than --max-drop "
                     f"{max_drop}%: " + "; ".join(problems))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-live", action="store_true",
                    help="do not compare against the published index")
    ap.add_argument("--max-drop", type=float, default=10.0,
                    help="tolerated shrink vs. the live index, in percent (default 10)")
    args = ap.parse_args()

    try:
        meta = check_structure()
        if not args.skip_live:
            check_against_live(meta, args.max_drop)
    except Failed as e:
        print(f"\nVERIFY FAILED: {e}", file=sys.stderr)
        return 1
    print("\nindex verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
