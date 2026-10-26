"""Visitor introductions for county and nation hubs, from structured Atlas fields.

Narrative and *Comments columns are not in the site data and are not used here.
Public pages never describe a record as indexed, and an introduction mentions
the Atlas at most once.
"""

from __future__ import annotations

import html
import re
import zlib
from collections import Counter
from statistics import median

FULL_INDEXED_MIN = 3

COUNTRY_CODE = {
    "England": "GB",
    "Scotland": "GB",
    "Wales": "GB",
    "Northern Ireland": "GB",
    "Republic of Ireland": "IE",
    "Isle of Man": "IM",
}

BRITAIN = {"England", "Scotland", "Wales"}


def word_limits(n: int, kind: str) -> tuple[int, int]:
    if kind == "nation":
        return (150, 220)
    if n <= 1:
        return (18, 70)
    if n < 12:
        return (40, 80)
    return (90, 150)


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def crc(key, salt) -> int:
    return zlib.crc32(f"{key}|{salt}".encode("utf-8")) & 0xFFFFFFFF


def pick(key, salt, options):
    options = [option for option in options if option]
    if not options:
        return None
    return options[crc(key, salt) % len(options)]


def comma(value: int) -> str:
    return f"{value:,}"


def format_number(value) -> str:
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def join_and(items) -> str:
    items = [item for item in items if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def word_count(text: str) -> int:
    plain = re.sub(r"<[^>]+>", " ", text or "")
    plain = html.unescape(plain)
    return len(plain.split())


def nforts(n: int) -> str:
    if n == 1:
        return "one hillfort"
    return f"{comma(n)} hillforts"


def _tables():
    import build_site as sitegen

    return sitegen


def labels(codes, table):
    return [table[code] for code in codes or [] if code in table]


def in_phrase(name: str) -> str:
    if name == "Isle of Man":
        return "on the Isle of Man"
    if name == "Republic of Ireland":
        return "in the Republic of Ireland"
    return f"in {name}"


def where_clause(kind: str, name: str, country: str) -> str:
    if kind == "nation":
        return in_phrase(name)
    if country == "Republic of Ireland":
        return f"in {name} in the Republic of Ireland"
    if country == "Isle of Man":
        return f"in {name} on the Isle of Man"
    return f"in {name}, {country}"


def where_plain(kind: str, name: str, country: str) -> str:
    if kind == "nation":
        if name == "Isle of Man":
            return "the Isle of Man"
        if name == "Republic of Ireland":
            return "the Republic of Ireland"
        return name
    if country == "Republic of Ireland":
        return f"{name}, Republic of Ireland"
    return f"{name}, {country}"


def place_name(kind: str, name: str) -> str:
    if kind == "nation" and name == "Isle of Man":
        return "The Isle of Man"
    if kind == "nation" and name == "Republic of Ireland":
        return "The Republic of Ireland"
    return name


def heading(kind: str, name: str) -> str:
    if kind == "nation" and name == "Isle of Man":
        return "Hillforts on the Isle of Man"
    if kind == "nation" and name == "Republic of Ireland":
        return "Hillforts in the Republic of Ireland"
    return f"Hillforts in {name}"


def best_heading(name: str) -> str:
    if name == "Isle of Man":
        return "Best hillforts to visit on the Isle of Man"
    if name == "Republic of Ireland":
        return "Best hillforts to visit in the Republic of Ireland"
    return f"Best hillforts to visit in {name}"


def roman_framing(kind: str, name: str, country: str) -> bool:
    if kind == "nation":
        return name in BRITAIN
    return country in BRITAIN


def distinctive_name(site, group) -> str:
    same = [other for other in group if other["name"] == site["name"]]
    if len(same) == 1:
        return site["name"]
    parish = site.get("parish")
    if parish:
        return f"{site['name']} ({parish})"
    return site["name"]


def ambiguous_label(site, group) -> bool:
    same = [
        other for other in group
        if other["name"] == site["name"] and (other.get("parish") or "") == (site.get("parish") or "")
    ]
    return len(same) > 1


def parent_morph(code: str):
    if "multivallate" in code:
        return "multivallate"
    if "bivallate" in code:
        return "bivallate"
    if "univallate" in code:
        return "univallate"
    return None


def period_labels(site, period_labels_table) -> list[str]:
    found = []
    for code in site.get("periods") or []:
        if code == "unknown" or code not in period_labels_table:
            continue
        found.append(period_labels_table[code])
    return found


def count_sites(sites, pred) -> int:
    return sum(1 for site in sites if pred(site))


def visible_earthworks(site) -> bool:
    condition = set(site.get("condition") or [])
    return "extant" in condition and "destroyed" not in condition


def poor_survival(site) -> bool:
    condition = set(site.get("condition") or [])
    return "destroyed" in condition or "cropmark" in condition


def area_phrase(value) -> str:
    if value < 0.95:
        return "under a hectare"
    if value >= 10 or abs(value - round(value)) < 0.05:
        return f"{int(round(value))} hectares"
    return f"{value:.1f} hectares"


def hectare_compound(value):
    if not isinstance(value, (int, float)) or value < 0.95:
        return None
    nearest = int(value + 0.5)
    if abs(value - nearest) < 0.05:
        return f"{nearest}-hectare"
    return f"{value:.1f}-hectare"




def indefinite(phrase: str) -> str:
    token = phrase.lower()
    if re.match(r"(8|11|18)(\D|$)", token) or re.match(r"8\d", token):
        return "an"
    if token[:1] in "aeiou" and not token.startswith(("uni", "one", "eu", "use")):
        return "an"
    return "a"


def with_article(phrase: str) -> str:
    return f"{indefinite(phrase)} {phrase}"


def area_words(value) -> str:
    if value < 0.95:
        return "under a hectare"
    nearest = int(value + 0.5)
    if abs(value - nearest) < 0.05:
        return "1 hectare" if nearest == 1 else f"{nearest} hectares"
    if value >= 20:
        return f"about {nearest} hectares"
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{text} hectares"


def condition_note(site) -> str:
    condition = set(site.get("condition") or [])
    extant = "extant" in condition
    if "destroyed" in condition or ("cropmark" in condition and not extant):
        return "poor"
    if extant and "cropmark" not in condition:
        return "visible"
    return ""


def type_plain(site, full=False) -> str:
    types = set(site.get("types") or [])
    topo = set(site.get("topo") or [])
    if "promontory" in types:
        if full:
            return "fort on a headland or spur, cut off by banks"
        if "coastal-promontory" in topo:
            return "fort on a coastal headland"
        return "fort on a headland or spur"
    if "contour" in types:
        if full:
            return "fort that follows the contours of a hilltop"
        return "hilltop fort"
    if "partial-contour" in types:
        if full:
            return "fort that follows part of a hilltop contour"
        return "fort on part of a hilltop"
    if "hillslope" in types:
        return "fort set on a slope"
    if "level" in types:
        return "enclosure on level ground"
    if "marsh" in types:
        return "fort in marshy ground"
    if "multiple" in types:
        return "site with more than one enclosure"
    return "hillfort"


def type_family(site) -> str:
    types = set(site.get("types") or [])
    topo = set(site.get("topo") or [])
    if "promontory" in types or "coastal-promontory" in topo:
        if "coastal-promontory" in topo:
            return "coast"
        return "promontory"
    if "contour" in types or "partial-contour" in types or "hilltop" in topo:
        return "hill"
    if "level" in types or "marsh" in types or "lowland" in topo:
        return "low"
    if "hillslope" in types:
        return "slope"
    return "other"


def rampart_with(site) -> str:
    parents = []
    for code in site.get("morph") or []:
        parent = parent_morph(str(code))
        if parent and parent not in parents:
            parents.append(parent)
    if parents == ["univallate"]:
        return "with a single rampart"
    if parents == ["bivallate"]:
        return "with two lines of rampart"
    if parents == ["multivallate"]:
        return "with several lines of rampart"
    return ""


def setting_clause(site, kind: str) -> str:
    topo = set(site.get("topo") or [])
    if "ridge" in topo and "ridge" not in kind:
        return "set on a ridge"
    if "coastal-promontory" in topo and "coast" not in kind and "headland" not in kind:
        return "on a coastal headland"
    if "spur" in topo and "spur" not in kind and "slope" not in kind and "headland" not in kind:
        return "set on a spur"
    if "knoll" in topo and "knoll" not in kind:
        return "on a knoll"
    if "valley-bottom" in topo and "valley" not in kind:
        return "in a valley"
    if "lowland" in topo and "level" not in kind and "low" not in kind:
        return "on low ground"
    return ""


def kind_with_area(kind: str, enclosed) -> str:
    area = area_words(enclosed)
    if kind.startswith("hilltop fort"):
        return f"hilltop fort of {area}{kind[len('hilltop fort'):]}"
    if kind.startswith("fort "):
        return f"fort of {area} {kind[5:]}"
    if kind.startswith("enclosure"):
        return f"enclosure of {area}{kind[len('enclosure'):]}"
    if kind.startswith("site "):
        return f"site of {area} {kind[5:]}"
    return f"{kind} of {area}"


def portrait_clause(site, full=False) -> str:
    kind = type_plain(site, full=full)
    enclosed = site.get("enclosed") if isinstance(site.get("enclosed"), (int, float)) else None
    rampart = rampart_with(site)
    setting = setting_clause(site, kind)
    if enclosed is None:
        core = kind
    elif enclosed < 0.95:
        if "," in kind:
            head, rest = kind.split(",", 1)
            core = f"small {head} covering under a hectare,{rest}"
        else:
            core = f"small {kind} covering under a hectare"
    elif enclosed >= 20 or (enclosed >= 10 and abs(enclosed - int(enclosed + 0.5)) < 0.05):
        core = kind_with_area(kind, enclosed)
    else:
        core = f"{hectare_compound(enclosed)} {kind}"
    phrase = core
    if rampart:
        phrase += f", {rampart}" if ("," in core or " of " in core) else f" {rampart}"
    if setting:
        phrase += f", {setting}"
    return with_article(phrase)


def fort_link(site, group) -> str:
    return f'<a href="/sites/{esc(site["slug"])}/">{esc(distinctive_name(site, group))}</a>'


def display_link(profile, site) -> str:
    link = fort_link(site, profile["sites"])
    if profile["kind"] == "nation":
        return f"{link} in {esc(site.get('county') or '')}"
    return link


def capitalise(text: str) -> str:
    if not text or text.startswith("<"):
        return text
    return text[0].upper() + text[1:]


def proportion(share: float) -> str:
    if share >= 0.85:
        return "almost all"
    if share >= 0.55:
        return "most"
    if share >= 0.35:
        return "many"
    return "some"


def awkward_place(name: str) -> bool:
    return any(mark in name for mark in (",", "&", "(", " and "))


def opening_clause(profile) -> str:
    count = nforts(profile["n"])
    where = esc(where_clause(profile["kind"], profile["name"], profile["country"]))
    place = esc(place_name(profile["kind"], profile["name"]))
    use_atlas = profile["n"] >= 12 and crc(profile["key"], "atlas") % 5 == 0
    if profile["kind"] == "nation" and profile["name"] == "Isle of Man":
        tail = ", scattered across the whole island"
    elif profile["kind"] == "nation":
        tail = ", spread across the whole country"
    else:
        tail = ""
    if use_atlas:
        return f"The Atlas of Hillforts of Britain and Ireland lists {count} {where}{tail}"
    if awkward_place(profile["name"]):
        return f"There are {count} {where}{tail}"
    return pick(profile["key"], "open", [
        f"{place} has {count}{tail}",
        f"There are {count} {where}{tail}",
    ])


def shares(profile) -> dict:
    n = max(profile["n"], 1)
    types = profile["type_counts"]
    topo = profile["topo_counts"]
    return {
        "prom": types.get("promontory", 0) / n,
        "coast": topo.get("coastal-promontory", 0) / n,
        "contour": (types.get("contour", 0) + types.get("partial-contour", 0)) / n,
        "hilltop": topo.get("hilltop", 0) / n,
        "level_type": types.get("level", 0) / n,
        "lowland": topo.get("lowland", 0) / n,
        "slope": max(types.get("hillslope", 0) / n, topo.get("hillslope", 0) / n),
        "spur": topo.get("spur", 0) / n,
    }


def landscape_clause(profile):
    if profile["n"] < 3:
        return None
    part = shares(profile)
    options = []
    hill_led = (
        part["contour"] >= 0.4
        and part["contour"] >= part["prom"]
        and part["level_type"] < 0.35
        and part["lowland"] < 0.35
    )
    coast_led = part["coast"] >= 0.35 and not (hill_led and part["contour"] >= part["coast"])
    if coast_led:
        word = proportion(part["coast"])
        if part["contour"] >= 0.25 or part["hilltop"] >= 0.25:
            options = [
                f"{word} stand on a coastal headland, with banks cutting the promontory off from the land behind, while others follow the contours of a hilltop",
                f"{word} are forts on a coastal headland, and others follow the contours of a hilltop",
            ]
        else:
            options = [
                f"{word} stand on a coastal headland, with banks cutting the promontory off from the land behind",
                f"{word} are forts on a coastal headland, cut off from the land behind by banks",
            ]
    elif hill_led:
        word = proportion(part["contour"])
        if part["coast"] >= 0.2 and part["prom"] - part["coast"] < 0.2:
            options = [
                f"{word} follow the contours of a hilltop, and some stand on coastal headlands cut off by banks",
                f"{word} are hilltop forts, with some on coastal headlands cut off by banks",
                f"{word} are forts that follow the contours of a hilltop, with others on coastal headlands",
            ]
        elif part["prom"] >= 0.25:
            options = [
                f"{word} follow the contours of a hilltop, and others are forts on a headland or spur cut off by banks",
                f"{word} are hilltop forts, though a good number close off a headland or spur with banks",
            ]
        elif part["spur"] >= 0.25:
            options = [
                f"{word} follow the contours of a hilltop, though some sit on a spur",
                f"{word} are hilltop forts, the banks taking their line from the summit, though some sit on a spur",
                f"{word} are forts that follow the contours of a hilltop, a number of them on a spur",
            ]
        else:
            options = [
                f"{word} follow the contours of a hilltop",
                f"{word} are hilltop forts, the banks taking their line from the summit",
                f"{word} are forts that follow the contours of a hilltop",
                f"{word} keep to the high ground, with their banks following the hilltop",
            ]
    elif part["prom"] >= 0.4:
        word = proportion(part["prom"])
        options = [
            f"{word} are forts on a headland or spur, cut off from the land behind by banks",
            f"{word} close off a headland or spur with banks",
            f"{word} are forts on a headland or spur cut off by banks",
        ]
    elif part["hilltop"] >= 0.4 and part["level_type"] < 0.35 and part["lowland"] < 0.35:
        word = proportion(part["hilltop"])
        if part["coast"] >= 0.2:
            options = [
                f"{word} sit on a hilltop, and some stand on coastal headlands cut off by banks",
                f"{word} are on high ground, with some on coastal headlands cut off by banks",
            ]
        else:
            options = [
                f"{word} sit on a hilltop",
                f"{word} are set on high ground",
            ]
    elif part["level_type"] >= 0.35:
        word = proportion(part["level_type"])
        options = [
            f"{word} are enclosures on level ground rather than forts on hilltops",
            f"{word} sit on low, fairly flat ground, the banks forming the enclosure",
        ]
    elif part["lowland"] >= 0.35:
        word = proportion(part["lowland"])
        options = [
            f"{word} sit on low ground rather than on hilltops",
            f"{word} are down on lower ground, away from the hilltops",
        ]
    elif part["slope"] >= 0.35:
        word = proportion(part["slope"])
        options = [
            f"{word} are set on a slope rather than on a summit",
            f"{word} sit on a slope, below the crest of the hill",
        ]
    else:
        bits = []
        if part["contour"] >= 0.2:
            bits.append("forts that follow the contours of a hilltop")
        elif part["hilltop"] >= 0.2:
            bits.append("forts on a hilltop")
        if part["prom"] >= 0.2 or part["coast"] >= 0.2:
            bits.append("forts on a headland or spur cut off by banks")
        if part["level_type"] >= 0.2 or part["lowland"] >= 0.2:
            bits.append("enclosures on level ground")
        if part["slope"] >= 0.2:
            bits.append("forts set on a slope")
        if len(bits) >= 2:
            options = [
                f"you will find both {bits[0]} and {bits[1]}",
                f"the forts include {bits[0]} and {bits[1]}",
            ]
        elif len(bits) == 1:
            options = [f"a good number are {bits[0]}"]
    if not options:
        return None
    return pick(profile["key"], "land", options)


def opening_sentence(profile, use_land: bool) -> str:
    opener = opening_clause(profile)
    land = landscape_clause(profile) if use_land else None
    if not land:
        return capitalise(opener) + "."
    if " and " in land or crc(profile["key"], "join") % 2 == 0:
        return f"{capitalise(opener)}: {land}."
    return f"{capitalise(opener)}, and {land}."


def largest_sentence(profile):
    largest = profile["largest"]
    if not largest or not profile["max_area"]:
        return None
    area = area_words(profile["max_area"])
    if len(largest) > 1:
        named = [site for site in largest[:2] if not ambiguous_label(site, profile["sites"])]
        labels = [distinctive_name(site, profile["sites"]) for site in named]
        if len(named) >= 2 and len(set(labels)) == len(labels):
            links = join_and(display_link(profile, site) for site in named[:2])
            return f"The largest are {links}, each covering {area}."
        return f"The largest cover {area}."
    site = largest[0]
    if ambiguous_label(site, profile["sites"]):
        return f"The largest covers {area}."
    link = display_link(profile, site)
    portrait = portrait_clause(site, full=False)
    median_area = profile["median_area"]
    giant = (
        profile["n"] >= 5
        and median_area
        and profile["max_area"] >= 10
        and profile["max_area"] >= 4 * median_area
    )
    sentence = f"{link} is much the largest, {portrait}" if giant else f"The largest is {link}, {portrait}"
    if condition_note(site) == "poor":
        sentence += ", though little of it survives above ground"
    return sentence + "."


def candidate_forts(profile) -> list:
    best = select_best(profile["sites"], profile["kind"])
    if best:
        return best
    return sorted(
        profile["sites"],
        key=lambda site: (-(site.get("enclosed") or 0), site["name"].lower(), site["code"]),
    )


def other_named(profile, limit: int) -> list:
    if limit <= 0:
        return []
    largest_slugs = {site["slug"] for site in profile["largest"][:1]}
    seen_counties = {site.get("county") for site in profile["largest"][:1]}
    chosen = []
    seen = set()

    def acceptable(site, allow_poor: bool, allow_same_county: bool) -> bool:
        if site["slug"] in seen or site["slug"] in largest_slugs:
            return False
        if ambiguous_label(site, profile["sites"]):
            return False
        if not allow_poor and condition_note(site) == "poor":
            return False
        if (
            profile["kind"] == "nation"
            and not allow_same_county
            and site.get("county") in seen_counties
        ):
            return False
        return True

    def add(site):
        seen.add(site["slug"])
        chosen.append(site)
        seen_counties.add(site.get("county"))

    pool = candidate_forts(profile)
    for allow_poor, allow_same in ((False, False), (True, False), (False, True), (True, True)):
        if profile["kind"] == "nation" and allow_same and len(chosen) >= 2:
            break
        for site in pool:
            if len(chosen) >= limit:
                return chosen
            if acceptable(site, allow_poor, allow_same):
                add(site)
    return chosen


def names_sentence(profile, limit: int):
    forts = other_named(profile, limit)
    if not forts:
        return None
    joined = join_and(display_link(profile, site) for site in forts)
    from_best = bool(select_best(profile["sites"], profile["kind"]))
    if len(forts) == 1:
        if from_best:
            return pick(profile["key"], "names1", [
                f"A good place to start is {joined}.",
                f"If you are choosing a first visit, look at {joined}.",
            ])
        return f"Also look at {joined}."
    if from_best:
        return pick(profile["key"], "names", [
            f"Good places to start include {joined}.",
            f"If you are choosing a first visit, look at {joined}.",
            f"The forts to consider first are {joined}.",
        ])
    if all((site.get("enclosed") or 0) >= 1 for site in forts):
        return f"Other sizeable forts include {joined}."
    return f"Also look at {joined}."


def dating_sentence(profile):
    early = late = roman = medieval = dated = iron = 0
    for site in profile["sites"]:
        periods = {code for code in (site.get("periods") or []) if code != "unknown"}
        if not periods:
            continue
        dated += 1
        if "800-400" in periods:
            early += 1
        if "400-ad50" in periods:
            late += 1
        if periods & {"800-400", "400-ad50"}:
            iron += 1
        if "ad50-400" in periods:
            roman += 1
        if periods & {"ad400-800", "post-800"}:
            medieval += 1
    if dated < 5:
        return None
    britain = roman_framing(profile["kind"], profile["name"], profile["country"])
    if iron / dated < 0.55 or iron < 5:
        if medieval >= 5 and medieval / dated >= 0.45 and iron / dated < 0.4:
            if medieval / profile["n"] >= 0.15:
                if britain:
                    return "Many of the dated forts belong to the early medieval centuries, after the Roman period."
                return "Many of the dated forts belong to the early medieval centuries."
            if britain:
                return "Where a date has been suggested, it is often early medieval, in the centuries after the Roman period."
            return "Where a date has been suggested, it is often early medieval."
        return None
    if early >= 3 and late >= 3:
        span = (
            "from about 800 BC to the Roman conquest"
            if britain
            else "from about 800 BC into the early centuries AD"
        )
        core = f"mostly Iron Age, {span}"
    elif late >= early:
        core = (
            "mostly later Iron Age, in the centuries before the Roman conquest"
            if britain
            else "mostly later Iron Age, into the early centuries AD"
        )
    else:
        core = "mostly early Iron Age, from about 800 BC"
    if iron / profile["n"] >= 0.35:
        sentence = f"They are {core}."
    else:
        sentence = f"Where a date has been suggested, they are {core}."
    if britain and roman >= 5 and roman / dated >= 0.3:
        sentence += " Some were still occupied in the Roman period."
    return sentence


def morph_classes(profile):
    classes = []
    for site in profile["sites"]:
        parents = []
        for code in site.get("morph") or []:
            parent = parent_morph(str(code))
            if parent and parent not in parents:
                parents.append(parent)
        if len(parents) == 1:
            classes.append(parents[0])
    return classes


def rampart_detail(profile):
    if profile["n"] < 4:
        return None
    classes = morph_classes(profile)
    if len(classes) < max(4, int(0.35 * profile["n"])):
        return None
    known = len(classes)
    single = sum(1 for item in classes if item == "univallate") / known
    double = sum(1 for item in classes if item == "bivallate") / known
    several = sum(1 for item in classes if item == "multivallate") / known
    stone = profile["surface_counts"].get("stone-wall", 0) / profile["n"]
    earth = profile["surface_counts"].get("earthen-bank", 0) / profile["n"]
    if single >= 0.6 and earth >= 0.45 and stone < earth:
        return "usually with a single earthen rampart"
    if single >= 0.6 and stone >= 0.4 and stone >= earth:
        return "usually with a single stone rampart"
    if single >= 0.6:
        return "usually with a single rampart"
    if double >= 0.45 and double >= single:
        return "often with two lines of rampart"
    if several >= 0.4 and several >= double and several >= single:
        return "often with several lines of rampart"
    return None


def size_clause(profile):
    measured = profile["measured"]
    if len(measured) < 5 or len(measured) / profile["n"] < 0.55:
        return None
    if profile["under_1"] / len(measured) >= 0.6:
        return "most cover less than a hectare"
    if profile["median_area"] and profile["median_area"] >= 1.5:
        return f"a typical enclosure covers {area_words(profile['median_area'])}"
    return None


def survival_text(profile):
    if profile["n"] < 4:
        return None
    visible = profile["visible"] / profile["n"]
    poor = sum(1 for site in profile["sites"] if condition_note(site) == "poor") / profile["n"]
    stone = profile["surface_counts"].get("stone-wall", 0) / profile["n"]
    earth = profile["surface_counts"].get("earthen-bank", 0) / profile["n"]
    if visible >= 0.55:
        if stone >= 0.4 and stone >= earth:
            return pick(profile["key"], "survive", [
                "Most are still visible on the ground",
                "At most of them the walls are still there to see",
            ])
        return pick(profile["key"], "survive", [
            "Most still survive as visible earthworks",
            "At most of them the earthworks are still there to see",
        ])
    if poor >= 0.45 and visible <= 0.4:
        return "At many of them, little survives above ground"
    return None


def character_sentence(profile):
    survival = survival_text(profile)
    rampart = rampart_detail(profile)
    size = size_clause(profile)
    if survival and survival.startswith("At many"):
        rampart = None
    if survival and "wall" in survival.lower() and rampart and "stone" in rampart:
        rampart = None
    extras = [item for item in (rampart, size) if item]
    if survival and extras:
        if len(extras) == 1 and extras[0].startswith(("most ", "a typical")):
            return f"{survival}, and {extras[0]}."
        if len(extras) == 1:
            return f"{survival}, {extras[0]}."
        return f"{survival}, {extras[0]}, and {extras[1]}."
    if survival:
        return survival + "."
    lead = {
        "usually with a single earthen rampart": "A single earthen rampart is the usual form",
        "usually with a single stone rampart": "A single stone rampart is the usual form",
        "usually with a single rampart": "A single rampart is the usual form",
        "often with two lines of rampart": "Two lines of rampart are common",
        "often with several lines of rampart": "Several lines of rampart are common",
    }
    if rampart and size:
        return f"{lead[rampart]}, and {size}."
    if rampart:
        return lead[rampart] + "."
    if size:
        return capitalise(size) + "."
    return None


def landuse_clause(profile):
    if profile["n"] < 4:
        return None
    ranked = profile["land_counts"].most_common(1)
    if not ranked:
        return None
    code, count = ranked[0]
    if count / profile["n"] < 0.45:
        return None
    pretty = {
        "pasture": "pasture",
        "moorland": "heather moorland",
        "woodland": "woodland",
        "forestry": "forestry plantation",
        "scrub": "scrub or bracken",
        "arable": "arable land",
        "coastal-grassland": "coastal grassland",
        "heath": "heath",
        "parkland": "parkland",
    }
    if code not in pretty:
        return None
    if count / profile["n"] >= 0.6:
        return f"the ground around them is mostly {pretty[code]}"
    return f"many of the forts lie in {pretty[code]}"


def altitude_clause(profile):
    altitudes = profile["altitudes"]
    if len(altitudes) < max(4, int(0.5 * profile["n"])):
        return None
    lo, hi = min(altitudes), max(altitudes)
    if hi - lo < 80:
        return None
    hi_r = int(round(hi / 10.0) * 10)
    lo_r = int(round(lo / 10.0) * 10)
    if lo_r < 30:
        return f"they run from near sea level up to about {hi_r} m"
    return f"they stand from about {lo_r} m to about {hi_r} m above sea level"


def ground_sentence(profile):
    land = landuse_clause(profile)
    altitude = altitude_clause(profile)
    if land and altitude:
        return f"{capitalise(land)}, and {altitude}."
    if land:
        return capitalise(land) + "."
    if altitude:
        return capitalise(altitude) + "."
    return None


def scheduled_sentence(profile):
    if profile["kind"] == "nation" and profile["name"] in {"Republic of Ireland", "Isle of Man"}:
        return None
    if profile["kind"] == "county" and profile["country"] in {"Republic of Ireland", "Isle of Man"}:
        return None
    if profile["n"] < 6 or profile["scheduled"] / profile["n"] < 0.55:
        return None
    if profile["scheduled"] / profile["n"] >= 0.75:
        return "Most of them are scheduled monuments."
    return "Many of them are scheduled monuments."


def portrait_aside(profile, skip_text: str = ""):
    largest = profile["largest"][:1]
    largest_family = type_family(largest[0]) if largest else ""
    largest_poor = bool(largest) and condition_note(largest[0]) == "poor"
    fallback = None
    for site in other_named(profile, 4):
        if condition_note(site) == "poor":
            continue
        link = display_link(profile, site)
        if skip_text and link in skip_text:
            continue
        portrait = portrait_clause(site, full=False)
        if portrait in {"a hillfort", "a small hillfort"}:
            continue
        sentence = f"{link} is {portrait}."
        if type_family(site) != largest_family:
            return sentence
        if largest_poor and fallback is None:
            fallback = sentence
    return fallback


def aside_sentence(profile):
    return portrait_aside(profile)


def extra_sentence(profile):
    return portrait_aside(profile, aside_sentence(profile) or "")


def detail_sentence(profile):
    skip = f"{aside_sentence(profile) or ''} {extra_sentence(profile) or ''}"
    for site in other_named(profile, 3):
        if condition_note(site) == "poor":
            continue
        link = display_link(profile, site)
        if link in skip:
            continue
        portrait = portrait_clause(site, full=False)
        if not any(token in portrait for token in ("hectare", "rampart", "headland", "hilltop", "enclosure", "slope")):
            continue
        return f"{link} is {portrait}."
    return None


def close_sentence(profile, long: bool) -> str:
    has_best = profile["indexed_n"] >= FULL_INDEXED_MIN
    if has_best and long:
        return pick(profile["key"], "close-l", [
            "If you are deciding where to go, start with the forts picked out below. The map shows every hillfort, and each name opens its own page.",
            "The list below is there to help you choose a visit. Every hillfort is on the map, with its own page.",
        ])
    if has_best:
        return pick(profile["key"], "close-s", [
            "The list below is a good place to start, and the map shows the rest.",
            "Start with the forts picked out below, or open the map and look around.",
            "Use the list below to choose a visit, then the map to see what else is nearby.",
        ])
    if long:
        return pick(profile["key"], "close-m", [
            "The map below shows the full spread, and each name opens its own page.",
            "Use the map to see how they are spread, and open any name for a closer look.",
        ])
    return pick(profile["key"], "close-s2", [
        "Every fort is on the map below.",
        "The map below shows where they all sit.",
    ])


def render_pack(profile, name_limit, use_land, use_dating, use_character, use_aside, use_ground, use_scheduled, use_extra, use_detail, long_close):
    lead = [opening_sentence(profile, use_land)]
    largest = largest_sentence(profile)
    if largest:
        lead.append(largest)
    names = names_sentence(profile, name_limit)
    if names:
        lead.append(names)
    if use_aside:
        aside = aside_sentence(profile)
        if aside:
            lead.append(aside)
    if use_extra:
        extra = extra_sentence(profile)
        if extra:
            lead.append(extra)
    if use_detail:
        detail = detail_sentence(profile)
        if detail:
            lead.append(detail)
    dating = dating_sentence(profile) if use_dating else None
    character = character_sentence(profile) if use_character else None
    colour = []
    if dating and character and crc(profile["key"], "colour-order") % 2:
        colour.extend([character, dating])
    else:
        if dating:
            colour.append(dating)
        if character:
            colour.append(character)
    if use_ground:
        ground = ground_sentence(profile)
        if ground:
            colour.append(ground)
    if use_scheduled:
        scheduled = scheduled_sentence(profile)
        if scheduled:
            colour.append(scheduled)
    paragraphs = [" ".join(item for item in lead if item)]
    if colour:
        paragraphs.append(" ".join(colour))
    paragraphs.append(close_sentence(profile, long_close))
    return [paragraph for paragraph in paragraphs if paragraph.strip()]


def pack_words(items) -> int:
    return word_count(" ".join(item for item in items if item))


def assemble_many(profile) -> tuple[list[str], int]:
    lo, hi = word_limits(profile["n"], profile["kind"])
    target = (lo + hi) // 2 + (crc(profile["key"], "len") % 11) - 5
    target = max(lo, min(hi, target))
    name_choices = (4, 3) if profile["kind"] == "nation" else (2, 1)
    flags = {
        "land": landscape_clause(profile) is not None,
        "dating": dating_sentence(profile) is not None,
        "character": character_sentence(profile) is not None,
        "aside": aside_sentence(profile) is not None,
        "ground": ground_sentence(profile) is not None,
        "scheduled": scheduled_sentence(profile) is not None,
        "extra": extra_sentence(profile) is not None,
        "detail": detail_sentence(profile) is not None,
    }
    best = None
    for name_limit in name_choices:
        for use_land in ((True, False) if flags["land"] else (False,)):
            for use_dating in ((True, False) if flags["dating"] else (False,)):
                for use_character in ((True, False) if flags["character"] else (False,)):
                    for use_aside in ((True, False) if flags["aside"] else (False,)):
                        for use_ground in ((True, False) if flags["ground"] else (False,)):
                            for use_scheduled in ((True, False) if flags["scheduled"] else (False,)):
                                for use_extra in ((True, False) if flags["extra"] else (False,)):
                                    for use_detail in ((True, False) if flags["detail"] else (False,)):
                                        for long_close in (False, True):
                                            paragraphs = render_pack(
                                                profile,
                                                name_limit,
                                                use_land,
                                                use_dating,
                                                use_character,
                                                use_aside,
                                                use_ground,
                                                use_scheduled,
                                                use_extra,
                                                use_detail,
                                                long_close,
                                            )
                                        words = pack_words(paragraphs)
                                        distance = 0 if lo <= words <= hi else min(abs(words - lo), abs(words - hi)) + 1000
                                        essential = 0
                                        if flags["land"] and not use_land:
                                            essential += 4
                                        if flags["dating"] and not use_dating:
                                            essential += 4
                                        if flags["character"] and not use_character:
                                            essential += 3
                                        if flags["aside"] and not use_aside:
                                            essential += 1
                                        fluff = 0
                                        if use_scheduled:
                                            fluff += 3
                                        if use_ground:
                                            fluff += 2
                                        if use_extra:
                                            fluff += 2
                                        if use_detail:
                                            fluff += 1
                                        if long_close:
                                            fluff += 1
                                        rank = (
                                            distance,
                                            name_choices[0] - name_limit,
                                            essential,
                                            fluff,
                                            abs(words - target),
                                        )
                                        if best is None or rank < best[0]:
                                            best = (rank, paragraphs, words)
    paragraphs = best[1]
    return paragraphs, word_count(" ".join(paragraphs))


def single_sentences(profile) -> list[str]:
    site = profile["sites"][0]
    place = esc(profile["name"])
    link = fort_link(site, profile["sites"])
    portrait = portrait_clause(site, full=True)
    if awkward_place(profile["name"]):
        first = f"The only recorded hillfort in {place} is {link}, {portrait}."
    else:
        first = f"{place}'s only recorded hillfort is {link}, {portrait}."
    note = condition_note(site)
    if note == "poor":
        second = "Little survives above ground today."
    elif note == "visible":
        surface = set(site.get("surface") or [])
        if "stone-wall" in surface and "earthen-bank" not in surface:
            second = "The stone wall is still there to see."
        else:
            second = "The earthworks are still there to see."
    else:
        second = "It is marked on the map below."
    return [first, second]


def pair_sentences(profile) -> list[str]:
    ordered = sorted(
        profile["sites"],
        key=lambda site: (-(site.get("enclosed") or 0), site["name"].lower(), site["code"]),
    )
    place = esc(profile["name"])
    where = esc(where_clause(profile["kind"], profile["name"], profile["country"]))
    if awkward_place(profile["name"]):
        sentences = [f"There are two hillforts {where}."]
    else:
        sentences = [f"{place} has two hillforts."]
    primary, secondary = ordered[0], ordered[1]
    detail = f"{fort_link(primary, profile['sites'])} is {portrait_clause(primary, full=True)}"
    note = condition_note(primary)
    if note == "poor":
        detail += ", and little survives above ground"
    elif note == "visible":
        detail += ", and the earthworks are still there to see"
    detail += "."
    sentences.append(detail)
    if primary.get("scheduled") and profile["country"] not in {"Republic of Ireland", "Isle of Man"}:
        sentences.append("It is a scheduled monument.")
    complement = portrait_clause(secondary, full=True)
    if complement in {"a hillfort", "a small hillfort"}:
        sentences.append(f"{fort_link(secondary, profile['sites'])} is the other.")
    else:
        sentences.append(f"{fort_link(secondary, profile['sites'])} is {complement}.")
    note2 = condition_note(secondary)
    if note2 == "poor" and note != "poor":
        sentences.append(f"Little survives of {fort_link(secondary, profile['sites'])} above ground.")
    elif note2 == "visible" and note == "poor":
        sentences.append(f"The earthworks of {fort_link(secondary, profile['sites'])} are still visible.")
    sentences.append("Both are marked on the map below.")
    return sentences


def assemble_few(profile) -> tuple[list[str], int]:
    if profile["n"] <= 1:
        sentences = single_sentences(profile)
    else:
        sentences = pair_sentences(profile)
    lo, hi = word_limits(profile["n"], profile["kind"])
    while pack_words(sentences) > hi and len(sentences) > 2:
        sentences.pop(-2)
    if pack_words(sentences) < lo:
        filler = "It is marked on the map below." if profile["n"] <= 1 else "Open either name for a closer look."
        if filler not in sentences:
            sentences.append(filler)
    paragraph = " ".join(sentences)
    return [paragraph], word_count(paragraph)


def assemble(profile) -> tuple[list[str], int]:
    if profile["n"] <= 2:
        return assemble_few(profile)
    return assemble_many(profile)

def build_profile(sites, *, kind, name, country, slug) -> dict:
    tables = _tables()
    measured = [site for site in sites if isinstance(site.get("enclosed"), (int, float))]
    measured.sort(key=lambda site: (-site["enclosed"], site["name"].lower(), site["code"]))
    areas = [site["enclosed"] for site in measured]
    type_counts = Counter()
    topo_counts = Counter()
    land_counts = Counter()
    surface_counts = Counter()
    for site in sites:
        for code in site.get("types") or []:
            if code in tables.TYPE_LABELS:
                type_counts[code] += 1
        for code in site.get("topo") or []:
            if code in tables.TOPO_LABELS:
                topo_counts[code] += 1
        for code in site.get("landuse") or []:
            if code in tables.LANDUSE_LABELS:
                land_counts[code] += 1
        for code in site.get("surface") or []:
            if code in tables.SURFACE_LABELS:
                surface_counts[code] += 1
    largest = []
    if measured:
        hi = measured[0]["enclosed"]
        largest = [site for site in measured if site["enclosed"] == hi]
    return {
        "kind": kind,
        "name": name,
        "country": country,
        "slug": slug,
        "key": f"{kind}:{slug}",
        "sites": sites,
        "n": len(sites),
        "indexed_n": count_sites(sites, lambda site: site.get("index")),
        "measured": measured,
        "areas": areas,
        "median_area": round(float(median(areas)), 2) if areas else None,
        "max_area": areas[0] if measured else None,
        "min_area": min(areas) if areas else None,
        "largest": largest,
        "under_1": sum(1 for area in areas if area < 1),
        "type_counts": type_counts,
        "topo_counts": topo_counts,
        "land_counts": land_counts,
        "surface_counts": surface_counts,
        "visible": count_sites(sites, visible_earthworks),
        "scheduled": count_sites(sites, lambda site: bool(site.get("scheduled"))),
        "altitudes": [site["altitude"] for site in sites if isinstance(site.get("altitude"), (int, float))],
        "stone": surface_counts.get("stone-wall", 0),
    }


def visit_score(site) -> float:
    score = 0.0
    enclosed = site.get("enclosed")
    if isinstance(enclosed, (int, float)):
        score += min(float(enclosed), 40)
    elif isinstance(site.get("footprint"), (int, float)):
        score += min(float(site["footprint"]), 15) * 0.4
    condition = set(site.get("condition") or [])
    if "extant" in condition:
        score += 20
    elif "cropmark" in condition:
        score += 4
    if "destroyed" in condition and "extant" not in condition:
        score -= 8
    if site.get("wikipedia"):
        score += 40
    if site.get("scheduled"):
        score += 15
    excavations = geophysics = earthworks = lidar = 0
    for item in site.get("investigations") or []:
        label = str(item).lower()
        if label.startswith("excav"):
            excavations += 1
        elif "geophys" in label:
            geophysics += 1
        elif label.startswith("earth"):
            earthworks += 1
        elif "lidar" in label:
            lidar += 1
    score += min(excavations, 4) * 8
    score += min(geophysics, 2) * 5
    score += min(earthworks, 3) * 3
    score += min(lidar, 2) * 3
    score += min(len(site.get("refs") or []), 8) * 2
    reliability = str(site.get("datingReliability") or "")
    if reliability.startswith("A "):
        score += 8
    elif reliability.startswith("B "):
        score += 4
    if period_labels(site, _tables().PERIOD_LABELS):
        score += 3
    return score


def select_best(sites, kind: str) -> list:
    indexed = [site for site in sites if site.get("index")]
    if len(indexed) < FULL_INDEXED_MIN:
        return []
    indexed.sort(key=lambda site: (-visit_score(site), site["name"].lower(), site["code"]))
    if len(indexed) <= 10:
        return indexed
    cap = 10 if kind == "nation" else 8
    return indexed[:cap]


def fact_line(site) -> str:
    sentence = f"It is {portrait_clause(site, full=False)}"
    note = condition_note(site)
    if note == "poor":
        return sentence + ", and little survives above ground."
    if note == "visible":
        surface = set(site.get("surface") or [])
        if "stone-wall" in surface and "earthen-bank" not in surface:
            return sentence + ", and the stone wall is still visible."
        return sentence + ", and the earthworks are still visible."
    return sentence + "."


def size_label(site) -> str:
    if isinstance(site.get("enclosed"), (int, float)):
        return f"{format_number(site['enclosed'])} ha"
    if isinstance(site.get("footprint"), (int, float)):
        return f"footprint {format_number(site['footprint'])} ha"
    return ""


def stats_rows(profile) -> list[tuple[str, str, str]]:
    rows = [("Hillforts", comma(profile["n"]), "")]
    if profile["largest"]:
        rows.append((
            "Largest",
            f"{format_number(profile['max_area'])} ha",
            distinctive_name(profile["largest"][0], profile["sites"]),
        ))
    if profile["visible"]:
        rows.append(("Visible earthworks", comma(profile["visible"]), ""))
    if profile["scheduled"]:
        rows.append(("Scheduled monument", comma(profile["scheduled"]), ""))
    return rows


def meta_description(profile, has_best: bool) -> str:
    where = where_plain(profile["kind"], profile["name"], profile["country"])
    lead = f"{nforts(profile['n']).capitalize()} in {where}."
    if profile["largest"]:
        lead += (
            f" {distinctive_name(profile['largest'][0], profile['sites'])} is the largest, "
            f"at {format_number(profile['max_area'])} ha."
        )
    if has_best:
        lead += " Places to visit are picked out on the page."
    else:
        lead += " See them on the map."
    text = " ".join(lead.split())
    if len(text) > 180:
        text = f"{nforts(profile['n']).capitalize()} in {where}."
        if has_best:
            text += " Places to visit are picked out on the page."
    return text


def json_ld(profile, best, description, canonical, h1) -> dict:
    code = COUNTRY_CODE[profile["country"] if profile["kind"] == "county" else profile["name"]]
    place = {"@type": "Place", "name": profile["name"]}
    if profile["kind"] == "county":
        place["address"] = {
            "@type": "PostalAddress",
            "addressRegion": profile["name"],
            "addressCountry": code,
        }
        place["containedInPlace"] = {"@type": "Place", "name": profile["country"]}
    else:
        place["address"] = {"@type": "PostalAddress", "addressCountry": code}
    data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": h1,
        "url": canonical,
        "description": description,
        "about": place,
    }
    if best:
        data["mainEntity"] = {
            "@type": "ItemList",
            "name": best_heading(profile["name"]),
            "itemListOrder": "https://schema.org/ItemListOrderDescending",
            "numberOfItems": len(best),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index,
                    "name": site["name"],
                    "url": f"https://hillfortsmap.co.uk/sites/{site['slug']}/",
                }
                for index, site in enumerate(best, start=1)
            ],
        }
    return data


INTRO_BANS = (
    (r"\brecords?\b", "record"),
    (r"recorded for", "recorded for"),
    (r"short introduction", "short introduction"),
    (r"other types", "other types"),
    (r"likely destroyed", "likely destroyed"),
    (r"\bunivallate\b", "univallate"),
    (r"\bbivallate\b", "bivallate"),
    (r"\bmultivallate\b", "multivallate"),
    (r"dating reliability", "dating reliability"),
)


def assert_intro(profile, paragraphs, words: int) -> None:
    lo, hi = word_limits(profile["n"], profile["kind"])
    if not (lo <= words <= hi):
        raise RuntimeError(f"{profile['slug']} intro is {words} words; expected {lo}–{hi}")
    plain = html.unescape(re.sub(r"<[^>]+>", " ", " ".join(paragraphs))).lower()
    for pattern, label in INTRO_BANS:
        if re.search(pattern, plain):
            raise RuntimeError(f"{profile['slug']} intro contains {label}")
    if plain.count("atlas of hillforts") > 1:
        raise RuntimeError(f"{profile['slug']} intro mentions the Atlas more than once")
    links = re.findall(r'href="/sites/[^"]+/"', " ".join(paragraphs))
    if profile["n"] >= 1 and not links:
        raise RuntimeError(f"{profile['slug']} intro does not link a hillfort")
    if profile["kind"] == "nation" and len(links) < 3:
        raise RuntimeError(f"{profile['slug']} intro names too few hillforts")


def hub_content(sites, *, kind, name, country, slug, nation_slug, canonical) -> dict:
    profile = build_profile(sites, kind=kind, name=name, country=country, slug=slug)
    paragraphs, words = assemble(profile)
    assert_intro(profile, paragraphs, words)
    best = select_best(sites, kind)
    h1 = heading(kind, name)
    description = meta_description(profile, bool(best))
    title = f"{h1} | Best hillforts to visit" if best else f"{h1} | Hillforts Map"
    if kind == "nation":
        crumbs = f'<p class="crumbs"><a href="/">Home</a> / {esc(name)}</p>'
    else:
        crumbs = (
            f'<p class="crumbs"><a href="/">Home</a> / '
            f'<a href="/nations/{esc(nation_slug)}/">{esc(country)}</a> / {esc(name)}</p>'
        )
    prose = '<div class="hub-intro">' + "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs) + "</div>"
    stats = ['<dl class="hub-stats">']
    for label, value, sub in stats_rows(profile):
        sub_html = f"<span>{esc(sub)}</span>" if sub else ""
        stats.append(f"<div><dt>{esc(label)}</dt><dd>{esc(value)}{sub_html}</dd></div>")
    stats.append("</dl>")
    best_html = ""
    if best:
        items = []
        for site in best:
            size = size_label(site)
            size_html = f' <span class="best-size">{esc(size)}</span>' if size else ""
            items.append(
                "<li><div class=\"best-body\">"
                f'<a href="/sites/{esc(site["slug"])}/">{esc(site["name"])}</a>{size_html}'
                f"<p>{esc(fact_line(site))}</p></div></li>"
            )
        best_html = f"<h2>{esc(best_heading(name))}</h2><ol class=\"best-list\">{''.join(items)}</ol>"
    body = f"{crumbs}<h1>{esc(h1)}</h1>{prose}{''.join(stats)}{best_html}"
    return {
        "title": title,
        "description": description,
        "h1": h1,
        "body": body,
        "json_ld": json_ld(profile, best, description, canonical, h1),
        "words": words,
        "best_slugs": [site["slug"] for site in best],
        "paragraphs": paragraphs,
    }
