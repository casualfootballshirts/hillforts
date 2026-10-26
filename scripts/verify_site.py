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

GA_ID = "G-3QGXKPZ9XK"
CONSENT_KEY = "hillforts_consent"
PRIVACY_EMAIL = "privacy@hillfortsmap.co.uk"
CONSENT_DENIED = (
    "analytics_storage",
    "ad_storage",
    "ad_user_data",
    "ad_personalization",
)
# index,follow pages are listed in the sitemap. These four follow that rule.
INFO_INDEXED = ("about", "privacy", "cookies", "terms")
FOOTER_LINKS = (
    ('href="/about/"', "About"),
    ('href="/privacy/"', "Privacy"),
    ('href="/cookies/"', "Cookies"),
    ('href="/terms/"', "Terms"),
)


def fail(message):
    print("FAIL", message)
    return 1


def check_chrome(name, text):
    errors = 0
    tag = f"https://www.googletagmanager.com/gtag/js?id={GA_ID}"
    default = "gtag('consent', 'default'"
    config = f"gtag('config', '{GA_ID}')"
    if tag not in text:
        errors += fail(f"{name} missing Google tag")
    if default not in text:
        errors += fail(f"{name} missing consent default")
    if config not in text:
        errors += fail(f"{name} missing gtag config")
    if tag in text and default in text and config in text:
        default_at = text.find(default)
        tag_at = text.find(tag)
        config_at = text.find(config)
        if not (default_at < tag_at < config_at):
            errors += fail(f"{name} consent default is not before the Google tag and gtag config")
        js_at = text.find("gtag('js', new Date())")
        if js_at == -1 or "=== 'accepted'" not in text[js_at:config_at]:
            errors += fail(f"{name} runs gtag config without an accepted choice")
    for key in CONSENT_DENIED:
        if f"'{key}': 'denied'" not in text:
            errors += fail(f"{name} missing denied {key}")
    if f"localStorage.getItem('{CONSENT_KEY}') === 'accepted'" not in text:
        errors += fail(f"{name} does not restore an accepted choice before config")
    banner_at = text.find('id="cookie-banner"')
    content_at = text.find('id="content"')
    banner = text[banner_at:content_at] if banner_at != -1 and content_at > banner_at else ""
    if not banner:
        errors += fail(f"{name} missing cookie banner")
    else:
        if "hidden" not in banner.split(">", 1)[0]:
            errors += fail(f"{name} cookie banner is not hidden until a choice is needed")
        if 'href="/cookies/"' not in banner:
            errors += fail(f"{name} banner missing cookie policy link")
        if 'class="cookie-choice" id="cookie-reject"' not in banner:
            errors += fail(f"{name} missing Reject button")
        if 'class="cookie-choice" id="cookie-accept"' not in banner:
            errors += fail(f"{name} missing Accept button")
        if f'data-consent-key="{CONSENT_KEY}"' not in banner:
            errors += fail(f"{name} missing consent storage key")
    footer_at = text.find('<footer class="site-footer">')
    footer = text[footer_at:] if footer_at != -1 else ""
    if not footer:
        errors += fail(f"{name} missing footer")
    else:
        for needle, label in FOOTER_LINKS:
            if needle not in footer:
                errors += fail(f"{name} footer missing {label}")
        if "data-cookie-settings" not in footer or ">Cookie settings</button>" not in footer:
            errors += fail(f"{name} footer missing Cookie settings")
    if "/assets/consent.js" not in text:
        errors += fail(f"{name} missing consent script")
    for needle in ATTRIBUTION:
        if needle not in text:
            errors += fail(f"{name} missing attribution {needle}")
    for snippet in BANNED:
        if snippet in text:
            errors += fail(f"{name} contains banned text: {snippet}")
    return errors


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
    expected_urls = 1 + len(INFO_INDEXED) + 6 + len(county_slugs) + len(indexed)
    if sitemap.count("<loc>") != expected_urls:
        errors += fail(f"sitemap locs {sitemap.count('<loc>')} != {expected_urls}")
    for slug in INFO_INDEXED:
        if f"https://hillfortsmap.co.uk/{slug}/" not in sitemap:
            errors += fail(f"{slug} missing from sitemap")
    if "https://hillfortsmap.co.uk/404.html" in sitemap:
        errors += fail("404 listed in sitemap")

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

    html_files = sorted(DIST.rglob("*.html"))
    expected_html = len(sites) + 6 + len(county_slugs) + 1 + 1 + len(INFO_INDEXED)
    if len(html_files) != expected_html:
        errors += fail(f"expected {expected_html} html files, found {len(html_files)}")
    for path in html_files:
        errors += check_chrome(path.relative_to(DIST).as_posix(), path.read_text(encoding="utf-8"))
    print(f"Checked tag, consent, banner, and footer on {len(html_files)} pages")

    for slug in INFO_INDEXED:
        path = DIST / slug / "index.html"
        if not path.exists():
            errors += fail(f"missing {slug} page")
            continue
        text = path.read_text(encoding="utf-8")
        if 'content="index,follow"' not in text:
            errors += fail(f"{slug} should be index,follow")
        for bad in ("example.com", "lorem ipsum", "[insert", "todo@", "placeholder@"):
            if bad in text.lower():
                errors += fail(f"{slug} contains placeholder text: {bad}")

    about = (DIST / "about" / "index.html").read_text(encoding="utf-8") if (DIST / "about" / "index.html").exists() else ""
    header = home.split("<main", 1)[0]
    if 'href="/about/"' not in header or ">About</a>" not in header:
        errors += fail("About missing from main navigation")
    if 'href="/about/" aria-current="page"' not in about:
        errors += fail("About page does not mark itself current")
    for needle in (
        "Atlas of Hillforts of Britain and Ireland",
        "https://doi.org/10.5284/1118744",
        "private land",
        "scheduled monuments",
        "public rights of way",
        "earthworks",
    ):
        if needle not in about:
            errors += fail(f"about page missing {needle}")

    policy_phrases = {
        "privacy": (
            "Last updated 26 October 2026",
            "UK GDPR",
            "Information Commissioner's Office",
            "https://ico.org.uk/make-a-complaint/",
            "https://policies.google.com/privacy",
            "https://osmfoundation.org/wiki/Privacy_Policy",
            "https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement",
            CONSENT_KEY,
            GA_ID,
            "no accounts",
            "Who we are",
            f"mailto:{PRIVACY_EMAIL}",
        ),
        "cookies": (
            "Last updated 26 October 2026",
            "_ga",
            "_ga_" + GA_ID.split("-", 1)[1],
            CONSENT_KEY,
            "2 years",
            "localStorage",
            "https://policies.google.com/privacy",
            f"mailto:{PRIVACY_EMAIL}",
        ),
        "terms": (
            "Last updated 26 October 2026",
            f"mailto:{PRIVACY_EMAIL}",
            "as-is",
            "right of access",
            "own risk",
            "CC BY-SA 4.0",
            "https://creativecommons.org/licenses/by-sa/4.0/",
        ),
    }
    for slug, phrases in policy_phrases.items():
        text = (DIST / slug / "index.html").read_text(encoding="utf-8") if (DIST / slug / "index.html").exists() else ""
        for phrase in phrases:
            if phrase not in text:
                errors += fail(f"{slug} page missing {phrase}")
        if "postal address" in text.lower() or "does not publish a postal address" in text:
            errors += fail(f"{slug} still says no contact address is published")

    consent_js = DIST / "assets" / "consent.js"
    if not consent_js.exists():
        errors += fail("missing consent.js")
    else:
        script = consent_js.read_text(encoding="utf-8")
        for needle in (
            "localStorage",
            "analytics_storage",
            '"granted"',
            '"denied"',
            "cookie-accept",
            "cookie-reject",
            "data-cookie-settings",
            'callGtag("config"',
            "_ga",
        ):
            if needle not in script:
                errors += fail(f"consent.js missing {needle}")

    if errors:
        print(f"{errors} checks failed")
        return 1
    print("All checks passed")
    print(f"Sample indexed: {sample_indexed['code']} {sample_indexed['name']}")
    print(f"Sample tail: {tail['code']} {tail['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
