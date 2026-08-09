#!/usr/bin/env python3
"""Transform the crawled AMO corpus into the static index the web app consumes.

Filters to OSI/FSF-licensed extensions, extracts public repository URLs, scores
each extension on transparent trust components, and writes chunked JSON.

See docs/specs/001-trust-directory.md for the scoring rationale.
"""
import json
import math
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
DB = os.path.join(ROOT, "data", "amo.sqlite")
STATIC = os.path.join(ROOT, "web", "static")
OUT = os.path.join(STATIC, "data")

# Canonical origin, mirrored from web/src/lib/seo.ts — the sitemap needs
# absolute URLs and is written here rather than by the SvelteKit build.
SITE_URL = "https://ffext.iodev.org"

# Reference date: the corpus snapshot. Recency is measured against the newest
# last_updated in the data so the build is deterministic and not wall-clock bound.
SNAPSHOT = None

# --- licensing ---------------------------------------------------------------

OSI_LICENSES = {
    "MIT": ("MIT", "permissive"),
    "Apache-2.0": ("Apache 2.0", "permissive"),
    "BSD-2-Clause": ("BSD 2-Clause", "permissive"),
    "BSD-3-Clause": ("BSD 3-Clause", "permissive"),
    "ISC": ("ISC", "permissive"),
    "Unlicense": ("Unlicense", "public-domain"),
    "CC0-1.0": ("CC0 1.0", "public-domain"),
    "MPL-2.0": ("MPL 2.0", "weak-copyleft"),
    "MPL-1.1": ("MPL 1.1", "weak-copyleft"),
    "LGPL-2.1-only": ("LGPL 2.1", "weak-copyleft"),
    "LGPL-3.0-only": ("LGPL 3.0", "weak-copyleft"),
    "LGPL-3.0-or-later": ("LGPL 3.0+", "weak-copyleft"),
    "GPL-2.0-only": ("GPL 2.0", "copyleft"),
    "GPL-2.0-or-later": ("GPL 2.0+", "copyleft"),
    "GPL-3.0-only": ("GPL 3.0", "copyleft"),
    "GPL-3.0-or-later": ("GPL 3.0+", "copyleft"),
    "AGPL-3.0-only": ("AGPL 3.0", "strong-copyleft"),
    "AGPL-3.0-or-later": ("AGPL 3.0+", "strong-copyleft"),
    "Artistic-2.0": ("Artistic 2.0", "permissive"),
}

# MPL-2.0 is AMO's pre-selected default in the submission form, so on its own it
# carries far less signal than a deliberately chosen license.
DEFAULT_LICENSE = "MPL-2.0"

FORGE_RE = re.compile(
    r"https?://(?:www\.)?(github\.com|gitlab\.com|codeberg\.org|bitbucket\.org|"
    r"git\.sr\.ht|framagit\.org|salsa\.debian\.org|invent\.kde\.org)/"
    r"([A-Za-z0-9._~%-]+)/([A-Za-z0-9._~%-]+)",
    re.I,
)

# --- permission risk ---------------------------------------------------------

HIGH_RISK = {
    "<all_urls>", "*://*/*", "http://*/*", "https://*/*",
    "nativeMessaging", "debugger", "proxy", "webRequest", "webRequestBlocking",
    "cookies", "history", "browsingData", "clipboardRead", "management",
    "privacy", "downloads", "pkcs11", "declarativeNetRequest",
    "declarativeNetRequestWithHostAccess", "webAuthenticationProxy",
}
MEDIUM_RISK = {
    "tabs", "bookmarks", "notifications", "contextMenus", "menus", "geolocation",
    "sessions", "topSites", "downloads.open", "clipboardWrite", "search",
    "webNavigation", "identity", "scripting", "dns", "captivePortal",
}

PERMISSION_HELP = {
    "<all_urls>": "Read and change all data on every website you visit",
    "*://*/*": "Read and change all data on every website you visit",
    "webRequest": "Observe and inspect all network requests",
    "webRequestBlocking": "Block or modify network requests before they are sent",
    "cookies": "Read and write cookies, including session tokens",
    "history": "Read your complete browsing history",
    "nativeMessaging": "Exchange messages with programs outside the browser",
    "debugger": "Attach to the browser debugger — very broad access",
    "proxy": "Control how the browser connects to the network",
    "browsingData": "Clear browsing data",
    "clipboardRead": "Read the contents of your clipboard",
    "management": "Manage your other extensions",
    "privacy": "Change privacy-related browser settings",
    "downloads": "Manage and access your downloads",
    "tabs": "See the URLs and titles of your open tabs",
    "bookmarks": "Read and modify your bookmarks",
    "storage": "Store data locally in the browser",
    "activeTab": "Access the current tab only when you click the extension",
    "alarms": "Schedule background tasks",
    "notifications": "Show you desktop notifications",
    "contextMenus": "Add entries to the right-click menu",
    "unlimitedStorage": "Store unlimited amounts of local data",
    "scripting": "Inject scripts into web pages",
    "webNavigation": "Observe navigation between pages",
    "geolocation": "Access your physical location",
    "identity": "Access account identity for sign-in flows",
    "search": "Use and change search engines",
    "sessions": "Access recently closed tabs and windows",
    "topSites": "Read your most-visited sites",
}


ICON_RE = re.compile(
    r"^https://addons\.mozilla\.org/user-media/addon_icons/\d+/(\d+)-64\.png"
    r"(?:\?modified=([0-9a-f]+))?$"
)


def compact_icon(url, addon_id):
    """AMO icon URLs are derivable from the addon id; keep only the cache key.

    Reconstructed client-side as
    /user-media/addon_icons/{id//1000}/{id}-64.png?modified={hash}
    """
    if not url:
        return None
    m = ICON_RE.match(url)
    if m and int(m.group(1)) == addon_id:
        return m.group(2) or ""
    return url


def txt(v):
    """AMO localises many fields as {locale: value}; flatten to a search string."""
    if isinstance(v, dict):
        return " ".join(str(x) for x in v.values() if x)
    return str(v) if v else ""


def localized(v, default_locale="en-US"):
    if isinstance(v, dict):
        return v.get(default_locale) or next((x for x in v.values() if x), None)
    return v


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " "))
    return re.sub(r"[ \t]+", " ", s).strip()


def write_sitemap(verified, details, snapshot):
    """Emit a sitemap covering the static pages and the source-verified tier.

    Only the verified tier is listed. The declared tier is four times larger and
    is, by construction, the cohort we can say the least about — pointing
    crawlers at 52k of those pages would spend the site's crawl budget on its
    weakest content.
    """
    day = snapshot.date().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, changefreq, priority in (("/", "daily", "1.0"),
                                       ("/methodology", "monthly", "0.7")):
        lines.append(f"<url><loc>{SITE_URL}{path}</loc><lastmod>{day}</lastmod>"
                     f"<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>")
    for it in verified:
        last = (details.get(it["id"], {}).get("lastUpdated") or "")[:10] or day
        lines.append(f"<url><loc>{SITE_URL}/ext/{it['id']}</loc>"
                     f"<lastmod>{last}</lastmod><changefreq>monthly</changefreq></url>")
    lines.append("</urlset>")
    with open(os.path.join(STATIC, "sitemap.xml"), "w") as f:
        f.write("\n".join(lines))
    return len(verified) + 2


def find_repo(addon, license_url):
    """Return (repo_url, host, owner, name) from metadata, else description text."""
    candidates = []
    for key in ("homepage", "support_url"):
        block = (addon.get(key) or {}).get("url") or {}
        if isinstance(block, dict):
            candidates += [x for x in block.values() if x]
    if license_url:
        candidates.append(license_url)

    for source in (candidates, None):
        if source is None:
            blob = " ".join([
                txt(addon.get("description")), txt(addon.get("summary")),
                txt(addon.get("developer_comments")),
            ])
            m = FORGE_RE.search(blob)
            if m:
                return _repo_tuple(m)
            return None
        for url in source:
            m = FORGE_RE.search(url or "")
            if m:
                return _repo_tuple(m)
    return None


def _repo_tuple(m):
    host, owner, name = m.group(1).lower(), m.group(2), m.group(3)
    name = re.sub(r"\.git$", "", name)
    # Avoid matching non-repo paths on forges (e.g. github.com/orgs/x)
    if owner.lower() in {"orgs", "sponsors", "features", "about", "pricing", "explore"}:
        return None
    return (f"https://{host}/{owner}/{name}", host, owner, name)


def classify_permissions(file_block):
    """Merge MV2 permissions and MV3 host_permissions, then band by sensitivity."""
    perms = list(file_block.get("permissions") or [])
    hosts = list(file_block.get("host_permissions") or [])
    optional = list(file_block.get("optional_permissions") or [])

    all_required = perms + hosts
    high, medium, low = [], [], []
    for p in all_required:
        if p in HIGH_RISK:
            high.append(p)
        elif p in MEDIUM_RISK:
            medium.append(p)
        elif p.startswith(("http://", "https://", "*://", "file://", "ws://", "wss://")):
            # A specific host match is far narrower than <all_urls>
            (high if p in HIGH_RISK else medium).append(p)
        else:
            low.append(p)
    return {
        "high": sorted(set(high)),
        "medium": sorted(set(medium)),
        "low": sorted(set(low)),
        "optional": sorted(set(optional)),
        "broadHostAccess": any(
            p in {"<all_urls>", "*://*/*", "http://*/*", "https://*/*"}
            for p in all_required
        ),
    }


def data_collection(file_block):
    dc = file_block.get("data_collection_permissions") or []
    opt = file_block.get("optional_data_collection_permissions") or []
    if dc == ["none"]:
        return {"state": "none", "required": [], "optional": opt}
    if dc:
        return {"state": "declared", "required": dc, "optional": opt}
    return {"state": "undisclosed", "required": [], "optional": opt}


def days_since(iso, snapshot):
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return max(0, (snapshot - d).days)
    except Exception:
        return None


def score(addon, repo, perms, dc, age_days, license_slug):
    """Itemised 0-100 trust score. Every component is surfaced in the UI."""
    c = {}

    # Source availability (30) — the strongest signal.
    if repo:
        c["source"] = {"points": 30, "max": 30, "label": "Public source repository linked"}
    elif license_slug == DEFAULT_LICENSE:
        c["source"] = {"points": 0, "max": 30,
                       "label": "No public source; license is AMO's default (MPL-2.0)"}
    else:
        c["source"] = {"points": 6, "max": 30,
                       "label": "No public source found, but license was deliberately chosen"}

    # Permission footprint (25) — inverted risk.
    p = 25
    p -= 12 if perms["broadHostAccess"] else 0
    p -= min(9, 3 * len([x for x in perms["high"] if x not in
                         {"<all_urls>", "*://*/*", "http://*/*", "https://*/*"}]))
    p -= min(4, len(perms["medium"]))
    p = max(0, p)
    if perms["broadHostAccess"]:
        lbl = "Requests access to all websites"
    elif perms["high"]:
        lbl = f"{len(perms['high'])} sensitive permission(s)"
    elif perms["medium"]:
        lbl = "Moderate permissions only"
    else:
        lbl = "Minimal permissions"
    c["permissions"] = {"points": p, "max": 25, "label": lbl}

    # Data collection disclosure (15).
    if dc["state"] == "none":
        c["dataCollection"] = {"points": 15, "max": 15, "label": "Declares it collects no data"}
    elif dc["state"] == "declared":
        n = len(dc["required"])
        c["dataCollection"] = {"points": max(3, 11 - 2 * n), "max": 15,
                               "label": f"Discloses {n} data type(s) collected"}
    else:
        c["dataCollection"] = {"points": 5, "max": 15, "label": "No data-collection disclosure"}

    # Maintenance (15).
    if age_days is None:
        c["maintenance"] = {"points": 0, "max": 15, "label": "Unknown last update"}
    elif age_days <= 180:
        c["maintenance"] = {"points": 15, "max": 15, "label": "Updated within 6 months"}
    elif age_days <= 365:
        c["maintenance"] = {"points": 12, "max": 15, "label": "Updated within a year"}
    elif age_days <= 730:
        c["maintenance"] = {"points": 7, "max": 15, "label": "Updated within 2 years"}
    elif age_days <= 1460:
        c["maintenance"] = {"points": 3, "max": 15, "label": "Last updated 2-4 years ago"}
    else:
        c["maintenance"] = {"points": 0, "max": 15, "label": "Unmaintained for 4+ years"}

    # Adoption & reputation (15) — log-scaled so popularity cannot dominate.
    users = addon.get("average_daily_users") or 0
    ratings = addon.get("ratings") or {}
    avg, cnt = ratings.get("average") or 0, ratings.get("count") or 0
    up = min(9, round(math.log10(users + 1) * 2.0)) if users else 0
    rp = 0
    if cnt >= 5:
        rp = min(6, round((avg - 2.5) / 2.5 * 6)) if avg else 0
        rp = max(0, rp)
    c["adoption"] = {"points": up + rp, "max": 15,
                     "label": f"{users:,} daily users" + (f", {avg:.1f}★ ({cnt})" if cnt else "")}

    total = sum(v["points"] for v in c.values())
    return total, c


def main():
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT json FROM addons").fetchall()
    print(f"loaded {len(rows)} crawled extensions")

    # Determine snapshot date from the data itself for deterministic scoring.
    newest = None
    parsed = []
    for (j,) in rows:
        a = json.loads(j, strict=False)
        parsed.append(a)
        lu = a.get("last_updated")
        if lu:
            try:
                d = datetime.fromisoformat(lu.replace("Z", "+00:00"))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                newest = d if newest is None or d > newest else newest
            except Exception:
                pass
    snapshot = newest or datetime.now(timezone.utc)
    print(f"snapshot date: {snapshot.date()}")

    items, details = [], {}
    stats = Counter()

    for a in parsed:
        cv = a.get("current_version") or {}
        lic = cv.get("license") or {}
        slug = lic.get("slug")
        if slug not in OSI_LICENSES:
            stats["excluded_non_oss"] += 1
            continue
        if a.get("is_disabled"):
            stats["excluded_disabled"] += 1
            continue

        lic_name, lic_family = OSI_LICENSES[slug]
        repo = find_repo(a, lic.get("url"))
        fileb = cv.get("file") or {}
        perms = classify_permissions(fileb)
        dc = data_collection(fileb)
        age = days_since(a.get("last_updated"), snapshot)
        total, comps = score(a, repo, perms, dc, age, slug)

        promoted = sorted({p.get("category") for p in (a.get("promoted") or []) if p.get("category")})
        tier = "verified" if repo else "declared"
        stats[f"tier_{tier}"] += 1

        name = localized(a.get("name")) or a.get("slug")
        summary = strip_html(localized(a.get("summary")) or "")

        # Compact record for the client-side search index.
        items.append({
            "id": a["id"],
            "s": a.get("slug"),
            "n": name,
            "d": summary[:110],
            "ic": compact_icon((a.get("icons") or {}).get("64") or a.get("icon_url"), a["id"]),
            "l": slug,
            "lf": lic_family,
            "t": tier,
            "sc": total,
            "u": a.get("average_daily_users") or 0,
            "r": round((a.get("ratings") or {}).get("average") or 0, 2),
            "rc": (a.get("ratings") or {}).get("count") or 0,
            "c": a.get("categories") or [],
            "ag": age,
            "bh": perms["broadHostAccess"],
            "hp": len(perms["high"]),
            "dc": dc["state"],
            "pr": promoted,
            "rh": repo[1] if repo else None,
        })

        details[a["id"]] = {
            "id": a["id"],
            "slug": a.get("slug"),
            "name": name,
            "summary": summary,
            "description": strip_html(localized(a.get("description")) or ""),
            "icon": (a.get("icons") or {}).get("128") or a.get("icon_url"),
            "authors": [{"name": x.get("name"), "url": x.get("url")} for x in (a.get("authors") or [])],
            "license": {"slug": slug, "name": lic_name, "family": lic_family,
                        "url": lic.get("url"), "isAmoDefault": slug == DEFAULT_LICENSE},
            "repo": {"url": repo[0], "host": repo[1], "owner": repo[2], "name": repo[3]} if repo else None,
            "tier": tier,
            "score": total,
            "components": comps,
            "permissions": perms,
            "permissionHelp": {p: PERMISSION_HELP[p]
                               for p in perms["high"] + perms["medium"] + perms["low"]
                               if p in PERMISSION_HELP},
            "dataCollection": dc,
            "version": cv.get("version"),
            "lastUpdated": a.get("last_updated"),
            "created": a.get("created"),
            "ageDays": age,
            "users": a.get("average_daily_users") or 0,
            "ratings": a.get("ratings") or {},
            "categories": a.get("categories") or [],
            "promoted": promoted,
            "amoUrl": a.get("url"),
            "homepage": localized((a.get("homepage") or {}).get("url")),
            "supportUrl": localized((a.get("support_url") or {}).get("url")),
            "hasPrivacyPolicy": a.get("has_privacy_policy"),
            "hasEula": a.get("has_eula"),
            "isExperimental": a.get("is_experimental"),
            "requiresPayment": a.get("requires_payment"),
            "xpiSize": (fileb.get("size") or None),
        }

    items.sort(key=lambda x: (-x["sc"], -x["u"]))

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, "ext"), exist_ok=True)

    # Split by tier: the verified set is the default view and loads eagerly; the
    # much larger declared set is fetched only when the user opts into it.
    verified = [i for i in items if i["t"] == "verified"]
    declared = [i for i in items if i["t"] == "declared"]
    for fname, data in (("index-verified.json", verified), ("index-declared.json", declared)):
        with open(os.path.join(OUT, fname), "w") as f:
            json.dump(data, f, separators=(",", ":"))

    # Shard detail records so a page load fetches ~1/256th of the corpus.
    shards = {}
    for eid, rec in details.items():
        shards.setdefault(eid % 256, {})[str(eid)] = rec
    for k, v in shards.items():
        with open(os.path.join(OUT, "ext", f"{k}.json"), "w") as f:
            json.dump(v, f, separators=(",", ":"))

    cats = Counter()
    for it in items:
        for c in it["c"]:
            cats[c] += 1
    meta = {
        "generated": snapshot.isoformat(),
        "crawledTotal": len(rows),
        "listed": len(items),
        "tiers": {"verified": stats["tier_verified"], "declared": stats["tier_declared"]},
        "excludedNonOss": stats["excluded_non_oss"],
        "licenses": dict(Counter(i["l"] for i in items).most_common()),
        "categories": dict(cats.most_common()),
        "shardCount": 256,
    }
    with open(os.path.join(OUT, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    urls = write_sitemap(verified, details, snapshot)

    print(f"listed {len(items)} OSS extensions "
          f"(verified {stats['tier_verified']}, declared {stats['tier_declared']})")
    print(f"excluded {stats['excluded_non_oss']} non-OSS, {stats['excluded_disabled']} disabled")
    for fname in ("index-verified.json", "index-declared.json"):
        mb = os.path.getsize(os.path.join(OUT, fname)) / 1e6
        print(f"{fname} = {mb:.1f} MB")
    print(f"{len(shards)} detail shards")
    print(f"sitemap.xml = {urls} URLs")


if __name__ == "__main__":
    main()
