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
import unicodedata
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
    # Reachable only through the custom-name table below: AMO's dropdown has no
    # slug for these, so authors who use them have to type the name by hand.
    "Zlib": ("zlib", "permissive"),
    "MIT-0": ("MIT No Attribution", "permissive"),
    "WTFPL": ("WTFPL", "public-domain"),
    "OSL-3.0": ("OSL 3.0", "copyleft"),
    "EUPL-1.2": ("EUPL 1.2", "copyleft"),
}

# MPL-2.0 is AMO's pre-selected default in the submission form, so on its own it
# carries far less signal than a deliberately chosen license.
DEFAULT_LICENSE = "MPL-2.0"

# --- custom license names ----------------------------------------------------
#
# AMO lets an author bypass the license dropdown and supply a custom license,
# which arrives as `is_custom: true`, `slug: null` and a free-text name. Roughly
# one popular extension in nine takes that route, and most of them are genuinely
# proprietary ("Norton License Agreement", "Honey Terms of Use") - but a minority
# typed the name of an ordinary OSS license into the box. Tridactyl, to pick the
# case that prompted this, ships Apache-2.0 under the name "Apache v2".
#
# Those are recovered by exact match against the table below, after normalising
# case, accents and punctuation. Exact match, never substring: "ISC License +
# CC-BY" is a combination, "Custom BSD 3 License" is not the BSD 3-clause text,
# and "No License" is the opposite of "Unlicense". Anything the table does not
# name stays excluded, which is why an unresolved name is a listing decision
# deferred rather than a mistake - run scripts/report_exclusions.py to see the
# names worth adding.
#
# A version is always required where the family has incompatible versions, so
# bare "GNU Affero General Public License" does not match while
# "GNU Affero General Public License v3.0" does.

CUSTOM_LICENSE_NAMES = {
    "MIT": ["mit", "mit license", "the mit license", "mit license mit", "expat license"],
    "MIT-0": ["mit 0", "mit no attribution"],
    "Apache-2.0": [
        "apache 2.0", "apache 2", "apache v2", "apache v2.0", "apache2.0",
        "apache license 2.0", "apache license v2.0", "apache license version 2.0",
        "apache license version 2", "apache software license 2.0", "apache 2.0 license",
    ],
    "ISC": ["isc", "isc license"],
    "BSD-2-Clause": [
        "bsd 2 clause", "bsd 2 clause license", "2 clause bsd license",
        "simplified bsd license", "freebsd license",
    ],
    "BSD-3-Clause": [
        "bsd 3", "bsd 3 clause", "bsd 3 clause license", "the bsd 3 clause license",
        "3 clause bsd license", "new bsd license", "modified bsd license",
    ],
    "Unlicense": ["unlicense", "the unlicense", "unlicence", "the unlicence"],
    "CC0-1.0": [
        "cc0", "cc0 1.0", "cc0 universal", "cc0 1.0 universal", "creative commons zero",
        "cc0 1.0 universal cc0 1.0 public domain dedication",
    ],
    "MPL-1.1": [
        "mpl 1.1", "mozilla public license 1.1", "mozilla public licence 1.1",
        "mozilla public license version 1.1", "mozilla public licence version 1.1",
    ],
    "MPL-2.0": [
        "mpl 2.0", "mpl2.0", "mozilla public license 2.0", "mozilla public licence 2.0",
        "mozilla public license v2.0", "mozilla public license version 2.0",
        "mozilla public licence version 2.0",
    ],
    "LGPL-2.1-only": ["lgpl 2.1", "lgplv2.1", "gnu lesser general public license v2.1"],
    "LGPL-3.0-only": ["lgpl 3.0", "lgplv3", "gnu lesser general public license v3.0"],
    "LGPL-3.0-or-later": ["lgpl 3.0 or later", "lgplv3+"],
    "GPL-2.0-only": [
        "gpl 2.0", "gpl v2", "gplv2", "gnu gpl v2",
        "gnu general public license v2.0", "gnu general public license version 2",
    ],
    "GPL-2.0-or-later": [
        "gpl 2.0 or later", "gplv2+", "gpl v2+", "gnu general public license v2.0 or later",
    ],
    "GPL-3.0-only": [
        "gpl 3.0", "gpl v3", "gplv3", "gnu gpl v3",
        "gnu general public license v3.0", "gnu general public license version 3",
    ],
    "GPL-3.0-or-later": [
        "gpl 3.0 or later", "gplv3+", "gpl v3+",
        "gnu general public license v3.0 or later", "gnu general public license v3 or later",
    ],
    "AGPL-3.0-only": [
        "agpl 3.0", "agpl v3", "agpl v3.0", "agplv3", "gnu agpl v3", "gnu agpl v3.0",
        "affero general public license v3.0", "gnu affero general public license v3.0",
        "gnu affero general public license version 3.0",
    ],
    "AGPL-3.0-or-later": [
        "agpl 3.0 or later", "agplv3+", "gnu affero general public license v3.0 or later",
        "gnu affero general public license v3.0 or any later version",
    ],
    "Artistic-2.0": ["artistic 2.0", "artistic license 2.0"],
    "Zlib": ["zlib", "zlib license", "zlib libpng", "zlib libpng license"],
    "WTFPL": [
        "wtfpl", "wtfpl 2.0", "wtfpl version 2",
        "do what the fuck you want to public license",
    ],
    "OSL-3.0": ["osl 3.0", "open software license 3.0", "open software license osl 3.0"],
    "EUPL-1.2": [
        "eupl 1.2", "european union public license 1.2", "european union public licence 1.2",
        "european union public license v 1.2", "european union public licence v 1.2",
    ],
}


def normalize_license_name(name):
    """Fold a free-text license name to the form the alias table is keyed on."""
    s = unicodedata.normalize("NFKD", str(name or ""))
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"(?<!\d)\.(?!\d)", " ", s)  # "v. 1.2" -> "v 1.2"; "2.0" survives
    s = re.sub(r"[^a-z0-9.+]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _build_alias_table():
    table = {}
    for spdx, names in CUSTOM_LICENSE_NAMES.items():
        assert spdx in OSI_LICENSES, f"alias target not in OSI_LICENSES: {spdx}"
        for name in names:
            # Keys are written pre-normalised so the table stays greppable.
            assert normalize_license_name(name) == name, f"unnormalised alias key: {name!r}"
            assert name not in table, f"duplicate alias: {name!r} ({table.get(name)}/{spdx})"
            table[name] = spdx
    return table


CUSTOM_LICENSE_ALIASES = _build_alias_table()


def resolve_license(lic):
    """Return (spdx_slug, source) or None.

    `source` is "amo-field" when AMO's structured license field named the license
    and "custom-name" when it was recovered from free text. Both are the author's
    own claim; the second one was matched by us, and the site says so.
    """
    slug = lic.get("slug")
    if slug in OSI_LICENSES:
        return slug, "amo-field"
    if slug:
        return None  # a named non-OSS license, e.g. all-rights-reserved
    matched = CUSTOM_LICENSE_ALIASES.get(normalize_license_name(localized(lic.get("name"))))
    return (matched, "custom-name") if matched else None


# --- repositories ------------------------------------------------------------

# Public forges recognised as a source repository. Named explicitly rather than
# matched by pattern: "contains the word git" would sweep in mirrors, docs sites
# and download pages. Self-hosted Gitea/cgit instances are missed as a result,
# and that undercount is stated on the methodology page.
FORGE_HOSTS = [
    "github.com", "gitlab.com", "codeberg.org", "bitbucket.org",
    "git.sr.ht", "framagit.org", "salsa.debian.org", "invent.kde.org",
]

FORGE_RE = re.compile(
    r"https?://(?:www\.)?(" + "|".join(h.replace(".", r"\.") for h in FORGE_HOSTS) + r")/"
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


def url_slug(*candidates):
    """An ASCII slug for the decorative half of /ext/<id>-<slug>.

    AMO slugs are not URL-friendly across the whole corpus: ~2,950 of them carry
    non-ASCII characters ("4pda-инспектор", "sg-fórum-tuning"), which survive in a
    URL only as percent-encoded noise that no one can read or share. Accents are
    folded to their base letter and anything left over is dropped.

    The identity of the page lives in the numeric id, so an empty slug is a
    perfectly valid outcome — /ext/12345 still resolves.
    """
    for raw in candidates:
        if not raw:
            continue
        folded = unicodedata.normalize("NFKD", str(raw))
        ascii_only = folded.encode("ascii", "ignore").decode("ascii").lower()
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
        # Long enough to stay descriptive, short enough to survive being pasted
        # into a chat client that truncates.
        slug = slug[:60].rstrip("-")
        if slug:
            return slug
    return ""


def ext_path(item):
    """Canonical path for an extension. Mirrored in web/src/lib/utils.ts."""
    slug = item.get("s") or ""
    return f"/ext/{item['id']}-{slug}" if slug else f"/ext/{item['id']}"


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
        lines.append(f"<url><loc>{SITE_URL}{ext_path(it)}</loc>"
                     f"<lastmod>{last}</lastmod><changefreq>monthly</changefreq></url>")
    lines.append("</urlset>")
    with open(os.path.join(STATIC, "sitemap.xml"), "w") as f:
        f.write("\n".join(lines))
    return len(verified) + 2


def find_repo(addon, license_url):
    """Return (repo_url, host, owner, name, source) or None.

    `source` records which field the link came from, because the two are not
    equally trustworthy. A forge URL in AMO's own homepage/support_url field was
    put there by the author as the project's home. One scraped out of free-text
    description could be anything the author happened to mention - the library
    they used, a project they forked, someone else's issue tracker. The site
    labels the second kind rather than pretending both are the same evidence.
    """
    candidates = []
    for key in ("homepage", "support_url"):
        block = (addon.get(key) or {}).get("url") or {}
        if isinstance(block, dict):
            candidates += [x for x in block.values() if x]
    if license_url:
        candidates.append(license_url)

    for url in candidates:
        m = FORGE_RE.search(url or "")
        if m:
            found = _repo_tuple(m)
            if found:
                return (*found, "metadata")

    blob = " ".join([
        txt(addon.get("description")), txt(addon.get("summary")),
        txt(addon.get("developer_comments")),
    ])
    m = FORGE_RE.search(blob)
    if m:
        found = _repo_tuple(m)
        if found:
            return (*found, "description")
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


def score(addon, repo, perms, dc, age_days, license_slug, license_source):
    """Itemised 0-100 trust score. Every component is surfaced in the UI."""
    c = {}

    # Source availability (30) — the strongest signal.
    if repo:
        c["source"] = {"points": 30, "max": 30, "label": "Public source repository linked"}
    elif license_slug == DEFAULT_LICENSE and license_source == "amo-field":
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
        resolved = resolve_license(lic)
        if not resolved:
            stats["excluded_non_oss"] += 1
            if not lic.get("slug"):
                stats["excluded_custom_unmatched"] += 1
            continue
        slug, lic_source = resolved
        if a.get("is_disabled"):
            stats["excluded_disabled"] += 1
            continue
        stats[f"license_source_{lic_source}"] += 1

        lic_name, lic_family = OSI_LICENSES[slug]
        repo = find_repo(a, lic.get("url"))
        fileb = cv.get("file") or {}
        perms = classify_permissions(fileb)
        dc = data_collection(fileb)
        age = days_since(a.get("last_updated"), snapshot)
        total, comps = score(a, repo, perms, dc, age, slug, lic_source)

        promoted = sorted({p.get("category") for p in (a.get("promoted") or []) if p.get("category")})
        tier = "verified" if repo else "declared"
        stats[f"tier_{tier}"] += 1
        if repo:
            stats[f"repo_{repo[4]}"] += 1

        name = localized(a.get("name")) or a.get("slug")
        summary = strip_html(localized(a.get("summary")) or "")

        # Compact record for the client-side search index.
        items.append({
            "id": a["id"],
            # The AMO slug where it survives ASCII folding, the name otherwise.
            "s": url_slug(a.get("slug"), name),
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
            "rs": repo[4] if repo else None,
        })

        details[a["id"]] = {
            "id": a["id"],
            "slug": url_slug(a.get("slug"), name),
            "name": name,
            "summary": summary,
            "description": strip_html(localized(a.get("description")) or ""),
            "icon": (a.get("icons") or {}).get("128") or a.get("icon_url"),
            "authors": [{"name": x.get("name"), "url": x.get("url")} for x in (a.get("authors") or [])],
            "license": {"slug": slug, "name": lic_name, "family": lic_family,
                        "url": lic.get("url"), "source": lic_source,
                        "declaredAs": localized(lic.get("name")) if lic_source == "custom-name" else None,
                        # Only the dropdown value can be the form's pre-selection;
                        # an author who typed "MPL 2.0" by hand chose it.
                        "isAmoDefault": slug == DEFAULT_LICENSE and lic_source == "amo-field"},
            "repo": {"url": repo[0], "host": repo[1], "owner": repo[2], "name": repo[3],
                     "source": repo[4]} if repo else None,
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
        "excludedCustomUnmatched": stats["excluded_custom_unmatched"],
        "licenseSources": {"amoField": stats["license_source_amo-field"],
                           "customName": stats["license_source_custom-name"]},
        "repoSources": {"metadata": stats["repo_metadata"],
                        "description": stats["repo_description"]},
        "forgeHosts": FORGE_HOSTS,
        "licenses": dict(Counter(i["l"] for i in items).most_common()),
        "categories": dict(cats.most_common()),
        "shardCount": 256,
    }
    with open(os.path.join(OUT, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    urls = write_sitemap(verified, details, snapshot)

    print(f"listed {len(items)} OSS extensions "
          f"(verified {stats['tier_verified']}, declared {stats['tier_declared']})")
    print(f"license from AMO field {stats['license_source_amo-field']}, "
          f"recovered from custom name {stats['license_source_custom-name']}")
    print(f"excluded {stats['excluded_non_oss']} non-OSS "
          f"({stats['excluded_custom_unmatched']} unmatched custom names), "
          f"{stats['excluded_disabled']} disabled")
    for fname in ("index-verified.json", "index-declared.json"):
        mb = os.path.getsize(os.path.join(OUT, fname)) / 1e6
        print(f"{fname} = {mb:.1f} MB")
    print(f"{len(shards)} detail shards")
    print(f"sitemap.xml = {urls} URLs")


if __name__ == "__main__":
    main()
