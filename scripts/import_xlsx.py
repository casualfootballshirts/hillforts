#!/usr/bin/env python3
"""Convert the Atlas of Hillforts workbook into compact structured JSON.

Only an allowlist of identifiers, measurements, and yes/no flags is copied.
Narrative comment and summary columns are never read into the output.

Optional Wikipedia sitelinks are looked up from Wikidata (URLs only) and used
later to choose which site pages are indexed. Re-run:

    python scripts/import_xlsx.py --main /path/to/main11.xlsx
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
TARGET_INDEX = 300

# Well-known named sites. Used only to rank which pages get an original
# visitor introduction. These numbers are Atlas record ids, not page copy.
FAMOUS_IDS = {
    5, 49, 50, 75, 146, 387, 394, 405, 406, 468, 599, 601, 609, 614, 617,
    624, 654, 662, 723, 733, 801, 803, 1155, 1165, 1474, 1685, 1729, 1756,
    1888, 2136, 2466, 2554, 2682, 2938, 2961, 2968, 3085, 3087, 3327, 3399,
    3408, 3580, 3595, 3598, 3748, 3749, 3828, 3948, 4069,
    3219,  # South Barrule, Isle of Man
    3220,  # Cronk Sumark, Isle of Man
}

NATION_SLUGS = {
    "Scotland": "scotland",
    "England": "england",
    "Wales": "wales",
    "Republic of Ireland": "republic-of-ireland",
    "Northern Ireland": "northern-ireland",
    "Isle of Man": "isle-of-man",
}

TYPE_FIELDS = [
    ("Hillfort Type: Contour Fort", "contour"),
    ("Hillfort Type: Partial Contour Fort", "partial-contour"),
    ("Hillfort Type: Promontory Fort", "promontory"),
    ("Hillfort Type: Hillslope Fort", "hillslope"),
    ("Hillfort Type: Level Terrain Fort", "level"),
    ("Hillfort Type: Marsh Fort", "marsh"),
    ("Hillfort Type: Multiple Enclosure", "multiple"),
]

CONDITION_FIELDS = [
    ("Monument Condition: Extant", "extant"),
    ("Monument Condition: Cropmark", "cropmark"),
    ("Monument Condition: Likely Destroyed", "destroyed"),
]

MORPH_FIELDS = [
    ("Current Morphology: Univallate", "univallate"),
    ("Current Morphology: Partial Univallate", "partial-univallate"),
    ("Current Morphology: Bivallate", "bivallate"),
    ("Current Morphology: Partial Bivallate", "partial-bivallate"),
    ("Current Morphology: Multivallate", "multivallate"),
    ("Current Morphology: Partial Multivallate", "partial-multivallate"),
    ("Current Morphology: Unknown", "unknown"),
]

PERIOD_FIELDS = [
    ("Dating Evidence: Pre 1200BC", "pre-1200"),
    ("Dating Evidence: 1200BC - 800BC", "1200-800"),
    ("Dating Evidence: 800BC - 400BC", "800-400"),
    ("Dating Evidence: 400BC - AD50", "400-ad50"),
    ("Dating Evidence: AD50 - AD400", "ad50-400"),
    ("Dating Evidence: AD400 - AD800", "ad400-800"),
    ("Dating Evidence: Post AD800", "post-800"),
    ("Dating Evidence: Unknown", "unknown"),
]

TOPO_FIELDS = [
    ("Topographic Position: Hilltop", "hilltop"),
    ("Topographic Position: Coastal Promontory", "coastal-promontory"),
    ("Topographic Position: Inland Promontory", "inland-promontory"),
    ("Topographic Position: Valley Bottom", "valley-bottom"),
    ("Topographic Position: Knoll/Hillock/Outcrop", "knoll"),
    ("Topographic Position: Ridge", "ridge"),
    ("Topographic Position: Cliff/Plateau-edge/Scarp", "scarp"),
    ("Topographic Position: Hillslope", "hillslope"),
    ("Topographic Position: Lowland", "lowland"),
    ("Topographic Position: Spur", "spur"),
]

ASPECT_FIELDS = [
    ("Aspect: North", "north"),
    ("Aspect: Northeast", "northeast"),
    ("Aspect: East", "east"),
    ("Aspect: Southeast", "southeast"),
    ("Aspect: South", "south"),
    ("Aspect: Southwest", "southwest"),
    ("Aspect: West", "west"),
    ("Aspect: Northwest", "northwest"),
    ("Aspect: Level", "level"),
]

LANDUSE_FIELDS = [
    ("Land Use: Woodland", "woodland"),
    ("Land Use: Commercial Forestry Plantation", "forestry"),
    ("Land Use: Parkland", "parkland"),
    ("Land Use: Pasture (Grazing)", "pasture"),
    ("Land Use: Arable", "arable"),
    ("Land Use: Scrub/Bracken", "scrub"),
    ("Land Use: Bare Outcrop", "outcrop"),
    ("Land Use: Heather/Moorland", "moorland"),
    ("Land Use: Heath", "heath"),
    ("Land Use: Built-up", "built-up"),
    ("Land Use: Coastal Grassland", "coastal-grassland"),
]

SURFACE_FIELDS = [
    ("Enclosing Surface: Earthen Bank", "earthen-bank"),
    ("Enclosing Surface: Stone Wall", "stone-wall"),
    ("Enclosing Surface: Rubble", "rubble"),
    ("Enclosing Surface: Wall-walk", "wall-walk"),
    ("Enclosing Surface: Evidence of Timber", "timber"),
    ("Enclosing Surface: Vitrification", "vitrification"),
    ("Enclosing Surface: Other Burning", "burning"),
    ("Enclosing Surface: Palisade", "palisade"),
    ("Enclosing Surface: Counter Scarp Bank", "counterscarp"),
    ("Enclosing Surface: Berm", "berm"),
    ("Enclosing Surface: Unfinished", "unfinished"),
]

EXCAVATED_FIELDS = [
    ("Enclosing Excavated: Earthen Bank", "earthen-bank"),
    ("Enclosing Excavated: Stone Wall", "stone-wall"),
    ("Enclosing Excavated: Murus Duplex", "murus-duplex"),
    ("Enclosing Excavated: Timber-framed", "timber-framed"),
    ("Enclosing Excavated: Timber-laced", "timber-laced"),
    ("Enclosing Excavated: Vitrification", "vitrification"),
    ("Enclosing Excavated: Other Burning", "burning"),
    ("Enclosing Excavated: Palisade", "palisade"),
    ("Enclosing Excavated: Counter Scarp Bank", "counterscarp"),
    ("Enclosing Excavated: Berm", "berm"),
    ("Enclosing Excavated: Unfinished", "unfinished"),
]

INTERIOR_FIELDS = [
    ("Interior Surface: Round Stone Structures", "round-stone"),
    ("Interior Surface: Rectangular Stone Structures", "rectangular-stone"),
    ("Interior Surface: Curvilinear Platforms", "platforms"),
    ("Interior Surface: Other Roundhouse Evidence", "roundhouses"),
    ("Interior Surface: Pits", "pits"),
    ("Interior Surface: Quarry Hollows", "quarry-hollows"),
]

INTERIOR_EX_FIELDS = [
    ("Interior Excavation: Pits", "pits"),
    ("Interior Excavation: Postholes", "postholes"),
    ("Interior Excavation: Roundhouses", "roundhouses"),
    ("Interior Excavation: Rectangular", "rectangular"),
    ("Interior Excavation: Roads/Tracks", "roads"),
    ("Interior Excavation: Quarry Hollows", "quarry-hollows"),
]

FINDS_FIELDS = [
    ("Finds: Pottery", "pottery"),
    ("Finds: Metal", "metal"),
    ("Finds: Metalworking", "metalworking"),
    ("Finds: Human Bones", "human-bones"),
    ("Finds: Animal Bones", "animal-bones"),
    ("Finds: Lithics", "lithics"),
    ("Finds: Evironmental", "environmental"),
]

WATER_FIELDS = [
    ("Water Source: Spring", "spring"),
    ("Water Source: Stream", "stream"),
    ("Water Source: Pool", "pool"),
    ("Water Source: Flush", "flush"),
    ("Water Source: Well/Cistern", "well"),
]

FLAG_FIELDS = [
    ("Guard Chambers", "guard-chambers"),
    ("Chevaux de Frise", "chevaux-de-frise"),
    ("Annex", "annex"),
    ("Multi-period Enclosure System", "multi-period"),
    ("Ditches", "ditches"),
    ("Gang Working", "gang-working"),
]

# Distinctive narrative snippets. The importer fails if any survive into JSON.
BANNED_SNIPPETS = [
    "located on Aconbury HIll",
    "Kenyon suggested that occupation",
    "Main ditch gone on N and W sides",
    "Visitor erosion of paths",
    "following the natural contours and which also appears",
    "Little information about interior was gleaned",
    "Two original and four modern gaps",
    "Univallate hillfort with complete circuit, but the ditch is only visible",
]


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "site"


def is_yes(value) -> bool:
    if value is True:
        return True
    if value is None:
        return False
    return str(value).strip().lower() == "yes"


def ident(value):
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = str(int(value))
    elif isinstance(value, int):
        value = str(value)
    else:
        value = str(value).strip()
    if not value or value.lower() in {"none", "n/a", "no record found", "null"}:
        return None
    return value


def number(value):
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed.is_integer():
        return int(parsed)
    return round(parsed, 3)


def positive_area(value):
    parsed = number(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def flags(row, columns):
    found = []
    for header, code in columns:
        if is_yes(row.get(header)):
            found.append(code)
    return found


def split_controlled(value):
    if not value:
        return []
    parts = re.split(r"\s*;\s*", str(value).strip())
    seen = []
    for part in parts:
        part = " ".join(part.split())
        if part and part not in seen and part.lower() != "none":
            seen.append(part)
    return seen


def clean_refs(value):
    if not value:
        return []
    text = str(value).replace("_x000D_", "\n").replace("\r", "\n")
    refs = []
    for part in re.split(r"\n+", text):
        part = " ".join(part.split())
        if part:
            refs.append(part)
    return refs


def atlas_url(row, code):
    raw = ident(row.get("Record URL"))
    if not raw:
        raw = f"https://hillforts.arch.ox.ac.uk/records/{code}.html"
    if raw.startswith("http://"):
        raw = "https://" + raw[len("http://") :]
    return raw


def wikidata_id(value):
    text = ident(value)
    if not text:
        return None
    match = re.search(r"(Q\d+)\s*$", text)
    return match.group(1) if match else None


def fetch_wikipedia(qids):
    """Return {qid: article URL}, preferring English then Celtic languages."""
    found = {}
    preference = {"en": 0, "cy": 1, "gd": 2, "ga": 3, "sco": 4}
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "hillfortsmap-build/1.0 (https://hillfortsmap.co.uk; directory)",
    }
    endpoint = "https://query.wikidata.org/sparql"
    for start in range(0, len(qids), 200):
        chunk = qids[start : start + 200]
        values = " ".join(f"wd:{qid}" for qid in chunk)
        query = f"""
        SELECT ?item ?article ?lang WHERE {{
          VALUES ?item {{ {values} }}
          ?article schema:about ?item ;
                   schema:isPartOf ?site ;
                   schema:inLanguage ?lang .
          ?site wikibase:wikiGroup "wikipedia" .
        }}
        """
        data = urllib.parse.urlencode({"query": query}).encode()
        request = urllib.request.Request(endpoint, data=data, headers=headers)
        payload = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    payload = json.load(response)
                break
            except urllib.error.HTTPError as error:
                if error.code not in {429, 502, 503, 504} or attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        if payload is None:
            raise RuntimeError("Wikidata query failed")
        for binding in payload["results"]["bindings"]:
            qid = binding["item"]["value"].rsplit("/", 1)[-1]
            lang = binding["lang"]["value"]
            url = binding["article"]["value"]
            rank = preference.get(lang, 9)
            previous = found.get(qid)
            if previous is None or rank < previous[0]:
                found[qid] = (rank, url)
        time.sleep(0.6)
    return {qid: url for qid, (_rank, url) in found.items()}


def substance_score(site):
    score = 0
    condition = set(site.get("condition") or [])
    extant = "extant" in condition
    destroyed = "destroyed" in condition
    cropmark = "cropmark" in condition
    if extant and not destroyed:
        score += 80
    elif extant:
        score += 45
    elif cropmark and not destroyed:
        score += 15
    if site.get("scheduled"):
        score += 25
    if site.get("alt"):
        score += 5
    periods = [item for item in site.get("periods") or [] if item != "unknown"]
    if periods:
        score += 10
    if site.get("dating"):
        score += 5
    area = site.get("enclosed") or 0
    if area >= 1:
        score += 4
    if area >= 5:
        score += 6
    if area >= 15:
        score += 8
    if site.get("wikipedia"):
        score += 70
    if site["id"] in FAMOUS_IDS:
        score += 60
    return score


def choose_index(sites):
    """Pick about 300 pages for the sitemap.

    Wikipedia sitelinks, scheduled status, extant condition, size, and a
    short list of well-known names all add weight. Well-known names stay in
    even when that pushes the set to the cap.
    """
    ranked = sorted(
        sites,
        key=lambda site: (
            -substance_score(site),
            -(site.get("enclosed") or 0),
            site["id"],
        ),
    )
    protected = {site["id"] for site in sites if site["id"] in FAMOUS_IDS}
    chosen = set(protected)
    for site in ranked:
        if len(chosen) >= TARGET_INDEX:
            break
        chosen.add(site["id"])

    # Keep a few extant records from every nation inside the indexed set.
    by_nation = defaultdict(list)
    for site in ranked:
        if "extant" in (site.get("condition") or []):
            by_nation[site["nation"]].append(site)
    chosen_by_nation = defaultdict(int)
    for site in sites:
        if site["id"] in chosen:
            chosen_by_nation[site["nation"]] += 1
    for nation, candidates in by_nation.items():
        while chosen_by_nation[nation] < 3 and candidates:
            candidate = candidates.pop(0)
            if candidate["id"] in chosen:
                continue
            removable = [
                site
                for site in ranked
                if site["id"] in chosen
                and site["id"] not in protected
                and chosen_by_nation[site["nation"]] > 3
            ]
            if not removable:
                break
            drop = removable[-1]
            chosen.remove(drop["id"])
            chosen_by_nation[drop["nation"]] -= 1
            chosen.add(candidate["id"])
            chosen_by_nation[nation] += 1

    for site in sites:
        site["index"] = site["id"] in chosen


def row_to_site(row, wikipedia):
    site_name = ident(row.get("Site Name")) or ""
    code = site_name.split()[0] if site_name else ""
    if not re.fullmatch(r"[A-Z]{2,3}\d+", code or ""):
        country_code = ident(row.get("Country Code")) or "XX"
        code = f"{country_code}{int(row['Atlas Number']):04d}"
    name = ident(row.get("Name")) or code
    alts = split_controlled(row.get("Alternative Name(s)"))
    # Alternative names are sometimes separated with semicolons already handled.
    # A few use "A; B" which split_controlled covers.
    country = ident(row.get("Country"))
    county = ident(row.get("Current County or Unitary Authority"))
    qid = wikidata_id(row.get("Wikidata URL"))
    areas = []
    for key in (
        "Enclosed Area 1 (ha)",
        "Enclosed Area 2 (ha)",
        "Enclosed Area 3 (ha)",
        "Enclosed Area 4 (ha)",
    ):
        area = positive_area(row.get(key))
        if area is not None:
            areas.append(area)
    quadrants = {}
    for label, key in (
        ("ne", "Number of Ramparts NE Quadrant"),
        ("se", "Number of Ramparts SE Quadrant"),
        ("sw", "Number of Ramparts SW Quadrant"),
        ("nw", "Number of Ramparts NW Quadrant"),
    ):
        value = number(row.get(key))
        if value is not None:
            quadrants[label] = value
    site = {
        "id": int(row["Atlas Number"]),
        "code": code,
        "name": name,
        "country": country,
        "nation": NATION_SLUGS.get(country, slugify(country or "unknown")),
        "county": county,
        "lat": round(float(row["Latitude"]), 6),
        "lon": round(float(row["Longitude"]), 6),
        "atlas": atlas_url(row, code),
    }
    if alts:
        site["alt"] = alts
    historic = ident(row.get("Historic County"))
    if historic:
        site["historic"] = historic
    parish = ident(row.get("Current Parish/Community/Council/Townland"))
    if parish:
        site["parish"] = parish
    ngr = ident(row.get("NGR"))
    if ngr:
        site["ngr"] = ngr
    altitude = number(row.get("Altitude (m)"))
    if altitude is not None:
        site["altitude"] = altitude
    types = flags(row, TYPE_FIELDS)
    if types:
        site["types"] = types
    condition = flags(row, CONDITION_FIELDS)
    if condition:
        site["condition"] = condition
    morph = flags(row, MORPH_FIELDS)
    if morph:
        site["morph"] = morph
    scheduled = ident(row.get("Scheduled Monument Number"))
    if scheduled:
        site["scheduled"] = scheduled
    her_name = ident(row.get("HER"))
    if her_name:
        site["herName"] = her_name
    her_id = ident(row.get("HER Primary Record Number"))
    if her_id:
        site["herId"] = her_id
    her_alt = ident(row.get("HER Second Identifier"))
    if her_alt:
        site["herAlt"] = her_alt
    nmr_record = ident(row.get("NMR Record Number"))
    if nmr_record:
        site["nmrRecord"] = nmr_record
    nmr_monument = ident(row.get("NMR Monument Number"))
    if nmr_monument:
        site["nmrMonument"] = nmr_monument
    nmr_url = ident(row.get("NMR URL"))
    if nmr_url:
        site["nmrUrl"] = nmr_url
    if qid:
        site["wiki"] = qid
        if qid in wikipedia:
            site["wikipedia"] = wikipedia[qid]
    enclosed = positive_area(row.get("Total Enclosed Area (ha)"))
    if enclosed is not None:
        site["enclosed"] = enclosed
    elif areas:
        site["enclosed"] = areas[0]
    if len(areas) > 1:
        site["areas"] = areas
    footprint = positive_area(row.get("Total Footprint Area (ha)"))
    if footprint is not None:
        site["footprint"] = footprint
    ramparts = number(row.get("Number of Ramparts"))
    if ramparts is not None:
        site["ramparts"] = ramparts
    if quadrants:
        site["quadrants"] = quadrants
    ditch_count = number(row.get("Number of Ditches"))
    if ditch_count is not None:
        site["ditchCount"] = ditch_count
    entrances = number(row.get("Number of Possible Original Entrances"))
    if entrances is not None:
        site["entrances"] = entrances
    breaks = number(row.get("Total Number of Breaks Through Ramparts"))
    if breaks is not None:
        site["breaks"] = breaks
    if row.get("Ramparts Form a Complete Circuit") not in (None, ""):
        site["circuit"] = is_yes(row.get("Ramparts Form a Complete Circuit"))
    periods = flags(row, PERIOD_FIELDS)
    if periods:
        site["periods"] = periods
    dating = split_controlled(row.get("Dating Evidence"))
    if dating:
        site["dating"] = dating
    reliability = ident(row.get("Dating Evidence: Reliability"))
    if reliability:
        site["datingReliability"] = reliability
    topo = flags(row, TOPO_FIELDS)
    if topo:
        site["topo"] = topo
    aspect = flags(row, ASPECT_FIELDS)
    if aspect:
        site["aspect"] = aspect
    landuse = flags(row, LANDUSE_FIELDS)
    if landuse:
        site["landuse"] = landuse
    surface = flags(row, SURFACE_FIELDS)
    if surface:
        site["surface"] = surface
    excavated = flags(row, EXCAVATED_FIELDS)
    if excavated:
        site["excavated"] = excavated
    interior = flags(row, INTERIOR_FIELDS)
    if interior:
        site["interior"] = interior
    interior_ex = flags(row, INTERIOR_EX_FIELDS)
    if interior_ex:
        site["interiorExcavation"] = interior_ex
    finds = flags(row, FINDS_FIELDS)
    if finds:
        site["finds"] = finds
    water = flags(row, WATER_FIELDS)
    if water:
        site["water"] = water
    extra = flags(row, FLAG_FIELDS)
    if extra:
        site["flags"] = extra
    forms = split_controlled(row.get("Entrances"))
    if forms:
        site["entranceForms"] = forms
    investigations = split_controlled(row.get("Investigations"))
    if investigations:
        site["investigations"] = investigations
    second_county = ident(row.get("Second Current County or Unitary Authority"))
    if second_county:
        site["secondCounty"] = second_county
    refs = clean_refs(row.get("References"))
    if refs:
        site["refs"] = refs
    site["slug"] = slugify(f"{code}-{name}")
    return site


def assign_slugs(sites):
    used = set()
    for site in sites:
        slug = site["slug"]
        if slug in used:
            slug = f"{slug}-{site['id']}"
            site["slug"] = slug
        used.add(slug)
    county_owners = defaultdict(set)
    for site in sites:
        county_owners[slugify(site["county"] or "unknown")].add(site["nation"])
    for site in sites:
        base = slugify(site["county"] or "unknown")
        if len(county_owners[base]) > 1:
            site["countySlug"] = f"{site['nation']}-{base}"
        else:
            site["countySlug"] = base


def load_rows(path):
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    header = list(next(rows))
    index = {name: position for position, name in enumerate(header)}
    records = []
    for raw in rows:
        if raw[index["Atlas Number"]] is None:
            continue
        records.append({name: raw[position] for name, position in index.items()})
    workbook.close()
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", required=True, type=Path, help="Path to main11.xlsx")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "sites.json")
    parser.add_argument(
        "--skip-wikidata",
        action="store_true",
        help="Do not look up Wikipedia sitelinks (ranking uses substance and known names only).",
    )
    parser.add_argument(
        "--wikipedia-cache",
        type=Path,
        default=ROOT / "data" / "wikipedia.json",
        help="Cache of Wikidata QID to Wikipedia article URL.",
    )
    args = parser.parse_args()

    rows = load_rows(args.main)
    qids = []
    for row in rows:
        qid = wikidata_id(row.get("Wikidata URL"))
        if qid:
            qids.append(qid)
    wikipedia = {}
    if args.wikipedia_cache.exists() and args.skip_wikidata:
        wikipedia = json.loads(args.wikipedia_cache.read_text(encoding="utf-8"))
    elif not args.skip_wikidata:
        print(f"Looking up Wikipedia sitelinks for {len(qids)} Wikidata items...")
        wikipedia = fetch_wikipedia(qids)
        args.wikipedia_cache.parent.mkdir(parents=True, exist_ok=True)
        args.wikipedia_cache.write_text(
            json.dumps(wikipedia, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"Wikipedia articles: {len(wikipedia)}")

    sites = [row_to_site(row, wikipedia) for row in rows]
    assign_slugs(sites)
    choose_index(sites)
    sites.sort(key=lambda site: site["id"])

    blob = json.dumps(sites, ensure_ascii=False, separators=(",", ":"))
    for snippet in BANNED_SNIPPETS:
        if snippet in blob:
            raise SystemExit(f"Banned narrative snippet survived import: {snippet}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(blob, encoding="utf-8")

    indexed = [site for site in sites if site["index"]]
    print(f"Wrote {len(sites)} sites to {args.out} ({len(blob)} bytes)")
    print(f"Indexed {len(indexed)}")
    counts = defaultdict(int)
    for site in indexed:
        counts[site["country"]] += 1
    for country, count in sorted(counts.items(), key=lambda item: -item[1]):
        print(f"  {count:4d}  {country}")
    wiki_indexed = sum(1 for site in indexed if site.get("wikipedia"))
    print(f"Indexed with a Wikipedia article: {wiki_indexed}")
    missing_famous = sorted(FAMOUS_IDS - {site["id"] for site in indexed})
    if missing_famous:
        print("Famous ids not indexed:", missing_famous)


if __name__ == "__main__":
    main()
