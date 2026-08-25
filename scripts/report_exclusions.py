#!/usr/bin/env python3
"""Report what the corpus is missing, and why.

Two modes, both aimed at the same recurring question - "extension X is open
source, why isn't it on ffext?"

    ./scripts/report_exclusions.py                 corpus report (needs a crawl)
    ./scripts/report_exclusions.py tridactyl-vim   one extension, live from AMO

The corpus report ranks the extensions excluded by the license filter by daily
users, and groups the unresolved custom license names so the one alias worth
adding to CUSTOM_LICENSE_NAMES is at the top of the list. Most of the residue is
genuinely proprietary and belongs there; the report exists so that the handful
that are not stop depending on somebody noticing by accident.

Run it after every crawl, before build_index.py.
"""
import argparse
import json
import os
import signal
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_index import (  # noqa: E402
    CUSTOM_LICENSE_ALIASES,
    OSI_LICENSES,
    classify_permissions,
    data_collection,
    find_repo,
    localized,
    normalize_license_name,
    resolve_license,
)

DB = os.path.join(os.path.dirname(__file__), "..", "data", "amo.sqlite")
API = "https://addons.mozilla.org/api/v5/addons/addon/"
UA = "ffext-directory/0.1 (open-source extension directory; +https://github.com/elsbrock/ffext)"


def verdict(addon):
    """Why one addon is or is not listed. Mirrors the filter in build_index."""
    lic = (addon.get("current_version") or {}).get("license") or {}
    name = localized(lic.get("name"))
    resolved = resolve_license(lic)

    if addon.get("is_disabled"):
        return False, "disabled on AMO", name
    if resolved:
        slug, source = resolved
        if source == "custom-name":
            return True, f"listed as {slug} (recovered from custom name {name!r})", name
        return True, f"listed as {slug} (AMO license field)", name
    if lic.get("slug"):
        return False, f"license {lic['slug']} is not OSI/FSF-approved", name
    if not lic:
        return False, "no license declared", None
    return False, f"custom license {name!r} matches no known OSS license name", name


def report_one(slug_or_id):
    url = API + urllib.parse.quote(str(slug_or_id)) + "/?lang=en-US"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            addon = json.loads(r.read().decode("utf-8"), strict=False)
    except urllib.error.HTTPError as e:
        print(f"AMO returned {e.code} for {slug_or_id!r}", file=sys.stderr)
        return 1

    listed, why, name = verdict(addon)
    lic = (addon.get("current_version") or {}).get("license") or {}
    repo = find_repo(addon, lic.get("url"))
    perms = classify_permissions((addon.get("current_version") or {}).get("file") or {})

    print(f"{localized(addon.get('name'))}  (id {addon['id']}, slug {addon.get('slug')})")
    print(f"  users        {addon.get('average_daily_users') or 0:,}")
    kind = "custom" if lic.get("is_custom") else (lic.get("slug") or "none")
    print(f"  license      {name!r} [{kind}]")
    print(f"  repository   {repo[0] + ' (from ' + repo[4] + ')' if repo else 'none found'}")
    print(f"  tier         {'verified' if repo else 'declared'}")
    print(f"  broad hosts  {perms['broadHostAccess']}")
    print(f"  {'LISTED' if listed else 'NOT LISTED'}: {why}")
    if not listed and lic.get("is_custom") and name:
        print(f"\n  To list it, the normalised name to add to CUSTOM_LICENSE_NAMES is:")
        print(f"      {normalize_license_name(name)!r}")
        print(f"  Only add it if that name unambiguously identifies one OSI/FSF license.")
    return 0


def report_corpus(limit):
    if not os.path.exists(DB):
        print(f"no corpus at {DB} — run scripts/crawl_amo.py first", file=sys.stderr)
        return 1
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT json FROM addons").fetchall()

    listed = disabled = 0
    named_non_oss = defaultdict(int)
    unmatched = defaultdict(list)
    recovered = defaultdict(int)

    for (j,) in rows:
        a = json.loads(j, strict=False)
        lic = (a.get("current_version") or {}).get("license") or {}
        resolved = resolve_license(lic)
        if resolved and a.get("is_disabled"):
            disabled += 1
            continue
        if resolved:
            listed += 1
            if resolved[1] == "custom-name":
                recovered[resolved[0]] += 1
            continue
        if lic.get("slug"):
            named_non_oss[lic["slug"]] += 1
            continue
        name = localized(lic.get("name")) or ""
        unmatched[normalize_license_name(name)].append(
            (a.get("average_daily_users") or 0, name, a.get("slug"))
        )

    print(f"crawled {len(rows)}   listed {listed}   "
          f"excluded {len(rows) - listed} ({disabled} of them disabled on AMO)\n")

    print(f"recovered from custom license names: {sum(recovered.values())}")
    for slug, n in sorted(recovered.items(), key=lambda x: -x[1]):
        print(f"  {n:6d}  {slug}")

    print(f"\nexcluded by a named non-OSS license:")
    for slug, n in sorted(named_non_oss.items(), key=lambda x: -x[1]):
        print(f"  {n:6d}  {slug}")

    total_unmatched = sum(len(v) for v in unmatched.values())
    print(f"\nunresolved custom license names: {total_unmatched} extensions, "
          f"{len(unmatched)} distinct names")
    print(f"top {limit} by the daily users behind each name — an OSS license name "
          f"here is an alias worth adding:\n")
    ranked = sorted(unmatched.items(), key=lambda kv: -sum(u for u, _, _ in kv[1]))
    print(f"  {'users':>12}  {'n':>4}  name")
    for key, entries in ranked[:limit]:
        users = sum(u for u, _, _ in entries)
        top = max(entries, key=lambda e: e[0])
        example, top_slug = top[1] or "(blank)", top[2]
        print(f"  {users:>12,}  {len(entries):>4}  {example!r}  e.g. {top_slug}")

    print(f"\n{len(OSI_LICENSES)} licenses accepted, "
          f"{len(CUSTOM_LICENSE_ALIASES)} custom-name aliases known")
    return 0


def main():
    # The report is long and meant to be piped into head/grep.
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("addon", nargs="?", help="AMO slug or id to check live against the API")
    ap.add_argument("--limit", type=int, default=40, help="rows in the corpus report")
    args = ap.parse_args()
    sys.exit(report_one(args.addon) if args.addon else report_corpus(args.limit))


if __name__ == "__main__":
    main()
