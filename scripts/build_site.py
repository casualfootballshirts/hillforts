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
    return """<footer class="site-footer"><div class="wrap"><p>Lock &amp; Ralston, Atlas of Hillforts of Britain and Ireland. <a href="https://doi.org/10.5284/1118744">https://doi.org/10.5284/1118744</a>. <a href="https://hillforts.arch.ox.ac.uk">hillforts.arch.ox.ac.uk</a>. Licence <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.</p></div></footer>"""


def header(active=None) -> str:
    links = ['<a href="/#map">Map</a>']
    for name, slug in NATION_ORDER:
        current = ' aria-current="page"' if active == slug else ""
        links.append(f'<a href="/nations/{slug}/"{current}>{esc(name)}</a>')
    return f"""<a class="skip" href="#content">Skip to content</a>
<header class="site-header"><div class="wrap"><a class="brand" href="/">Hillforts Map</a><nav>{''.join(links)}</nav></div></header>"""


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
<main id="content">{body}</main>
{attribution()}
{map_scripts}
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
