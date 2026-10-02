#!/usr/bin/env python3
"""Check the built site against the content and indexation rules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SITES = ROOT / "data" / "sites.json"

BANNED = [
    "located on Aconbury HIll",
    "Kenyon suggested that occupation",
    "Main ditch gone on N and W sides",
    "Visitor erosion of paths",
    "following the natural contours and which also appears",
    "Little information about interior was gleaned",
    "Two original and four modern gaps",
    "Univallate hillfort with complete circuit, but the ditch is only visible",
    "Summary Description",
    "Monument Condition: Comments",
    "Enclosing Works Summary",
]

ATTRIBUTION = [
    "Lock &amp; Ralston",
    "https://doi.org/10.5284/1118744",
    "hillforts.arch.ox.ac.uk",
    "CC BY-SA 4.0",
]


def fail(message):
    print("FAIL", message)
    return 1


def main():
    errors = 0
    sites = json.loads(SITES.read_text(encoding="utf-8"))
    raw = SITES.read_text(encoding="utf-8")
    for snippet in BANNED:
        if snippet in raw:
            errors += fail(f"sites.json contains banned text: {snippet}")

    if len(sites) != 4147:
        errors += fail(f"expected 4147 sites, found {len(sites)}")

    indexed = [site for site in sites if site.get("index")]
    if len(indexed) != 300:
        errors += fail(f"expected 300 indexed sites, found {len(indexed)}")

    slugs = [site["slug"] for site in sites]
    if len(slugs) != len(set(slugs)):
        errors += fail("duplicate site slugs")

    pages = list((DIST / "sites").glob("*/index.html"))
    if len(pages) != len(sites):
        errors += fail(f"expected {len(sites)} site pages, found {len(pages)}")

    nations = list((DIST / "nations").glob("*/index.html"))
    counties = list((DIST / "counties").glob("*/index.html"))
    if len(nations) != 6:
        errors += fail(f"expected 6 nation pages, found {len(nations)}")
    county_slugs = {site["countySlug"] for site in sites}
    if len(counties) != len(county_slugs):
        errors += fail(f"expected {len(county_slugs)} county pages, found {len(counties)}")

    for name in ("index.html", "404.html", "robots.txt", "sitemap.xml", "CNAME", ".nojekyll"):
        if not (DIST / name).exists():
            errors += fail(f"missing {name}")

    cname = (DIST / "CNAME").read_text(encoding="utf-8").strip()
    if cname != "hillfortsmap.co.uk":
        errors += fail(f"unexpected CNAME: {cname}")

    robots = (DIST / "robots.txt").read_text(encoding="utf-8")
    if "Sitemap: https://hillfortsmap.co.uk/sitemap.xml" not in robots:
        errors += fail("robots.txt missing sitemap")

    sitemap = (DIST / "sitemap.xml").read_text(encoding="utf-8")
    expected_urls = 1 + 6 + len(county_slugs) + len(indexed)
    if sitemap.count("<loc>") != expected_urls:
        errors += fail(f"sitemap locs {sitemap.count('<loc>')} != {expected_urls}")

    map_data = json.loads((DIST / "data" / "map.json").read_text(encoding="utf-8"))
    if len(map_data["sites"]) != len(sites):
        errors += fail("map.json count mismatch")

    sample_indexed = next(site for site in indexed if site["code"] == "EN0001") if any(
        site["code"] == "EN0001" and site.get("index") for site in sites
    ) else indexed[0]
    tail = next(site for site in sites if not site.get("index"))

    indexed_html = (DIST / "sites" / sample_indexed["slug"] / "index.html").read_text(encoding="utf-8")
    tail_html = (DIST / "sites" / tail["slug"] / "index.html").read_text(encoding="utf-8")
    home = (DIST / "index.html").read_text(encoding="utf-8")
    nation = (DIST / "nations" / "scotland" / "index.html").read_text(encoding="utf-8")
    county_slug = next(site["countySlug"] for site in sites if site["nation"] == "england" and site["county"] == "Cornwall")
    county = (DIST / "counties" / county_slug / "index.html").read_text(encoding="utf-8")

    if 'class="lede"' not in indexed_html:
        errors += fail("indexed page missing visitor copy")
    if 'content="index,follow"' not in indexed_html:
        errors += fail("indexed page robots tag")
    if 'class="lede"' in tail_html:
        errors += fail("tail page has visitor copy")
    if 'content="noindex,follow"' not in tail_html:
        errors += fail("tail page missing noindex")
    if f"/sites/{tail['slug']}/" in sitemap:
        errors += fail("tail page listed in sitemap")
    if f"/sites/{sample_indexed['slug']}/" not in sitemap:
        errors += fail("indexed page missing from sitemap")

    for page_name, text in (("home", home), ("nation", nation), ("county", county), ("site", indexed_html), ("tail", tail_html)):
        for needle in ATTRIBUTION:
            if needle not in text:
                errors += fail(f"{page_name} missing attribution {needle}")
        for snippet in BANNED:
            if snippet in text:
                errors += fail(f"{page_name} contains banned text: {snippet}")

    if "data-mode=\"hub\"" not in home or "markercluster" not in home.lower() and "leaflet.markercluster.js" not in home:
        errors += fail("home map assets missing")
    if "data-mode=\"site\"" not in indexed_html:
        errors += fail("site map missing")
    if "Cornwall" not in county:
        errors += fail("county page content")
    if "Scotland" not in nation:
        errors += fail("nation page content")

    # Spot-check a few more pages for banned narrative, not only the samples.
    checked = 0
    for site in sites[::200]:
        text = (DIST / "sites" / site["slug"] / "index.html").read_text(encoding="utf-8")
        checked += 1
        for snippet in BANNED:
            if snippet in text:
                errors += fail(f"{site['code']} contains banned text")
    print(f"Spot-checked {checked} site pages")

    if errors:
        print(f"{errors} checks failed")
        return 1
    print("All checks passed")
    print(f"Sample indexed: {sample_indexed['code']} {sample_indexed['name']}")
    print(f"Sample tail: {tail['code']} {tail['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
