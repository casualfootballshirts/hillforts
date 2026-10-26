#!/usr/bin/env python3
"""Build the static Hillforts Map site into dist/."""

from __future__ import annotations

import html
import json
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DATA = ROOT / "data" / "sites.json"
DIST = ROOT / "dist"
BASE = "https://hillfortsmap.co.uk"
GA_MEASUREMENT_ID = "G-3QGXKPZ9XK"
CONSENT_STORAGE_KEY = "hillforts_consent"
POLICY_UPDATED = "26 October 2026"
INFO_PAGES = ("about", "privacy", "cookies", "terms")

NATION_ORDER = [
    ("Scotland", "scotland"),
    ("England", "england"),
    ("Wales", "wales"),
    ("Republic of Ireland", "republic-of-ireland"),
    ("Northern Ireland", "northern-ireland"),
    ("Isle of Man", "isle-of-man"),
]

TYPE_LABELS = {
    "contour": "contour fort",
    "partial-contour": "partial contour fort",
    "promontory": "promontory fort",
    "hillslope": "hillslope fort",
    "level": "level-terrain fort",
    "marsh": "marsh fort",
    "multiple": "multiple enclosure",
}

CONDITION_LABELS = {
    "extant": "Extant",
    "cropmark": "Cropmark",
    "destroyed": "Likely destroyed",
}

MORPH_LABELS = {
    "univallate": "univallate",
    "partial-univallate": "partial univallate",
    "bivallate": "bivallate",
    "partial-bivallate": "partial bivallate",
    "multivallate": "multivallate",
    "partial-multivallate": "partial multivallate",
    "unknown": "unknown",
}

PERIOD_LABELS = {
    "pre-1200": "before 1200 BC",
    "1200-800": "1200–800 BC",
    "800-400": "800–400 BC",
    "400-ad50": "400 BC–AD 50",
    "ad50-400": "AD 50–400",
    "ad400-800": "AD 400–800",
    "post-800": "after AD 800",
    "unknown": "undated",
}

TOPO_LABELS = {
    "hilltop": "hilltop",
    "coastal-promontory": "coastal promontory",
    "inland-promontory": "inland promontory",
    "valley-bottom": "valley bottom",
    "knoll": "knoll or outcrop",
    "ridge": "ridge",
    "scarp": "cliff, plateau edge, or scarp",
    "hillslope": "hillslope",
    "lowland": "lowland",
    "spur": "spur",
}

ASPECT_LABELS = {
    "north": "north",
    "northeast": "northeast",
    "east": "east",
    "southeast": "southeast",
    "south": "south",
    "southwest": "southwest",
    "west": "west",
    "northwest": "northwest",
    "level": "level",
}

LANDUSE_LABELS = {
    "woodland": "woodland",
    "forestry": "commercial forestry",
    "parkland": "parkland",
    "pasture": "pasture",
    "arable": "arable",
    "scrub": "scrub or bracken",
    "outcrop": "bare outcrop",
    "moorland": "heather moorland",
    "heath": "heath",
    "built-up": "built-up land",
    "coastal-grassland": "coastal grassland",
}

SURFACE_LABELS = {
    "earthen-bank": "earthen bank",
    "stone-wall": "stone wall",
    "rubble": "rubble",
    "wall-walk": "wall-walk",
    "timber": "timber",
    "vitrification": "vitrification",
    "burning": "other burning",
    "palisade": "palisade",
    "counterscarp": "counterscarp bank",
    "berm": "berm",
    "unfinished": "unfinished work",
}

EXCAVATED_LABELS = {
    "earthen-bank": "earthen bank",
    "stone-wall": "stone wall",
    "murus-duplex": "murus duplex",
    "timber-framed": "timber-framed wall",
    "timber-laced": "timber-laced wall",
    "vitrification": "vitrification",
    "burning": "other burning",
    "palisade": "palisade",
    "counterscarp": "counterscarp bank",
    "berm": "berm",
    "unfinished": "unfinished work",
}

INTERIOR_LABELS = {
    "round-stone": "round stone structures",
    "rectangular-stone": "rectangular stone structures",
    "platforms": "curvilinear platforms",
    "roundhouses": "other roundhouse evidence",
    "pits": "pits",
    "quarry-hollows": "quarry hollows",
}

INTERIOR_EX_LABELS = {
    "pits": "pits",
    "postholes": "postholes",
    "roundhouses": "roundhouses",
    "rectangular": "rectangular structures",
    "roads": "roads or tracks",
    "quarry-hollows": "quarry hollows",
}

FINDS_LABELS = {
    "pottery": "pottery",
    "metal": "metal",
    "metalworking": "metalworking",
    "human-bones": "human bones",
    "animal-bones": "animal bones",
    "lithics": "lithics",
    "environmental": "environmental material",
}

WATER_LABELS = {
    "spring": "spring",
    "stream": "stream",
    "pool": "pool",
    "flush": "flush",
    "well": "well or cistern",
}

FLAG_LABELS = {
    "guard-chambers": "guard chambers",
    "chevaux-de-frise": "chevaux de frise",
    "annex": "annex",
    "multi-period": "multi-period enclosure system",
    "pre-activity": "pre-hillfort activity",
    "post-activity": "later activity",
    "ditches": "ditches",
    "gang-working": "gang working",
}

FILTERS = """
<form class="filters" data-filters>
  <div class="filter-search">
    <label for="q">Search</label>
    <input id="q" name="q" type="search" placeholder="Name, parish, or Atlas number" autocomplete="off">
  </div>
  <fieldset>
    <legend>Type</legend>
    <label><input type="checkbox" name="type" value="contour"> Contour</label>
    <label><input type="checkbox" name="type" value="partial-contour"> Partial contour</label>
    <label><input type="checkbox" name="type" value="promontory"> Promontory</label>
    <label><input type="checkbox" name="type" value="hillslope"> Hillslope</label>
    <label><input type="checkbox" name="type" value="level"> Level terrain</label>
    <label><input type="checkbox" name="type" value="marsh"> Marsh</label>
    <label><input type="checkbox" name="type" value="multiple"> Multiple enclosure</label>
  </fieldset>
  <fieldset>
    <legend>Condition</legend>
    <label><input type="checkbox" name="condition" value="extant"> Extant</label>
    <label><input type="checkbox" name="condition" value="cropmark"> Cropmark</label>
    <label><input type="checkbox" name="condition" value="destroyed"> Likely destroyed</label>
  </fieldset>
  <fieldset>
    <legend>Morphology</legend>
    <label><input type="checkbox" name="morph" value="univallate"> Univallate</label>
    <label><input type="checkbox" name="morph" value="bivallate"> Bivallate</label>
    <label><input type="checkbox" name="morph" value="multivallate"> Multivallate</label>
  </fieldset>
  <fieldset>
    <legend>Scheduled monument</legend>
    <label><input type="radio" name="scheduled" value="" checked> Any</label>
    <label><input type="radio" name="scheduled" value="yes"> Yes</label>
    <label><input type="radio" name="scheduled" value="no"> No</label>
  </fieldset>
  <button type="reset">Clear</button>
</form>
"""


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def join_and(items) -> str:
    items = [item for item in items if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def article(label: str) -> str:
    return ("an " if label[:1].lower() in "aeiou" else "a ") + label


def format_number(value) -> str:
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def format_coord(value) -> str:
    return f"{float(value):.5f}"


def labels(codes, table):
    return [table[code] for code in codes or [] if code in table]


def morph_parents(codes):
    parents = []
    for code in codes or []:
        parent = None
        if "multivallate" in code:
            parent = "multivallate"
        elif "bivallate" in code:
            parent = "bivallate"
        elif "univallate" in code:
            parent = "univallate"
        if parent and parent not in parents:
            parents.append(parent)
    return parents


def search_text(site) -> str:
    parts = [
        site.get("name") or "",
        site.get("code") or "",
        site.get("county") or "",
        site.get("parish") or "",
        site.get("historic") or "",
    ]
    parts.extend(site.get("alt") or [])
    return " ".join(parts).lower()


def place_phrase(site) -> str:
    parts = []
    parish = site.get("parish")
    county = site.get("county")
    if parish and parish != county:
        parts.append(parish)
    if county:
        parts.append(county)
    if site.get("country"):
        parts.append(site["country"])
    return ", ".join(parts)


def visitor_copy(site) -> list[str]:
    """Original visitor text built only from structured flags and measurements."""
    sentences = []
    type_labels = labels(site.get("types"), TYPE_LABELS)
    if type_labels:
        kind = join_and(article(label) for label in type_labels)
    else:
        kind = "a hillfort"
    sentences.append(f"{site['name']} is {kind} in {place_phrase(site)}.")
    if site.get("alt"):
        sentences.append("Other names on the record: " + join_and(site["alt"]) + ".")

    condition = set(site.get("condition") or [])
    extant = "extant" in condition
    destroyed = "destroyed" in condition
    cropmark = "cropmark" in condition
    if extant and destroyed:
        status = "It is recorded as both extant and likely destroyed"
        visible = "Survival on the ground may be uneven."
    elif extant and cropmark:
        status = "It is recorded as extant, with cropmark evidence as well"
        visible = "Banks or ramparts are the remains most likely to be visible."
    elif extant:
        status = "It is recorded as extant"
        visible = "Banks or ramparts are the remains most likely to be visible."
    elif cropmark:
        status = "It is recorded as a cropmark"
        visible = "The enclosure is more likely to show from the air than as standing earthworks."
    elif destroyed:
        status = "It is recorded as likely destroyed"
        visible = "Surface remains may be slight or absent."
    else:
        status = "No condition flag is set on the record"
        visible = ""

    detail = []
    morphs = [label for label in labels(site.get("morph"), MORPH_LABELS) if label != "unknown"]
    if morphs:
        detail.append("a " + join_and(morphs) + " rampart form")
    if site.get("surface"):
        detail.append("surface evidence of " + join_and(labels(site["surface"], SURFACE_LABELS)))
    if site.get("enclosed"):
        detail.append(f"an enclosed area of {format_number(site['enclosed'])} hectares")
    if detail:
        sentences.append(status + ", with " + join_and(detail) + ".")
    else:
        sentences.append(status + ".")
    if visible:
        sentences.append(visible)

    topo = site.get("topo") or []
    landscape = []
    if topo:
        places = []
        for code in topo:
            label = TOPO_LABELS[code]
            if code == "lowland":
                places.append("lowland")
            else:
                places.append(article(label))
        if topo == ["lowland"]:
            landscape.append("in a lowland setting")
        else:
            landscape.append("on " + join_and(places))
    if site.get("altitude") is not None:
        landscape.append(f"at {format_number(site['altitude'])} m")
    aspects = site.get("aspect") or []
    directions = [ASPECT_LABELS[code] for code in aspects if code != "level"]
    if directions:
        landscape.append("facing " + join_and(directions))
    if landscape:
        sentences.append("The topographic record places it " + join_and(landscape) + ".")
    if "level" in aspects and not directions:
        sentences.append("The aspect is recorded as level.")
    if site.get("landuse"):
        sentences.append(
            "Recorded land use includes " + join_and(labels(site["landuse"], LANDUSE_LABELS)) + "."
        )

    periods = [PERIOD_LABELS[code] for code in site.get("periods") or [] if code != "unknown"]
    methods = site.get("dating") or []
    if periods or methods:
        dating = "Dating evidence is recorded"
        if periods:
            dating += " for " + join_and(periods)
        if methods:
            dating += " (" + join_and(methods) + ")"
        reliability = site.get("datingReliability")
        if reliability and reliability != "D - None":
            dating += f". Reliability is recorded as {reliability}"
        sentences.append(dating + ".")
    if site.get("scheduled"):
        sentences.append(f"A scheduled monument number is recorded ({site['scheduled']}).")
    return sentences


def source_links(site):
    links = [("Atlas of Hillforts record", site["atlas"])]
    if site.get("wikipedia"):
        links.append(("Wikipedia", site["wikipedia"]))
    if site.get("wiki"):
        links.append(("Wikidata", f"https://www.wikidata.org/wiki/{site['wiki']}"))
    if site.get("nmrUrl"):
        links.append(("Canmore", site["nmrUrl"]))
    scheduled = str(site.get("scheduled") or "")
    monument = str(site.get("nmrMonument") or "")
    if site["country"] == "England" and scheduled.isdigit():
        links.append((
            "Historic England list entry",
            f"https://historicengland.org.uk/listing/the-list/list-entry/{scheduled}",
        ))
    if site["country"] == "England" and monument.isdigit():
        links.append((
            "Historic England research record",
            f"https://heritagegateway.org.uk/Gateway/Results_Single.aspx?uid={monument}&resourceID=19191",
        ))
    if site["country"] == "Scotland" and scheduled.isdigit():
        links.append((
            "Historic Environment Scotland designation",
            f"https://www.trove.scot/designation/SM{scheduled}",
        ))
    if site["country"] == "Wales" and monument.isdigit():
        links.append(("Coflein", f"https://coflein.gov.uk/en/site/{monument}/"))
    if site["country"] == "Republic of Ireland" and site.get("herId"):
        links.append((
            "Archaeological Survey of Ireland",
            "https://maps.archaeology.ie/HistoricEnvironment/",
        ))
    if site["country"] == "Northern Ireland" and site.get("herId"):
        links.append((
            "Northern Ireland Sites and Monuments Record",
            "https://apps.communities-ni.gov.uk/NISMR-PUBLIC/Default.aspx",
        ))
    return links


def fact_rows(site):
    sections = []

    location = [
        ("Atlas number", f"{site['code']} ({site['id']})"),
        ("Country", site.get("country")),
        ("Current county or unitary authority", site.get("county")),
    ]
    if site.get("historic") and site.get("historic") != site.get("county"):
        location.append(("Historic county", site["historic"]))
    elif site.get("historic"):
        location.append(("Historic county", site["historic"]))
    if site.get("parish"):
        location.append(("Parish, community, or townland", site["parish"]))
    if site.get("secondCounty"):
        location.append(("Also recorded in", site["secondCounty"]))
    if site.get("ngr"):
        location.append(("National Grid reference", site["ngr"]))
    location.append(("Latitude", format_coord(site["lat"])))
    location.append(("Longitude", format_coord(site["lon"])))
    if site.get("altitude") is not None:
        location.append(("Altitude", f"{format_number(site['altitude'])} m"))
    sections.append(("Location", location))

    classification = []
    if site.get("types"):
        classification.append(("Type", join_and(labels(site["types"], TYPE_LABELS))))
    if site.get("condition"):
        classification.append(("Condition", join_and(labels(site["condition"], CONDITION_LABELS))))
    morphs = [label for label in labels(site.get("morph"), MORPH_LABELS) if label != "unknown"]
    if morphs:
        classification.append(("Morphology", join_and(morphs)))
    if "circuit" in site:
        classification.append(("Complete rampart circuit", "Yes" if site["circuit"] else "No"))
    if site.get("ramparts") is not None:
        classification.append(("Number of ramparts", format_number(site["ramparts"])))
    quadrants = site.get("quadrants") or {}
    if quadrants and len(set(quadrants.values())) > 1:
        order = [("ne", "NE"), ("se", "SE"), ("sw", "SW"), ("nw", "NW")]
        text = ", ".join(f"{label} {format_number(quadrants[key])}" for key, label in order if key in quadrants)
        classification.append(("Ramparts by quadrant", text))
    if site.get("ditchCount") is not None:
        classification.append(("Number of ditches", format_number(site["ditchCount"])))
    if site.get("entrances") is not None:
        classification.append(("Possible original entrances", format_number(site["entrances"])))
    if site.get("breaks") is not None:
        classification.append(("Breaks through the ramparts", format_number(site["breaks"])))
    if site.get("enclosed") is not None:
        classification.append(("Enclosed area", f"{format_number(site['enclosed'])} ha"))
    if site.get("areas"):
        classification.append((
            "Enclosure areas",
            ", ".join(f"{format_number(area)} ha" for area in site["areas"]),
        ))
    if site.get("footprint") is not None:
        classification.append(("Footprint", f"{format_number(site['footprint'])} ha"))
    if site.get("surface"):
        classification.append(("Enclosing works, as visible", join_and(labels(site["surface"], SURFACE_LABELS))))
    if site.get("excavated"):
        classification.append(("Enclosing works, excavated", join_and(labels(site["excavated"], EXCAVATED_LABELS))))
    if site.get("flags"):
        classification.append(("Also recorded", join_and(labels(site["flags"], FLAG_LABELS))))
    if site.get("entranceForms"):
        classification.append(("Entrance forms", "; ".join(site["entranceForms"])))
    if classification:
        sections.append(("Form and condition", classification))

    landscape = []
    if site.get("topo"):
        landscape.append(("Topographic position", join_and(labels(site["topo"], TOPO_LABELS))))
    if site.get("aspect"):
        landscape.append(("Aspect", join_and(labels(site["aspect"], ASPECT_LABELS))))
    if site.get("landuse"):
        landscape.append(("Land use", join_and(labels(site["landuse"], LANDUSE_LABELS))))
    if site.get("water"):
        landscape.append(("Water source", join_and(labels(site["water"], WATER_LABELS))))
    if landscape:
        sections.append(("Landscape", landscape))

    dating = []
    periods = labels(site.get("periods"), PERIOD_LABELS)
    if periods:
        dating.append(("Dating", join_and(periods)))
    if site.get("dating"):
        dating.append(("Dating evidence", join_and(site["dating"])))
    if site.get("datingReliability"):
        dating.append(("Dating reliability", site["datingReliability"]))
    if dating:
        sections.append(("Dating", dating))

    interior = []
    if site.get("interior"):
        interior.append(("Interior surface", join_and(labels(site["interior"], INTERIOR_LABELS))))
    if site.get("interiorExcavation"):
        interior.append(("Interior excavation", join_and(labels(site["interiorExcavation"], INTERIOR_EX_LABELS))))
    if site.get("finds"):
        interior.append(("Finds", join_and(labels(site["finds"], FINDS_LABELS))))
    if site.get("investigations"):
        interior.append(("Investigations", "; ".join(site["investigations"])))
    if interior:
        sections.append(("Interior and investigation", interior))

    identifiers = []
    if site.get("scheduled"):
        identifiers.append(("Scheduled monument number", site["scheduled"]))
    if site.get("herName") or site.get("herId"):
        her = " ".join(part for part in (site.get("herName"), site.get("herId")) if part)
        if site.get("herAlt"):
            her += f" (second identifier {site['herAlt']})"
        identifiers.append(("HER", her))
    nmr_bits = []
    if site.get("nmrRecord"):
        nmr_bits.append(f"record {site['nmrRecord']}")
    if site.get("nmrMonument"):
        nmr_bits.append(f"monument {site['nmrMonument']}")
    if nmr_bits:
        identifiers.append(("National record", "; ".join(nmr_bits)))
    if site.get("wiki"):
        identifiers.append(("Wikidata", site["wiki"]))
    if identifiers:
        sections.append(("Identifiers", identifiers))
    return sections


def attribution() -> str:
    return """<footer class="site-footer"><div class="wrap"><nav class="footer-nav" aria-label="Information"><a href="/about/">About</a><a href="/privacy/">Privacy</a><a href="/cookies/">Cookies</a><a href="/terms/">Terms</a><button type="button" class="cookie-settings" data-cookie-settings>Cookie settings</button></nav><p>Lock &amp; Ralston, Atlas of Hillforts of Britain and Ireland. <a href="https://doi.org/10.5284/1118744">https://doi.org/10.5284/1118744</a>. <a href="https://hillforts.arch.ox.ac.uk">hillforts.arch.ox.ac.uk</a>. Licence <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.</p></div></footer>"""


def header(active=None) -> str:
    links = ['<a href="/#map">Map</a>']
    for name, slug in NATION_ORDER:
        current = ' aria-current="page"' if active == slug else ""
        links.append(f'<a href="/nations/{slug}/"{current}>{esc(name)}</a>')
    about_current = ' aria-current="page"' if active == "about" else ""
    links.append(f'<a href="/about/"{about_current}>About</a>')
    return f"""<a class="skip" href="#content">Skip to content</a>
<header class="site-header"><div class="wrap"><a class="brand" href="/">Hillforts Map</a><nav aria-label="Main">{''.join(links)}</nav></div></header>"""


def analytics_head() -> str:
    return f"""<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('consent', 'default', {{
  'analytics_storage': 'denied',
  'ad_storage': 'denied',
  'ad_user_data': 'denied',
  'ad_personalization': 'denied'
}});
try {{
  if (localStorage.getItem('{CONSENT_STORAGE_KEY}') === 'accepted') {{
    gtag('consent', 'update', {{'analytics_storage': 'granted'}});
  }}
}} catch (e) {{}}
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
<script>
gtag('js', new Date());
try {{
  if (localStorage.getItem('{CONSENT_STORAGE_KEY}') === 'accepted') {{
    gtag('config', '{GA_MEASUREMENT_ID}');
  }}
}} catch (e) {{}}
</script>"""


def cookie_banner() -> str:
    return f"""<div id="cookie-banner" class="cookie-banner" role="region" aria-labelledby="cookie-banner-title" aria-describedby="cookie-banner-text" hidden tabindex="-1" data-consent-key="{CONSENT_STORAGE_KEY}" data-measurement-id="{GA_MEASUREMENT_ID}">
<div class="wrap cookie-banner-inner">
<div class="cookie-banner-copy">
<p id="cookie-banner-title" class="cookie-banner-title">Cookies</p>
<p id="cookie-banner-text">Google Analytics stays off unless you accept. It tells us which pages are used. <a href="/cookies/">Cookie policy</a></p>
</div>
<div class="cookie-banner-actions">
<button type="button" class="cookie-choice" id="cookie-reject">Reject</button>
<button type="button" class="cookie-choice" id="cookie-accept">Accept</button>
</div>
</div>
</div>"""


def shell(title, description, robots, canonical, body, active=None, json_ld=None, include_map=True) -> str:
    ld = ""
    if json_ld:
        payload = json.dumps(json_ld, ensure_ascii=False).replace("<", "\\u003c")
        ld = f'<script type="application/ld+json">{payload}</script>'
    map_head = ""
    map_scripts = ""
    if include_map:
        map_head = """<link rel="stylesheet" href="/assets/vendor/leaflet.css">
<link rel="stylesheet" href="/assets/vendor/MarkerCluster.css">
<link rel="stylesheet" href="/assets/vendor/MarkerCluster.Default.css">"""
        map_scripts = """<script src="/assets/vendor/leaflet.js"></script>
<script src="/assets/vendor/leaflet.markercluster.js"></script>
<script src="/assets/directory.js"></script>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{analytics_head()}
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{esc(canonical)}">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
{map_head}
<link rel="stylesheet" href="/assets/site.css">
{ld}
</head>
<body>
{header(active)}
{cookie_banner()}
<main id="content">{body}</main>
{attribution()}
{map_scripts}
<script src="/assets/consent.js"></script>
</body>
</html>
"""


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def render_facts(site) -> str:
    blocks = []
    for heading, rows in fact_rows(site):
        body = "".join(f"<dt>{esc(label)}</dt><dd>{esc(value)}</dd>" for label, value in rows if value)
        blocks.append(f"<h3>{esc(heading)}</h3><dl class=\"facts\">{body}</dl>")
    return "".join(blocks)


def render_links(site) -> str:
    items = "".join(
        f'<li><a href="{esc(url)}" rel="noopener noreferrer">{esc(label)}</a></li>'
        for label, url in source_links(site)
    )
    return f"<h3>Sources</h3><ul class=\"links\">{items}</ul>"


def render_refs(site) -> str:
    refs = site.get("refs") or []
    if not refs:
        return ""
    items = "".join(f"<li>{esc(ref)}</li>" for ref in refs)
    return f"<h3>References</h3><ol class=\"refs\">{items}</ol>"


def list_item(site) -> str:
    type_bits = [TYPE_LABELS[code] for code in (site.get("types") or [])[:2]]
    meta = [bit for bit in [site.get("county")] if bit]
    meta.extend(labels(site.get("condition"), CONDITION_LABELS))
    meta.extend(bit[:1].upper() + bit[1:] for bit in type_bits)
    return (
        f'<li data-site data-slug="{esc(site["slug"])}" '
        f'data-types="{" ".join(site.get("types") or [])}" '
        f'data-condition="{" ".join(site.get("condition") or [])}" '
        f'data-morph="{" ".join(morph_parents(site.get("morph")))}" '
        f'data-scheduled="{"1" if site.get("scheduled") else "0"}" '
        f'data-search="{esc(search_text(site))}">'
        f'<a href="/sites/{esc(site["slug"])}/">{esc(site["name"])}</a>'
        f'<span>{esc(" · ".join(meta))}</span></li>'
    )


def site_page(site) -> str:
    indexed = bool(site.get("index"))
    robots = "index,follow" if indexed else "noindex,follow"
    crumbs = (
        f'<p class="crumbs"><a href="/">Home</a> / '
        f'<a href="/nations/{esc(site["nation"])}/">{esc(site["country"])}</a> / '
        f'<a href="/counties/{esc(site["countySlug"])}/">{esc(site["county"])}</a> / '
        f'{esc(site["name"])}</p>'
    )
    lede = ""
    description = f"Atlas of Hillforts record {site['code']}, {site['name']}, {site.get('county')}, {site.get('country')}."
    if indexed:
        paragraphs = visitor_copy(site)
        lede = '<div class="lede">' + "".join(f"<p>{esc(paragraph)}</p>" for paragraph in paragraphs) + "</div>"
        description = paragraphs[0]
        if len(description) > 180:
            description = description[:177].rstrip() + "..."
    json_ld = None
    if indexed:
        json_ld = {
            "@context": "https://schema.org",
            "@type": "Place",
            "name": site["name"],
            "url": f"{BASE}/sites/{site['slug']}/",
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": site["lat"],
                "longitude": site["lon"],
            },
            "address": {
                "@type": "PostalAddress",
                "addressRegion": site.get("county"),
                "addressCountry": "IE" if site["country"] == "Republic of Ireland" else ("IM" if site["country"] == "Isle of Man" else "GB"),
            },
        }
    body = f"""<div class="wrap">
{crumbs}
<h1>{esc(site["name"])}</h1>
<p class="meta">{esc(site.get("county") or "")}, {esc(site.get("country") or "")} · Atlas {esc(site["code"])}</p>
{lede}
<div class="layout">
<article class="panel">{render_facts(site)}{render_links(site)}{render_refs(site)}</article>
<aside class="panel">
<div id="map" class="map site-map" data-mode="site" data-lat="{site["lat"]}" data-lon="{site["lon"]}" data-name="{esc(site["name"])}" role="region" aria-label="Map of {esc(site["name"])}"></div>
</aside>
</div>
</div>"""
    title = f"{site['name']}, {site.get('county')} | Hillforts Map"
    return shell(title, description, robots, f"{BASE}/sites/{site['slug']}/", body, active=site["nation"], json_ld=json_ld)


def hub_page(title, description, canonical, active, intro, extra, country, county, items) -> str:
    results = "".join(list_item(site) for site in items)
    body = f"""<div class="wrap">
{intro}
{extra}
{FILTERS}
<p class="count" data-count></p>
<div id="map" class="map" data-mode="hub" data-scroll="1" data-country="{esc(country)}" data-county="{esc(county)}" role="region" aria-label="Map"></div>
<h2>Sites</h2>
<noscript><p class="note">The map needs JavaScript. The list below works without it.</p></noscript>
<ul class="site-list" id="results">{results}</ul>
</div>"""
    return shell(title, description, "index,follow", canonical, body, active=active)


def comma(value: int) -> str:
    return f"{value:,}"


def info_page(slug, title, description, body, active=None) -> None:
    write(
        DIST / slug / "index.html",
        shell(
            f"{title} | Hillforts Map",
            description,
            "index,follow",
            f"{BASE}/{slug}/",
            f'<div class="wrap prose">{body}</div>',
            active=active,
            include_map=False,
        ),
    )


def write_info_pages(site_count: int) -> None:
    ga_cookie = "_ga_" + GA_MEASUREMENT_ID.split("-", 1)[1]
    about = f"""<h1>About</h1>
<p>Hillforts Map is a map and directory of {comma(site_count)} hillforts across Britain and Ireland. It is built on the Atlas of Hillforts of Britain and Ireland.</p>
<p>The map clusters every fort. Zoom in and the groups separate until a single site is in view. You can also browse by nation and then by county or unitary authority: Scotland, England, Wales, the Republic of Ireland, Northern Ireland, and the Isle of Man. Lists and maps can be filtered by type of fort, condition, rampart layout, and whether a scheduled monument number is recorded. You can search by name, parish, or Atlas number.</p>
<p>Each site page sets out the key facts for that record, including where it is, the type and condition, and the identifiers and links held for it. Where a short introduction is shown, it was written for this site from those facts.</p>
<p><a href="/#map">Open the map</a></p>
<h2>Visiting responsibly</h2>
<p>Many hillforts are on private land, and many are scheduled monuments. A page on this site is not permission to visit. Check access before you set out, keep to public rights of way and other land you are allowed to use, and follow signs on the ground. Do not disturb the earthworks.</p>
<h2>Data source</h2>
<p>The records come from Lock &amp; Ralston, Atlas of Hillforts of Britain and Ireland. <a href="https://doi.org/10.5284/1118744">https://doi.org/10.5284/1118744</a>. <a href="https://hillforts.arch.ox.ac.uk">hillforts.arch.ox.ac.uk</a>. Licence <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.</p>
<p>This site is shared under the same licence. Keep that attribution if you reuse the data.</p>"""
    privacy = f"""<h1>Privacy policy</h1>
<p class="meta">Last updated {POLICY_UPDATED}</p>
<p>Hillforts Map publishes this website at <a href="{BASE}/">{BASE}/</a>. This policy explains what information is processed when you use the site. The site is operated by Hillforts Map.</p>
<h2>What this site does</h2>
<p>Hillforts Map is a static directory and map. There are no accounts, no forms, no comments, no newsletter, and no advertisements.</p>
<h2>Hosting</h2>
<p>The site is hosted on GitHub Pages. When you open a page, GitHub receives the request and keeps server logs. Those logs can include your IP address, the date and time, the page address, and basic details of your browser. GitHub describes this in the <a href="https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement">GitHub Privacy Statement</a>.</p>
<h2>Map tiles</h2>
<p>Pages with a map load tiles from OpenStreetMap (<a href="https://tile.openstreetmap.org/">tile.openstreetmap.org</a>). Your browser requests those images directly from OpenStreetMap, so OpenStreetMap receives your IP address and the tile request. The <a href="https://osmfoundation.org/wiki/Privacy_Policy">OpenStreetMap Foundation privacy policy</a> describes that processing.</p>
<h2>Analytics</h2>
<p>Hillforts Map uses Google Analytics 4, measurement ID {GA_MEASUREMENT_ID}, to see which pages are used. The tag loads with analytics storage denied. The measurement itself runs, and analytics cookies are stored, only after you accept. If you have not chosen, or if you reject, analytics storage stays denied, the measurement is not sent, and analytics cookies are not set.</p>
<p>Loading the tag contacts Google, so Google receives your IP address with that script request. After you accept, Google Analytics can store cookies and measure the visit. You can change your mind at any time with Cookie settings in the footer. Rejecting leaves analytics storage denied and clears analytics cookies already stored for this site.</p>
<p>Google's handling of this information is described in the <a href="https://policies.google.com/privacy">Google Privacy Policy</a>. The site does not show ads. Advertising storage, and the related advertising choices, stay denied.</p>
<h2>Consent record</h2>
<p>Your Accept or Reject choice is stored in this browser under the localStorage key <code>{CONSENT_STORAGE_KEY}</code>. It is not sent to a Hillforts Map server. It stays on your device until you change it or clear site data. The <a href="/cookies/">cookie policy</a> lists each cookie and this storage item, with its purpose and lifetime.</p>
<h2>Why this information is used</h2>
<p>Analytics cookies are used only with your consent, under the UK GDPR and the Privacy and Electronic Communications Regulations (PECR). The consent record is stored so the site can follow that choice. Hosting logs and map tiles are part of showing you the pages and maps. GitHub and the OpenStreetMap Foundation receive those technical requests and describe them in the policies linked above.</p>
<h2>How long it is kept</h2>
<p>The consent record remains in your browser until you change it or delete site data. Google Analytics cookies last up to 2 years and are stored only after you accept. How long Google, GitHub, and the OpenStreetMap Foundation keep information they receive is set out in their own policies. Hillforts Map does not keep a separate database of visitors.</p>
<h2>Your rights</h2>
<p>Under the UK GDPR you have:</p>
<ul>
<li>the right to be informed</li>
<li>the right of access</li>
<li>the right to rectification</li>
<li>the right to erasure</li>
<li>the right to restrict processing</li>
<li>the right to data portability</li>
<li>the right to object</li>
<li>rights related to automated decision-making and profiling</li>
</ul>
<p>Hillforts Map does not make automated decisions about you that have a legal or similarly significant effect.</p>
<p>The site does not run accounts or hold a visitor database. The information above sits in your browser, or with Google if you accept analytics, with GitHub for hosting logs, and with the OpenStreetMap Foundation for map tiles. You can reject analytics, change your choice through Cookie settings, and clear cookies and site data in your browser. The policies linked above explain how those organisations handle requests about information they hold.</p>
<p>Hillforts Map does not publish a postal address or an email address for privacy requests.</p>
<p>You have the right to complain to the Information Commissioner's Office (ICO), the UK supervisory authority for data protection: <a href="https://ico.org.uk/make-a-complaint/">https://ico.org.uk/make-a-complaint/</a>.</p>
<h2>Changes</h2>
<p>If this policy changes, the date at the top will change with it.</p>"""
    cookies = f"""<h1>Cookie policy</h1>
<p class="meta">Last updated {POLICY_UPDATED}</p>
<p>This page lists the cookies and similar storage used on Hillforts Map. The <a href="/privacy/">privacy policy</a> explains the wider picture.</p>
<h2>Your choice</h2>
<p>On a first visit, a banner asks you to accept or reject analytics cookies. Accept and Reject are stored on your device, and the banner stays closed until you open Cookie settings in the footer.</p>
<p>Analytics cookies are not set before you accept, and the measurement request is not sent until you do. If you reject, analytics storage stays denied. Any analytics cookies already stored for this site are cleared. You can change your choice at any time.</p>
<h2>Storage</h2>
<h3><code>{CONSENT_STORAGE_KEY}</code></h3>
<ul>
<li>Kind: localStorage on your device. It is not a cookie sent to a server.</li>
<li>Purpose: remembers whether you accepted or rejected analytics cookies, so the banner is not shown again and analytics stays off if you rejected.</li>
<li>Lifetime: until you change the choice or clear site data for this website.</li>
<li>Set by: Hillforts Map, when you use the banner.</li>
</ul>
<h3><code>_ga</code></h3>
<ul>
<li>Kind: cookie.</li>
<li>Purpose: used by Google Analytics 4 to distinguish visitors.</li>
<li>Lifetime: 2 years.</li>
<li>Set by: Google, and only after you accept. More detail is in the <a href="https://policies.google.com/privacy">Google Privacy Policy</a>.</li>
</ul>
<h3><code>{ga_cookie}</code></h3>
<ul>
<li>Kind: cookie.</li>
<li>Purpose: used by Google Analytics 4 to keep session state for measurement ID {GA_MEASUREMENT_ID}.</li>
<li>Lifetime: 2 years.</li>
<li>Set by: Google, and only after you accept.</li>
</ul>
<h2>Requests that are not cookies set by this site</h2>
<p>Pages with a map load tiles from OpenStreetMap. That request goes from your browser to OpenStreetMap, which receives your IP address. It is not a cookie set by Hillforts Map. See the <a href="https://osmfoundation.org/wiki/Privacy_Policy">OpenStreetMap Foundation privacy policy</a>.</p>
<p>The site is hosted on GitHub Pages. GitHub keeps server logs of page requests, as described in the <a href="https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement">GitHub Privacy Statement</a>.</p>
<p>The site does not use advertising cookies.</p>"""
    terms = f"""<h1>Terms of use</h1>
<p class="meta">Last updated {POLICY_UPDATED}</p>
<p>These terms cover your use of Hillforts Map at <a href="{BASE}/">{BASE}/</a>, published by Hillforts Map. The <a href="/privacy/">privacy policy</a> and <a href="/cookies/">cookie policy</a> sit alongside them.</p>
<h2>Disclaimer</h2>
<p>The maps, directories, and site pages are provided as-is. Hillforts Map cannot guarantee that names, locations, condition, access, or any other detail is accurate, complete, or up to date. Records can be wrong or out of date. Check an authoritative source before you rely on a page.</p>
<p>Nothing on this site grants any right of access to a hillfort, a monument, or the land it stands on. Many sites are on private land or are scheduled monuments. Any right to visit comes from the landowner and from the law, not from this website. A coordinate is a guide to the recorded location, not permission to cross land.</p>
<p>Visits are at your own risk. To the extent UK law allows, Hillforts Map is not liable for loss or damage arising from use of the site or from a visit to a place mentioned on it. Nothing in these terms limits liability that cannot be limited under UK law.</p>
<h2>Visiting</h2>
<p>Check access before you travel. Keep to public rights of way and other land you are allowed to use, follow signs, and do not disturb the earthworks.</p>
<h2>Data licence</h2>
<p>The underlying records come from Lock &amp; Ralston, Atlas of Hillforts of Britain and Ireland, <a href="https://doi.org/10.5284/1118744">https://doi.org/10.5284/1118744</a>, <a href="https://hillforts.arch.ox.ac.uk">hillforts.arch.ox.ac.uk</a>. They are used under the Creative Commons Attribution-ShareAlike 4.0 International licence (CC BY-SA 4.0): <a href="https://creativecommons.org/licenses/by-sa/4.0/">https://creativecommons.org/licenses/by-sa/4.0/</a>.</p>
<p>This site is shared under the same licence. If you share or adapt material from it that is covered by that licence, give appropriate credit, link to the licence, and distribute your adaptation under the same licence. A suitable credit line is: Lock &amp; Ralston, Atlas of Hillforts of Britain and Ireland.</p>
<p>Map tiles are loaded from OpenStreetMap. Map data is &copy; OpenStreetMap contributors.</p>
<h2>Using the website</h2>
<p>You may browse the site freely. Do not disrupt it, and do not put an unreasonable load on it or on the OpenStreetMap tile servers the maps use.</p>
<h2>Changes</h2>
<p>These terms may be updated. The date at the top is the date of the current version.</p>"""
    info_page(
        "about",
        "About",
        f"Hillforts Map is a directory and map of {comma(site_count)} hillforts across Britain and Ireland, built on the Atlas of Hillforts of Britain and Ireland.",
        about,
        active="about",
    )
    info_page(
        "privacy",
        "Privacy policy",
        "How Hillforts Map handles visitor information, including analytics, map tiles, hosting, and the consent record.",
        privacy,
    )
    info_page(
        "cookies",
        "Cookie policy",
        "Cookies and local storage used on Hillforts Map, including Google Analytics cookies and the consent record.",
        cookies,
    )
    info_page(
        "terms",
        "Terms of use",
        "Terms of use for Hillforts Map, including the disclaimer, visiting, and the CC BY-SA data licence.",
        terms,
    )


def main():
    sites = json.loads(DATA.read_text(encoding="utf-8"))
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copytree(SRC / "assets", DIST / "assets")

    by_nation = defaultdict(list)
    counties = {}
    for site in sites:
        by_nation[site["nation"]].append(site)
        bucket = counties.setdefault(site["countySlug"], {
            "slug": site["countySlug"],
            "name": site["county"],
            "country": site["country"],
            "nation": site["nation"],
            "sites": [],
        })
        bucket["sites"].append(site)

    for site in sites:
        write(DIST / "sites" / site["slug"] / "index.html", site_page(site))

    nation_cards = []
    for name, slug in NATION_ORDER:
        group = by_nation[slug]
        nation_cards.append(
            f'<li><a href="/nations/{slug}/">{esc(name)}</a><span>{comma(len(group))} sites</span></li>'
        )
        county_cards = []
        nation_counties = [county for county in counties.values() if county["nation"] == slug]
        nation_counties.sort(key=lambda county: county["name"].lower())
        for county in nation_counties:
            county_cards.append(
                f'<li><a href="/counties/{esc(county["slug"])}/">{esc(county["name"])}</a>'
                f'<span>{comma(len(county["sites"]))} sites</span></li>'
            )
        group_sorted = sorted(group, key=lambda item: item["name"].lower())
        intro = f"""<p class="crumbs"><a href="/">Home</a> / {esc(name)}</p>
<h1>Hillforts in {esc(name)}</h1>
<p class="intro">{esc(name)} has {comma(len(group))} hillforts in the Atlas of Hillforts of Britain and Ireland. Open a county or unitary authority, or filter the full national list and map.</p>"""
        extra = f"<h2>Counties and unitary authorities</h2><ul class=\"county-grid\">{''.join(county_cards)}</ul>"
        description = f"Directory of {comma(len(group))} hillforts in {name} from the Atlas of Hillforts of Britain and Ireland."
        write(
            DIST / "nations" / slug / "index.html",
            hub_page(
                f"Hillforts in {name} | Hillforts Map",
                description,
                f"{BASE}/nations/{slug}/",
                slug,
                intro,
                extra,
                name,
                "",
                group_sorted,
            ),
        )

    for county in counties.values():
        group_sorted = sorted(county["sites"], key=lambda item: item["name"].lower())
        intro = f"""<p class="crumbs"><a href="/">Home</a> / <a href="/nations/{esc(county["nation"])}/">{esc(county["country"])}</a> / {esc(county["name"])}</p>
<h1>Hillforts in {esc(county["name"])}</h1>
<p class="intro">{esc(county["name"])}, {esc(county["country"])}, has {comma(len(county["sites"]))} hillforts in the Atlas of Hillforts of Britain and Ireland.</p>"""
        description = f"Directory of {comma(len(county['sites']))} hillforts in {county['name']}, {county['country']}."
        write(
            DIST / "counties" / county["slug"] / "index.html",
            hub_page(
                f"Hillforts in {county['name']} | Hillforts Map",
                description,
                f"{BASE}/counties/{county['slug']}/",
                county["nation"],
                intro,
                "",
                county["country"],
                county["name"],
                group_sorted,
            ),
        )

    home = f"""<div class="wrap">
<h1>Hillforts of Britain and Ireland</h1>
<p class="intro">Hillforts Map is a directory of {comma(len(sites))} hillforts from the Atlas of Hillforts of Britain and Ireland. It covers Scotland, England, Wales, the Republic of Ireland, Northern Ireland, and the Isle of Man. The map clusters every record. Search here, or open a nation for its counties.</p>
<h2>Nations</h2>
<ul class="nation-grid">{''.join(nation_cards)}</ul>
<h2 id="map-heading">Map of all sites</h2>
{FILTERS}
<p class="count" data-count></p>
<div id="map" class="map" data-mode="hub" data-scroll="1" role="region" aria-label="Map of all hillforts"></div>
<h2>Matching sites</h2>
<noscript><p class="note">The master map needs JavaScript. Nation and county pages list their sites without it.</p></noscript>
<ul class="site-list" id="results" data-dynamic="1"></ul>
</div>"""
    write(
        DIST / "index.html",
        shell(
            "Hillforts Map | Britain and Ireland",
            f"A directory and clustered map of {comma(len(sites))} hillforts from the Atlas of Hillforts of Britain and Ireland.",
            "index,follow",
            f"{BASE}/",
            home,
        ),
    )

    missing = f"""<div class="wrap"><h1>Page not found</h1>
<p>That page is not on Hillforts Map.</p>
<p><a href="/">Back to the map</a></p></div>"""
    write(
        DIST / "404.html",
        shell(
            "Page not found | Hillforts Map",
            "That page is not on Hillforts Map.",
            "noindex,follow",
            f"{BASE}/404.html",
            missing,
            include_map=False,
        ),
    )

    write_info_pages(len(sites))

    map_sites = []
    for site in sites:
        map_sites.append({
            "slug": site["slug"],
            "name": site["name"],
            "lat": site["lat"],
            "lon": site["lon"],
            "country": site["country"],
            "county": site["county"],
            "types": site.get("types") or [],
            "condition": site.get("condition") or [],
            "morph": morph_parents(site.get("morph")),
            "scheduled": bool(site.get("scheduled")),
            "search": search_text(site),
        })
    (DIST / "data").mkdir(parents=True, exist_ok=True)
    (DIST / "data" / "map.json").write_text(
        json.dumps({"sites": map_sites}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    today = date.today().isoformat()
    urls = [f"{BASE}/"]
    urls.extend(f"{BASE}/{slug}/" for slug in INFO_PAGES)
    urls.extend(f"{BASE}/nations/{slug}/" for _name, slug in NATION_ORDER)
    urls.extend(f"{BASE}/counties/{county['slug']}/" for county in sorted(counties.values(), key=lambda item: item["slug"]))
    urls.extend(f"{BASE}/sites/{site['slug']}/" for site in sites if site.get("index"))
    body = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        body.append(f"<url><loc>{esc(url)}</loc><lastmod>{today}</lastmod></url>")
    body.append("</urlset>")
    write(DIST / "sitemap.xml", "\n".join(body) + "\n")
    write(DIST / "robots.txt", "User-agent: *\nAllow: /\n\nSitemap: https://hillfortsmap.co.uk/sitemap.xml\n")
    write(DIST / "CNAME", "hillfortsmap.co.uk\n")
    write(DIST / ".nojekyll", "")
    indexed = sum(1 for site in sites if site.get("index"))
    print(f"Built {len(sites)} site pages, {len(counties)} counties, {indexed} indexed sites")
    print(f"Sitemap URLs: {len(urls)}")


if __name__ == "__main__":
    main()
