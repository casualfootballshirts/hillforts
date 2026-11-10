#!/usr/bin/env python3
"""Check the built site against the content and indexation rules."""

from __future__ import annotations

import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SITES = ROOT / "data" / "sites.json"
PHOTOS = ROOT / "data" / "photos.json"

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
        if "OpenStreetMap contributors" not in footer or "https://www.openstreetmap.org/copyright" not in footer:
            errors += fail(f"{name} footer missing OpenStreetMap attribution")
    if "/assets/consent.js" not in text:
        errors += fail(f"{name} missing consent script")
    header_at = text.find("<header")
    header_end = text.find("</header>")
    header = text[header_at:header_end] if header_at != -1 and header_end > header_at else ""
    if 'src="/assets/logo.svg"' not in header or 'alt="Hillforts Map"' not in header:
        errors += fail(f"{name} missing header logo")
    for needle in (
        'rel="icon" href="/assets/favicon.svg"',
        'rel="icon" href="/assets/favicon-32.png"',
        'rel="apple-touch-icon" href="/assets/apple-touch-icon.png"',
    ):
        if needle not in text:
            errors += fail(f"{name} missing {needle}")
    photo = 'class="fort-photo"' in text
    default_og = 'property="og:image" content="https://hillfortsmap.co.uk/assets/og.png"'
    if photo:
        if 'property="og:image" content="https://hillfortsmap.co.uk/assets/photos/' not in text:
            errors += fail(f"{name} photo page missing its og:image")
        if default_og in text:
            errors += fail(f"{name} photo page still uses the default og:image")
    elif default_og not in text:
        errors += fail(f"{name} missing {default_og}")
    for needle in ATTRIBUTION:
        if needle not in text:
            errors += fail(f"{name} missing attribution {needle}")
    for snippet in BANNED:
        if snippet in text:
            errors += fail(f"{name} contains banned text: {snippet}")
    return errors


def hub_intro_words(text):
    match = re.search(r'<div class="hub-intro">(.*?)</div>', text, re.S)
    if not match:
        return None
    plain = html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))
    return len(plain.split())


def check_hubs(sites):
    """County and nation hubs stay indexable, with original intros and visit lists."""
    import hub_copy

    errors = 0
    by_county = defaultdict(list)
    by_nation = defaultdict(list)
    nation_names = {}
    for site in sites:
        by_county[site["countySlug"]].append(site)
        by_nation[site["nation"]].append(site)
        nation_names[site["nation"]] = site["country"]

    titles = []
    descriptions = []
    hubs = []
    for slug, group in by_nation.items():
        hubs.append((DIST / "nations" / slug / "index.html", group, "nation", nation_names[slug], slug))
    for slug, group in by_county.items():
        hubs.append((
            DIST / "counties" / slug / "index.html",
            group,
            "county",
            group[0]["county"],
            slug,
        ))

    for path, group, kind, name, slug in hubs:
        if not path.exists():
            errors += fail(f"missing hub {path}")
            continue
        text = path.read_text(encoding="utf-8")
        label = f"{kind} {slug}"
        if 'content="index,follow"' not in text:
            errors += fail(f"{label} should stay index,follow")
        if 'data-mode="hub"' not in text or "<h2>Sites</h2>" not in text:
            errors += fail(f"{label} missing map or site list")
        if 'class="hub-stats"' not in text:
            errors += fail(f"{label} missing stats")
        if '"@type": "CollectionPage"' not in text:
            errors += fail(f"{label} missing CollectionPage structured data")
        intro_html = re.search(r'<div class="hub-intro">(.*?)</div>', text, re.S)
        words = hub_intro_words(text)
        if words is None or not intro_html:
            errors += fail(f"{label} missing intro")
            continue
        intro_plain = html.unescape(re.sub(r"<[^>]+>", " ", intro_html.group(1))).lower()
        for pattern, phrase in hub_copy.INTRO_BANS:
            if re.search(pattern, intro_plain):
                errors += fail(f"{label} intro contains banned phrase {phrase}")
        if intro_plain.count("atlas of hillforts") > 1:
            errors += fail(f"{label} intro mentions the Atlas more than once")
        indexed_n = sum(1 for site in group if site.get("index"))
        best = hub_copy.select_best(group, kind)
        main = text.split("<main", 1)[1].split("</main>", 1)[0]
        if re.search(r"\bindexed\b", main, re.I):
            errors += fail(f"{label} uses the word indexed")
        title = re.search(r"<title>(.*?)</title>", text)
        description = re.search(r'<meta name="description" content="(.*?)">', text)
        if not title or not description:
            errors += fail(f"{label} missing title or description")
        else:
            titles.append(html.unescape(title.group(1)))
            descriptions.append(html.unescape(description.group(1)))
        lo, hi = hub_copy.word_limits(len(group), kind)
        if not (lo <= words <= hi):
            errors += fail(f"{label} intro is {words} words, expected {lo}–{hi}")
        if indexed_n >= hub_copy.FULL_INDEXED_MIN:
            if "Best hillforts to visit" not in text:
                errors += fail(f"{label} missing best-hillforts list")
            if '"@type": "ItemList"' not in text:
                errors += fail(f"{label} missing ItemList structured data")
            hrefs = re.findall(r'<ol class="best-list">.*?</ol>', text, re.S)
            found = re.findall(r'href="/sites/([^"]+)/"', hrefs[0]) if hrefs else []
            expected = [site["slug"] for site in best]
            if found != expected:
                errors += fail(f"{label} best list {found} != {expected}")
        else:
            if "Best hillforts to visit" in text or '"@type": "ItemList"' in text:
                errors += fail(f"{label} should not have a best-hillforts list")
        if kind == "county" and f'data-county="{html.escape(name, quote=True)}"' not in text:
            errors += fail(f"{label} map is not limited to {name}")
        if kind == "nation" and f'data-country="{html.escape(name, quote=True)}"' not in text:
            errors += fail(f"{label} map is not limited to {name}")

    if len(titles) != len(set(titles)):
        errors += fail("duplicate hub titles")
    if len(descriptions) != len(set(descriptions)):
        errors += fail("duplicate hub descriptions")
    if len(hubs) != 6 + len(by_county):
        errors += fail("hub count mismatch")
    return errors


LICENCE_NAME = re.compile(
    r"^(CC0|Public domain|CC BY (?:1\.0|2\.0|2\.5|3\.0|4\.0)|"
    r"CC BY-SA (?:1\.0|2\.0|2\.5|3\.0|4\.0)|OGL 1\.0|OGL 3)$"
)


def check_photos(sites):
    """Indexed forts may show one cached photo. Tail pages stay without one."""
    errors = 0
    if not PHOTOS.exists():
        return fail("missing data/photos.json")
    photos = json.loads(PHOTOS.read_text(encoding="utf-8"))
    indexed = {site["slug"]: site for site in sites if site.get("index")}
    extra = set(photos) - set(indexed)
    if extra:
        errors += fail(f"photos.json has {len(extra)} forts that are not indexed")
    photo_dir = ROOT / "src" / "assets" / "photos"
    for slug, photo in photos.items():
        site = indexed.get(slug)
        if not site:
            continue
        for key in ("id", "page", "file", "author", "licence", "licenceUrl", "via"):
            if not photo.get(key):
                errors += fail(f"{slug} photo missing {key}")
        if photo.get("id") != site["code"]:
            errors += fail(f"{slug} photo id does not match {site['code']}")
        author = photo.get("author") or ""
        if "<" in author or ">" in author or "&lt;" in author.lower():
            errors += fail(f"{slug} author still contains HTML")
        if not LICENCE_NAME.match(photo.get("licence") or ""):
            errors += fail(f"{slug} licence {photo.get('licence')!r} is not allowed")
        licence_url = photo.get("licenceUrl") or ""
        if not licence_url.startswith("https://"):
            errors += fail(f"{slug} licence URL is not https")
        host = urllib_host(licence_url).lower()
        if host not in {"creativecommons.org", "www.nationalarchives.gov.uk", "nationalarchives.gov.uk"}:
            errors += fail(f"{slug} licence host {host}")
        via = photo.get("via")
        page = photo.get("page") or ""
        if via == "Wikimedia Commons" and not page.startswith("https://commons.wikimedia.org/wiki/"):
            errors += fail(f"{slug} Commons credit does not link to a file page")
        elif via == "Geograph" and not page.startswith("https://www.geograph.org.uk/photo/"):
            errors += fail(f"{slug} Geograph credit does not link to a photo page")
        elif via not in {"Wikimedia Commons", "Geograph"}:
            errors += fail(f"{slug} via {via!r}")
        file_url = photo.get("file") or ""
        if not file_url.startswith("https://upload.wikimedia.org/"):
            errors += fail(f"{slug} original file is not a Commons upload")
        if urllib_host(file_url).lower().endswith("geograph.org.uk"):
            errors += fail(f"{slug} hotlinks a Geograph file")
        wide = photo_dir / f"{slug}-1200.webp"
        narrow = photo_dir / f"{slug}-600.webp"
        for path in (wide, narrow):
            if not path.is_file():
                errors += fail(f"missing {path.name}")
                continue
            blob = path.read_bytes()[:16]
            if blob[:4] != b"RIFF" or blob[8:12] != b"WEBP":
                errors += fail(f"{path.name} is not WebP")
            if path.stat().st_size > 500_000:
                errors += fail(f"{path.name} is {path.stat().st_size} bytes")
        text = (DIST / "sites" / slug / "index.html").read_text(encoding="utf-8")
        alt = html.escape(f"{site['name']} hillfort", quote=True)
        if f'alt="{alt}"' not in text or 'loading="lazy"' not in text:
            errors += fail(f"{slug} missing alt text or lazy loading")
        if 'class="fort-photo"' not in text:
            errors += fail(f"{slug} missing the photo figure")
        credit_author = html.escape(author, quote=True)
        if f"Photo: {credit_author}," not in text:
            errors += fail(f"{slug} credit line does not name the author")
        if html.escape(licence_url, quote=True) not in text or html.escape(page, quote=True) not in text:
            errors += fail(f"{slug} credit line does not link the licence and source")
        if photo.get("licence") not in text:
            errors += fail(f"{slug} credit line does not name the licence")
        if f"via <a href=\"{html.escape(page, quote=True)}\"" not in text:
            errors += fail(f"{slug} credit line does not use the source page as via")
        og = f'property="og:image" content="https://hillfortsmap.co.uk/assets/photos/{slug}-1200.webp"'
        if og not in text:
            errors += fail(f"{slug} og:image is not the local photo")
        if re.search(r'<img[^>]+src="https?://[^"]*geograph\.org\.uk', text):
            errors += fail(f"{slug} hotlinks a Geograph image")
        narrow_w = int(photo.get("narrowWidth") or 0)
        wide_w = int(photo.get("wideWidth") or 0)
        if narrow_w and f"/assets/photos/{slug}-600.webp {narrow_w}w" not in text:
            errors += fail(f"{slug} srcset is missing the smaller image")
        if wide_w and f"/assets/photos/{slug}-1200.webp {wide_w}w" not in text:
            errors += fail(f"{slug} srcset is missing the wide image")
    for site in sites:
        if site["slug"] in photos and site.get("index"):
            continue
        text = (DIST / "sites" / site["slug"] / "index.html").read_text(encoding="utf-8")
        if 'class="fort-photo"' in text or "/assets/photos/" in text:
            errors += fail(f"{site['code']} should not have a photo")
    return errors


MARKER_ICON_DIR = "/assets/vendor/images/"
MARKER_ICONS = {
    "iconUrl": "marker-icon.png",
    "iconRetinaUrl": "marker-icon-2x.png",
    "shadowUrl": "marker-shadow.png",
}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def check_marker_icons():
    """Leaflet 1.9 prefixes Icon.Default.imagePath onto iconUrl, so these stay bare filenames."""
    errors = 0
    script_path = DIST / "assets" / "directory.js"
    if not script_path.is_file():
        return fail("missing directory.js")
    script = script_path.read_text(encoding="utf-8")
    if not re.search(
        r"""L\.Icon\.Default\.imagePath\s*=\s*['"]/assets/vendor/images/['"]""",
        script,
    ):
        errors += fail("directory.js does not set L.Icon.Default.imagePath to /assets/vendor/images/")
    path_at = script.find("L.Icon.Default.imagePath")
    marker_at = script.find("L.marker(")
    if path_at == -1 or marker_at == -1 or path_at > marker_at:
        errors += fail("directory.js sets the marker icon path after a marker is created")
    for key, name in MARKER_ICONS.items():
        urls = re.findall(rf"""(?<![A-Za-z]){key}\s*:\s*['"]([^'"]+)['"]""", script)
        if urls != [name]:
            errors += fail(f"directory.js {key} should be the bare filename {name}, found {urls}")
        path = DIST / "assets" / "vendor" / "images" / name
        if not path.is_file():
            errors += fail(f"missing marker image {name}")
        elif path.read_bytes()[:8] != PNG_MAGIC:
            errors += fail(f"{name} is not a PNG")
        requested = DIST / (MARKER_ICON_DIR + name).lstrip("/")
        if not requested.is_file():
            errors += fail(f"Leaflet would request {MARKER_ICON_DIR}{name}, which is missing")
    for path in sorted((DIST / "assets").rglob("*.js")):
        if "vendor" in path.parts or path.name == "directory.js":
            continue
        text = path.read_text(encoding="utf-8")
        if "L.marker" in text or "L.Icon" in text or "new L.icon" in text:
            errors += fail(f"{path.relative_to(DIST).as_posix()} also creates Leaflet markers")
    return errors


def urllib_host(url):
    match = re.match(r"https://([^/]+)/", url or "")
    return match.group(1) if match else ""


def section_hrefs(text, ul_class):
    match = re.search(rf'<ul class="county-grid {ul_class}">(.*?)</ul>', text, re.S)
    if not match:
        return None
    return re.findall(r'href="([^"]+)"', match.group(1))


def check_home_highlights(sites, home, sitemap):
    """Homepage highlights link only to indexable URLs that are in the sitemap."""
    import build_site

    errors = 0
    title = re.search(r"<title>(.*?)</title>", home)
    description = re.search(r'<meta name="description" content="(.*?)">', home)
    og_title = re.search(r'<meta property="og:title" content="(.*?)">', home)
    og_description = re.search(r'<meta property="og:description" content="(.*?)">', home)
    expected_title = "Map of Hillforts in Britain and Ireland"
    expected_description = (
        "Interactive map of 4,147 hillforts across Britain and Ireland. "
        "Browse by nation and county, or search the full directory."
    )
    if not title or html.unescape(title.group(1)) != expected_title:
        errors += fail(f"homepage title is {title.group(1) if title else 'missing'}")
    if not description or html.unescape(description.group(1)) != expected_description:
        found = description.group(1) if description else "missing"
        errors += fail(f"homepage description is {found}")
    if not og_title or html.unescape(og_title.group(1)) != expected_title:
        errors += fail("homepage og:title does not match the title")
    if not og_description or html.unescape(og_description.group(1)) != expected_description:
        errors += fail("homepage og:description does not match the description")
    if expected_description != build_site.home_description(len(sites)):
        errors += fail("homepage description helper drifted from the published wording")
    if "search the full directory" in expected_description and 'type="search"' not in home:
        errors += fail("homepage meta claims search but there is no search field")

    start = home.find('<div class="home-highlights">')
    end = home.find("<h2>Matching sites</h2>", start if start != -1 else 0)
    if start == -1 or end == -1:
        errors += fail("homepage missing highlights")
        return errors
    block = home[start:end]
    for phrase in ("indexed", "noindex", "sitemap", "search console", "crawl"):
        if phrase in block.lower():
            errors += fail(f"homepage highlights contain meta text: {phrase}")

    locs = set(re.findall(r"<loc>(.*?)</loc>", sitemap))
    by_county = {}
    by_slug = {}
    for site in sites:
        by_county.setdefault(site["countySlug"], []).append(site)
        by_slug[site["slug"]] = site

    county_hrefs = section_hrefs(home, "home-counties")
    fort_hrefs = section_hrefs(home, "home-forts")
    if not county_hrefs or not fort_hrefs:
        errors += fail("homepage highlights missing county or fort links")
        return errors

    counties = {}
    for site in sites:
        bucket = counties.setdefault(site["countySlug"], {
            "slug": site["countySlug"],
            "name": site["county"],
            "country": site["country"],
            "nation": site["nation"],
            "sites": [],
        })
        bucket["sites"].append(site)
    expected_counties = [f"/counties/{county['slug']}/" for county in build_site.highlight_counties(counties)]
    expected_forts = [
        f"/sites/{site['slug']}/"
        for site in build_site.highlight_forts(build_site.highlight_counties(counties))
    ]
    if county_hrefs != expected_counties:
        errors += fail(f"homepage counties {county_hrefs} != {expected_counties}")
    if fort_hrefs != expected_forts:
        errors += fail(f"homepage forts {fort_hrefs} != {expected_forts}")
    if "/counties/dorset/" not in county_hrefs:
        errors += fail("homepage counties omit Dorset")
    if "/sites/en3598-maiden-castle-winterborne-st-martin/" not in fort_hrefs:
        errors += fail("homepage forts omit Maiden Castle")
    if not (10 <= len(county_hrefs) <= 16) or not (10 <= len(fort_hrefs) <= 16):
        errors += fail(f"homepage highlights expected about 12 links, got {len(county_hrefs)} counties and {len(fort_hrefs)} forts")

    nations = set()
    for href in county_hrefs:
        slug = href.strip("/").split("/")[-1]
        group = by_county.get(slug)
        if not group:
            errors += fail(f"homepage county link unknown: {href}")
            continue
        nations.add(group[0]["nation"])
        url = f"https://hillfortsmap.co.uk{href}"
        if url not in locs:
            errors += fail(f"homepage county not in sitemap: {href}")
        page = DIST / "counties" / slug / "index.html"
        if not page.exists():
            errors += fail(f"homepage county page missing: {href}")
        elif 'content="index,follow"' not in page.read_text(encoding="utf-8"):
            errors += fail(f"homepage county is not indexable: {href}")
    if len(nations) < 6:
        errors += fail(f"homepage counties miss a nation: {sorted(nations)}")

    for href in fort_hrefs:
        if not href.startswith("/sites/") or not href.endswith("/"):
            errors += fail(f"homepage fort link is not a site page: {href}")
            continue
        slug = href.strip("/").split("/")[-1]
        site = by_slug.get(slug)
        if site is None:
            errors += fail(f"homepage fort link unknown: {href}")
            continue
        if not site.get("index"):
            errors += fail(f"homepage fort is a noindexed tail page: {href}")
        url = f"https://hillfortsmap.co.uk{href}"
        if url not in locs:
            errors += fail(f"homepage fort not in sitemap: {href}")
        page = DIST / "sites" / slug / "index.html"
        if not page.exists():
            errors += fail(f"homepage fort page missing: {href}")
            continue
        page_html = page.read_text(encoding="utf-8")
        if 'content="index,follow"' not in page_html:
            errors += fail(f"homepage fort page is not indexable: {href}")
        if 'content="noindex,follow"' in page_html:
            errors += fail(f"homepage fort page is noindex: {href}")
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
    for name in (
        "logo.svg",
        "logo-mark.svg",
        "favicon.svg",
        "favicon-32.png",
        "favicon.ico",
        "apple-touch-icon.png",
        "og.png",
    ):
        if not (DIST / "assets" / name).exists():
            errors += fail(f"missing asset {name}")
    errors += check_marker_icons()

    cname = (DIST / "CNAME").read_text(encoding="utf-8").strip()
    if cname != "hillfortsmap.co.uk":
        errors += fail(f"unexpected CNAME: {cname}")

    robots = (DIST / "robots.txt").read_text(encoding="utf-8")
    if "Sitemap: https://hillfortsmap.co.uk/sitemap.xml" not in robots:
        errors += fail("robots.txt missing sitemap")

    sitemap = (DIST / "sitemap.xml").read_text(encoding="utf-8")
    expected_urls = 1 + len(INFO_INDEXED) + 6 + len(county_slugs) + len(indexed)
    if expected_urls != 487:
        errors += fail(f"sitemap formula changed: {expected_urls} != 487")
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
    errors += check_home_highlights(sites, home, sitemap)
    if "data-mode=\"site\"" not in indexed_html:
        errors += fail("site map missing")
    if "Cornwall" not in county:
        errors += fail("county page content")
    if "Scotland" not in nation:
        errors += fail("nation page content")
    errors += check_hubs(sites)

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

    access_path = ROOT / "data" / "access.json"
    if not access_path.exists():
        errors += fail("missing data/access.json")
        access = {}
    else:
        access = json.loads(access_path.read_text(encoding="utf-8"))
    if set(access) != {site["slug"] for site in sites}:
        errors += fail("access.json slugs do not match sites.json")
    banned_access = ("no data", "No car park", "legal access", "you can walk", "right to visit")
    nearby_line = re.compile(
        r" is \d+(?:\.\d+)? (?:mile|miles|yards) to the "
        r"(?:north|north-east|east|south-east|south|south-west|west|north-west)\.$"
    )
    metric_distance = re.compile(r"\b\d+(?:\.\d+)? (?:m|km)\b", re.I)
    parking_checked = way_checked = bare_checked = 0
    for site in sites:
        text = (DIST / "sites" / site["slug"] / "index.html").read_text(encoding="utf-8")
        record = access.get(site["slug"]) or {}
        main = text.split("<main", 1)[-1].split("</main>", 1)[0]
        if "<h3>Other hill forts nearby</h3>" not in text:
            errors += fail(f"{site['code']} missing Other hill forts nearby")
            break
        nearby = re.findall(r'<li class="nearby-fort">(.*?)</li>', text)
        if len(nearby) != 5:
            errors += fail(f"{site['code']} should list five nearby hillforts")
            break
        nearby_ok = True
        for item in nearby:
            plain = html.unescape(re.sub(r"<[^>]+>", "", item))
            if not nearby_line.search(plain):
                errors += fail(f"{site['code']} nearby line is not 'Name is distance to the bearing': {plain}")
                nearby_ok = False
                break
            if 'href="/sites/' not in item:
                errors += fail(f"{site['code']} nearby fort is missing its page link")
                nearby_ok = False
                break
        if not nearby_ok:
            break
        if "<h3>Getting there</h3>" not in text:
            errors += fail(f"{site['code']} missing Getting there")
            break
        for phrase in banned_access:
            if phrase in text:
                errors += fail(f"{site['code']} contains {phrase}")
                break
        if "OpenStreetMap shows" in main or "on OpenStreetMap" in main:
            errors += fail(f"{site['code']} still attributes OpenStreetMap in the page body")
            break
        metric_ok = True
        for chunk in re.findall(r'<ul class="(?:getting-there|nearby-forts)">(.*?)</ul>', text, re.S):
            plain = html.unescape(re.sub(r"<[^>]+>", " ", chunk))
            if metric_distance.search(plain):
                errors += fail(f"{site['code']} still uses a metric distance: {plain.strip()[:180]}")
                metric_ok = False
                break
        if not metric_ok:
            break
        parks = record.get("parking") or []
        directions = text.count("https://www.google.com/maps/dir/?api=1&amp;destination=")
        if directions != len(parks):
            errors += fail(f"{site['code']} has {directions} directions links for {len(parks)} car parks")
            break
        if parks:
            if "Nearest car park:" not in text:
                errors += fail(f"{site['code']} missing Nearest car park")
                break
            if len(parks) > 1 and "Next closest car park:" not in text:
                errors += fail(f"{site['code']} missing Next closest car park")
                break
            parking_checked += 1
        elif "car park" in text:
            errors += fail(f"{site['code']} mentions a car park without a cached one")
            break
        else:
            bare_checked += 1
        getting = re.search(r'<ul class="getting-there">(.*?)</ul>', text, re.S)
        getting_html = getting.group(1) if getting else ""
        way = record.get("way") or {}
        if way.get("kind"):
            if "Closest " not in getting_html or " within " not in getting_html:
                errors += fail(f"{site['code']} missing a path distance")
                break
            way_checked += 1
        elif " within " in getting_html:
            errors += fail(f"{site['code']} mentions a path without a cached one")
            break
        place = record.get("place") or {}
        if place.get("name") and place.get("kind") in {"town", "village"}:
            if f"Nearest {place['kind']}:" not in text:
                errors += fail(f"{site['code']} missing nearest {place['kind']}")
                break
    if parking_checked < 1 or way_checked < 1:
        errors += fail("could not sample a car park and a path")
    maiden = DIST / "sites" / "en3598-maiden-castle-winterborne-st-martin" / "index.html"
    if maiden.exists():
        maiden_text = maiden.read_text(encoding="utf-8")
        for phrase in (
            "Nearest car park: Maiden Castle, 480 yards to the north.",
            "Next closest car park: 0.8 miles to the south-east.",
            "Closest footpath: within 40 yards.",
            "Nearest village: Martinstown, 1.3 miles to the west.",
            '<a href="/sites/en3587-chalbury/">Chalbury</a> is 3.3 miles to the south-east.',
            "<h3>Other hill forts nearby</h3>",
        ):
            if phrase not in maiden_text:
                errors += fail(f"Maiden Castle missing {phrase}")
    else:
        errors += fail("missing Maiden Castle page")
    print(f"Getting there checked on {len(sites)} site pages ({bare_checked} without a car park)")

    errors += check_photos(sites)
    km_unit = re.compile(r"(?<![A-Za-z])km(?![A-Za-z])", re.I)
    kilometre_word = re.compile(r"\bkilomet(?:re|er)s?\b", re.I)
    km_hits = []
    osm_hits = []
    for path in html_files:
        page = path.read_text(encoding="utf-8")
        body = page.split("<main", 1)[-1].split("</main>", 1)[0] if "<main" in page else page
        if km_unit.search(page) or kilometre_word.search(page):
            km_hits.append(path.relative_to(DIST).as_posix())
        if "OpenStreetMap shows" in body or "on OpenStreetMap" in body:
            osm_hits.append(path.relative_to(DIST).as_posix())
    if km_hits:
        errors += fail(f"km remains on {len(km_hits)} public pages, for example {km_hits[0]}")
    if osm_hits:
        errors += fail(
            f"OpenStreetMap shows / on OpenStreetMap remains on {len(osm_hits)} pages, "
            f"for example {osm_hits[0]}"
        )
    else:
        print(f"No km, and no OpenStreetMap body phrasing, on {len(html_files)} public pages")

    if errors:
        print(f"{errors} checks failed")
        return 1
    print("All checks passed")
    print(f"Sample indexed: {sample_indexed['code']} {sample_indexed['name']}")
    print(f"Sample tail: {tail['code']} {tail['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
