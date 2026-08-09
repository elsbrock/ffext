#!/usr/bin/env python3
"""Crawl the full AMO Firefox extension corpus.

The AMO search API caps any single query at 600 pages x 50 = 30,000 results,
but the corpus is ~96,600. Every category is individually under that ceiling,
so we slice by category and union on addon id.

Resumable: progress is stored in SQLite, already-fetched pages are skipped.
"""
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://addons.mozilla.org/api/v5/addons/search/"
PAGE_SIZE = 50
MAX_PAGE = 600  # API hard ceiling
UA = "ffext-directory/0.1 (open-source extension directory; +https://github.com/elsbrock/ffext)"

CATEGORIES = [
    "appearance", "privacy-security", "photos-music-videos", "tabs",
    "feeds-news-blogging", "search-tools", "other", "web-development",
    "social-communication", "games-entertainment", "language-support",
    "download-management", "alerts-updates", "bookmarks", "shopping",
]

DB = os.path.join(os.path.dirname(__file__), "..", "data", "amo.sqlite")


def db_connect():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    # writes from worker threads are serialised by an explicit lock in main()
    con = sqlite3.connect(DB, timeout=60, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS addons (id INTEGER PRIMARY KEY, slug TEXT, json TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS done_pages (category TEXT, page INTEGER, n INTEGER, PRIMARY KEY (category, page))")
    con.commit()
    return con


def fetch(url, tries=5):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                # AMO payloads contain raw control characters in some descriptions
                return json.loads(r.read().decode("utf-8"), strict=False)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 30))
                continue
            raise
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"failed: {url}")


def page_url(category, page):
    q = {
        "app": "firefox", "type": "extension", "lang": "en-US",
        "page_size": PAGE_SIZE, "page": page, "category": category,
        "sort": "created",  # immutable field -> stable pagination across the crawl
    }
    return BASE + "?" + urllib.parse.urlencode(q)


def count_for(category):
    d = fetch(page_url(category, 1))
    return d["count"], d


def main():
    con = db_connect()
    done = {(c, p) for c, p in con.execute("SELECT category, page FROM done_pages")}
    lock = __import__("threading").Lock()

    def store(category, page, results):
        with lock:
            con.executemany(
                "INSERT OR REPLACE INTO addons (id, slug, json) VALUES (?,?,?)",
                [(a["id"], a.get("slug"), json.dumps(a, separators=(",", ":"))) for a in results],
            )
            con.execute("INSERT OR REPLACE INTO done_pages (category,page,n) VALUES (?,?,?)",
                        (category, page, len(results)))
            con.commit()

    for cat in CATEGORIES:
        total, first = count_for(cat)
        pages = min(-(-total // PAGE_SIZE), MAX_PAGE)
        if (cat, 1) not in done:
            store(cat, 1, first["results"])
        todo = [p for p in range(2, pages + 1) if (cat, p) not in done]
        print(f"[{cat}] count={total} pages={pages} todo={len(todo)}", flush=True)

        def work(p, cat=cat):
            try:
                d = fetch(page_url(cat, p))
                store(cat, p, d.get("results", []))
            except Exception as e:
                print(f"  !! {cat} p{p}: {e}", file=sys.stderr, flush=True)

        with ThreadPoolExecutor(max_workers=5) as ex:
            for i, _ in enumerate(ex.map(work, todo), 1):
                if i % 50 == 0:
                    n = con.execute("SELECT COUNT(*) FROM addons").fetchone()[0]
                    print(f"  [{cat}] {i}/{len(todo)} pages | unique addons={n}", flush=True)

        n = con.execute("SELECT COUNT(*) FROM addons").fetchone()[0]
        print(f"[{cat}] done | unique addons so far = {n}", flush=True)

    n = con.execute("SELECT COUNT(*) FROM addons").fetchone()[0]
    print(f"CRAWL COMPLETE: {n} unique extensions", flush=True)


if __name__ == "__main__":
    main()
