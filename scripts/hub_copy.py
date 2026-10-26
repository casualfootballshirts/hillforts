"""Original county and nation introductions from structured Atlas fields.

Narrative and *Comments columns are not in the site data and are not used here.
Public pages never describe a record as indexed.
"""

from __future__ import annotations

import html
import zlib
from collections import Counter
from statistics import median

FULL_INDEXED_MIN = 3
WORD_FULL = (120, 200)
WORD_SHORT_MAX = 119

COUNTRY_CODE = {
    "England": "GB",
    "Scotland": "GB",
    "Wales": "GB",
    "Northern Ireland": "GB",
    "Republic of Ireland": "IE",
    "Isle of Man": "IM",
}

ATLAS = "the Atlas of Hillforts of Britain and Ireland"


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def crc(key, salt) -> int:
    return zlib.crc32(f"{key}|{salt}".encode("utf-8")) & 0xFFFFFFFF


def pick(key, salt, options):
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


def article(label: str) -> str:
    word = label.split(" ", 1)[0].lower()
    if word.startswith(("uni", "one", "eu", "use")):
        choice = "a"
    elif word[:1] in "aeiou":
        choice = "an"
    else:
        choice = "a"
    return f"{choice} {label}"


def nforts(n: int) -> str:
    noun = "hillfort" if n == 1 else "hillforts"
    number = "one" if n == 1 else comma(n)
    return f"{number} {noun}"


def plural_label(label: str, n: int) -> str:
    if n == 1:
        return label
    return label + "s"


def finish(text: str) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text


def word_count(text: str) -> int:
    return len(text.split())


def labels(codes, table):
    return [table[code] for code in codes or [] if code in table]


def _tables():
    import build_site as sitegen

    return sitegen


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


def distinctive_name(site, group) -> str:
    same = [other for other in group if other["name"] == site["name"]]
    if len(same) == 1:
        return site["name"]
    parish = site.get("parish")
    if parish and sum(1 for other in same if other.get("parish") == parish) == 1:
        return f"{site['name']} ({parish})"
    return f"{site['name']} ({site['code']})"


def name_list(group, all_sites, limit=3) -> str:
    ordered = sorted(group, key=lambda site: (site["name"].lower(), site["code"]))
    names = [distinctive_name(site, all_sites) for site in ordered[:limit]]
    if len(ordered) > limit:
        return f"{len(ordered)} hillforts, including {join_and(names)}"
    return join_and(names)


def parent_morph(code: str):
    if "multivallate" in code:
        return "multivallate"
    if "bivallate" in code:
        return "bivallate"
    if "univallate" in code:
        return "univallate"
    return None


def condition_phrase(codes) -> str:
    codes = set(codes or [])
    bits = []
    if "extant" in codes:
        bits.append("extant")
    if "cropmark" in codes:
        bits.append("a cropmark")
    if "destroyed" in codes:
        bits.append("likely destroyed")
    if not bits:
        return ""
    return "recorded as " + join_and(bits)


def setting_phrase(site, topo_labels) -> str:
    place_bits = []
    lowland = False
    for code in site.get("topo") or []:
        if code not in topo_labels:
            continue
        if code == "lowland":
            lowland = True
        else:
            place_bits.append(article(topo_labels[code]))
    place = ""
    if place_bits and lowland:
        place = "on " + join_and(place_bits) + " and in a lowland setting"
    elif place_bits:
        place = "on " + join_and(place_bits)
    elif lowland:
        place = "in a lowland setting"
    altitude = site.get("altitude")
    if isinstance(altitude, (int, float)):
        height = f"at {format_number(altitude)} m"
        return f"{place} {height}".strip() if place else height
    return place


def period_labels(site, period_labels_table) -> list[str]:
    found = []
    for code in site.get("periods") or []:
        if code == "unknown" or code not in period_labels_table:
            continue
        found.append(period_labels_table[code])
    return found


def count_sites(sites, pred) -> int:
    return sum(1 for site in sites if pred(site))


def build_profile(sites, *, kind, name, country, slug) -> dict:
    tables = _tables()
    measured = [
        site for site in sites
        if isinstance(site.get("enclosed"), (int, float))
    ]
    measured.sort(key=lambda site: (-site["enclosed"], site["name"].lower(), site["code"]))
    areas = [site["enclosed"] for site in measured]
    type_counts = Counter()
    topo_counts = Counter()
    land_counts = Counter()
    surface_counts = Counter()
    morph_buckets = Counter()
    morph_partial = Counter()
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
        seen = set()
        partial_seen = set()
        for code in site.get("morph") or []:
            parent = parent_morph(code)
            if not parent:
                continue
            if parent not in seen:
                morph_buckets[parent] += 1
                seen.add(parent)
            if str(code).startswith("partial"):
                partial_seen.add(parent)
        for parent in partial_seen:
            morph_partial[parent] += 1

    def has_flag(*needles):
        def pred(site):
            cond = set(site.get("condition") or [])
            return all(needle in cond for needle in needles)
        return pred

    dated_sites = [site for site in sites if period_labels(site, tables.PERIOD_LABELS)]
    period_counts = Counter()
    for site in dated_sites:
        for label in period_labels(site, tables.PERIOD_LABELS):
            period_counts[label] += 1
    reliable = count_sites(
        sites,
        lambda site: str(site.get("datingReliability") or "").startswith(("A ", "B ")),
    )
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
        "morph_buckets": morph_buckets,
        "morph_partial": morph_partial,
        "extant": count_sites(sites, has_flag("extant")),
        "cropmark": count_sites(sites, has_flag("cropmark")),
        "destroyed": count_sites(sites, has_flag("destroyed")),
        "both_extant_destroyed": count_sites(sites, has_flag("extant", "destroyed")),
        "both_extant_crop": count_sites(sites, has_flag("extant", "cropmark")),
        "scheduled": count_sites(sites, lambda site: bool(site.get("scheduled"))),
        "dated": len(dated_sites),
        "period_counts": period_counts,
        "reliable": reliable,
        "excavation": count_sites(
            sites,
            lambda site: any(str(item).lower().startswith("excav") for item in site.get("investigations") or []),
        ),
        "geophysical": count_sites(
            sites,
            lambda site: any("geophys" in str(item).lower() for item in site.get("investigations") or []),
        ),
        "earthwork": count_sites(
            sites,
            lambda site: any(str(item).lower().startswith("earth") for item in site.get("investigations") or []),
        ),
        "vitrification": surface_counts.get("vitrification", 0),
        "chevaux": count_sites(sites, lambda site: "chevaux-de-frise" in (site.get("flags") or [])),
        "guards": count_sites(sites, lambda site: "guard-chambers" in (site.get("flags") or [])),
        "altitudes": [
            site["altitude"] for site in sites if isinstance(site.get("altitude"), (int, float))
        ],
        "promontory_share": type_counts.get("promontory", 0) / len(sites),
        "coastal_share": topo_counts.get("coastal-promontory", 0) / len(sites),
        "stone": surface_counts.get("stone-wall", 0),
    }


def opening_sentence(p) -> str:
    n = p["n"]
    where = where_clause(p["kind"], p["name"], p["country"])
    verb = "is" if n == 1 else "are"
    if p["kind"] == "county":
        if p["country"] in ("Republic of Ireland", "Isle of Man"):
            place = f"{p['name']}, {where_plain('nation', p['country'], p['country'])},"
        else:
            place = f"{p['name']}, {p['country']},"
        located = f"{where}," if "," in where else where
        options = [
            f"The Atlas of Hillforts of Britain and Ireland records {nforts(n)} {where}.",
            f"{place} has {nforts(n)} in {ATLAS}.",
            f"{nforts(n).capitalize()} {located} {verb} recorded in {ATLAS}.",
        ]
    else:
        bare = p["name"]
        if p["name"] == "Isle of Man":
            bare = "The Isle of Man"
        elif p["name"] == "Republic of Ireland":
            bare = "The Republic of Ireland"
        options = [
            f"The Atlas of Hillforts of Britain and Ireland records {nforts(n)} {where}.",
            f"{bare} has {nforts(n)} in {ATLAS}.",
            f"{nforts(n).capitalize()} {where} {verb} recorded in {ATLAS}.",
        ]
    return pick(p["key"], "open", options)


def introductions_sentence(p):
    k = p["indexed_n"]
    n = p["n"]
    if k <= 0:
        return None
    if k == n:
        options = [
            "Each of these records has a short introduction.",
            "A short introduction is given for every one of these records.",
        ]
    elif k == 1:
        options = [
            "One of these records has a short introduction.",
            "A short introduction is given for one hillfort.",
        ]
    else:
        options = [
            f"{comma(k)} of these records have a short introduction.",
            f"A short introduction is given for {comma(k)} hillforts.",
            f"Short introductions cover {comma(k)} of the {comma(n)} records.",
        ]
    return pick(p["key"], "intro", options)


def size_sentence(p):
    measured = p["measured"]
    if not measured:
        return None
    n = p["n"]
    n_m = len(measured)
    lo = p["min_area"]
    hi = p["max_area"]
    lo_s = format_number(lo)
    hi_s = format_number(hi)
    largest = p["largest"]
    lname = name_list(largest, p["sites"])
    verb = "is" if len(largest) == 1 else "are"
    has = "has" if len(largest) == 1 else "have"
    if len(largest) == 1:
        top = f"the largest is {lname} at {hi_s} hectares"
    else:
        top = f"the largest are {lname}, each at {hi_s} hectares"
    coverage = ""
    if n_m < n:
        coverage = f"Enclosed area is recorded for {nforts(n_m)}. "
    if n_m == 1:
        return finish(f"{coverage}The enclosed area of {lname} is {hi_s} hectares")
    if lo == hi:
        return finish(f"{coverage}Each recorded enclosed area is {hi_s} hectares")

    under = p["under_1"]
    med = format_number(p["median_area"])
    small = n_m >= 8 and under / n_m >= 0.6
    giant = n_m >= 5 and p["median_area"] and hi >= 4 * p["median_area"] and hi >= 10
    options = []
    if small:
        options.append(finish(
            f"{coverage}{comma(under)} of the {comma(n_m)} recorded enclosed areas are under one hectare. "
            f"The median is {med} hectares, and {top}"
        ))
        options.append(finish(
            f"{coverage}Enclosed areas run from {lo_s} to {hi_s} hectares, with a median of {med} hectares. "
            f"{comma(under)} of those {comma(n_m)} are under one hectare, and {top}"
        ))
    elif giant:
        options.append(finish(
            f"{coverage}The median enclosed area is {med} hectares. {lname} {has} the largest enclosed area, at {hi_s} hectares"
        ))
        options.append(finish(
            f"{coverage}Recorded enclosures span {lo_s}–{hi_s} hectares. "
            f"The median is {med} hectares, and {top}"
        ))
    options.extend([
        finish(f"{coverage}Enclosed areas run from {lo_s} to {hi_s} hectares, and {top}"),
        finish(
            f"{coverage}{lname} {has} the largest enclosed area, at {hi_s} hectares. "
            f"The smallest recorded enclosure is {lo_s} hectares"
        ),
    ])
    return pick(p["key"], "size", options)


def second_sentence(p):
    measured = p["measured"]
    if len(measured) < 2 or not p["max_area"]:
        return None
    hi = p["max_area"]
    seconds = [site for site in measured if site["enclosed"] < hi]
    if not seconds:
        return None
    second_area = seconds[0]["enclosed"]
    if second_area < 1 or hi < second_area * 2.5:
        return None
    group = [site for site in seconds if site["enclosed"] == second_area]
    name = name_list(group, p["sites"])
    if len(group) == 1:
        return finish(f"The next largest enclosed area is {name} at {format_number(second_area)} hectares")
    return finish(
        f"The next largest enclosed areas are {name}, each at {format_number(second_area)} hectares"
    )


def type_sentence(p):
    tables = _tables()
    counts = p["type_counts"]
    if not counts:
        return None
    ranked = counts.most_common()
    n = p["n"]
    if len(ranked) == 1 and ranked[0][1] == n and n > 1:
        label = plural_label(tables.TYPE_LABELS[ranked[0][0]], n)
        return finish(f"All {comma(n)} are {label}")
    chunks = []
    for code, count in ranked[:3]:
        label = tables.TYPE_LABELS[code]
        if count == 1:
            chunks.append(f"one {label}")
        else:
            chunks.append(f"{comma(count)} {plural_label(label, count)}")
    if len(ranked) > 3 and ranked[3][1] >= 3:
        options = [
            finish("Types recorded include " + join_and(chunks) + ". Other types are recorded as well"),
            finish(join_and(chunks).capitalize() + " are the types with the most records. Other types are recorded as well"),
        ]
    else:
        options = [
            finish("Types recorded include " + join_and(chunks)),
            finish(join_and(chunks).capitalize() + " are the types recorded"),
        ]
    top_code, top_count = ranked[0]
    if top_count > 1 and top_count / n >= 0.6:
        label = plural_label(tables.TYPE_LABELS[top_code], top_count)
        alt = f"{label.capitalize()} are recorded for {comma(top_count)} of the {comma(n)} hillforts"
        if len(ranked) > 1:
            code2, count2 = ranked[1]
            label2 = tables.TYPE_LABELS[code2]
            if count2 == 1:
                alt += f", and one {label2} is recorded as well"
            else:
                alt += f", and {plural_label(label2, count2)} for {comma(count2)}"
        options.append(finish(alt))
    return pick(p["key"], "types", options)


def condition_sentence(p):
    n = p["n"]
    extant, crop, destroyed = p["extant"], p["cropmark"], p["destroyed"]
    both_ed = p["both_extant_destroyed"]
    both_ec = p["both_extant_crop"]
    if extant + crop + destroyed == 0:
        return None
    if extant == n and crop == 0 and destroyed == 0:
        return finish(f"All {nforts(n)} are recorded as extant")
    if extant == n and n > 1:
        extras = []
        if destroyed and both_ed == destroyed:
            extras.append(
                "one of them is also marked likely destroyed"
                if destroyed == 1
                else f"{comma(destroyed)} of them are also marked likely destroyed"
            )
        elif destroyed:
            extras.append(f"likely destroyed is recorded for {nforts(destroyed)}")
        if crop and both_ec == crop:
            extras.append(
                "one of them is also marked as a cropmark"
                if crop == 1
                else f"{comma(crop)} of them are also marked as cropmarks"
            )
        elif crop:
            extras.append(f"a cropmark is recorded for {nforts(crop)}")
        sentence = f"All {comma(n)} are recorded as extant"
        if extras:
            sentence += ", and " + join_and(extras)
        return finish(sentence)

    parts = []
    if crop:
        parts.append(("cropmark", crop))
    if extant:
        parts.append(("extant", extant))
    if destroyed:
        parts.append(("likely destroyed", destroyed))
    parts.sort(key=lambda item: (-item[1], item[0]))

    def on_phrase(label, count):
        if label == "cropmark":
            return f"a cropmark on {nforts(count)}"
        if label == "likely destroyed":
            return f"likely destroyed on {nforts(count)}"
        return f"extant on {nforts(count)}"

    def ellipsis(label, count, first):
        if label == "cropmark":
            shown = "a cropmark" if count == 1 else "cropmarks"
        elif label == "likely destroyed":
            shown = "likely destroyed"
        else:
            shown = "extant"
        if first:
            if count == 1:
                return f"One hillfort is recorded as {shown}"
            return f"{comma(count)} hillforts are recorded as {shown}"
        if count == 1:
            return f"one as {shown}"
        return f"{comma(count)} as {shown}"

    inventory = "Condition is recorded as " + join_and(on_phrase(label, count) for label, count in parts)
    listed = join_and(ellipsis(label, count, index == 0) for index, (label, count) in enumerate(parts))
    overlap = []
    if both_ed >= 5 and both_ed < destroyed:
        overlap.append(f"{comma(both_ed)} are marked both extant and likely destroyed")
    if both_ec >= 5 and both_ec < crop:
        overlap.append(f"{comma(both_ec)} are marked both extant and a cropmark")
    options = [inventory, listed]
    if overlap:
        extra = ". ".join(sentence[0].upper() + sentence[1:] for sentence in overlap)
        options = [option + ". " + extra for option in options]
    return pick(p["key"], "condition", [finish(option) for option in options])


def dating_sentence(p):
    dated = p["dated"]
    if dated <= 0:
        return None
    ranked = p["period_counts"].most_common(3)
    if dated == 1 and ranked:
        return finish(f"A period is recorded for one hillfort: {ranked[0][0]}")
    bits = []
    for label, count in ranked:
        noun = "record" if count == 1 else "records"
        bits.append(f"{label} ({comma(count)} {noun})")
    if len(bits) == 1:
        period_clause = bits[0]
    else:
        period_clause = bits[0] + ", then " + join_and(bits[1:])
    sparse = p["n"] >= 20 and dated / p["n"] < 0.15
    if dated == p["n"]:
        quant = f"all {comma(p['n'])} hillforts"
    elif sparse:
        quant = f"only {comma(dated)} of the {comma(p['n'])} hillforts"
    else:
        quant = f"{comma(dated)} of the {comma(p['n'])} hillforts"
    period_bits = []
    for label, count in ranked:
        period_bits.append(f"{label} on {nforts(count)}")
    options = [
        finish(f"A period is recorded for {quant}, led by {period_clause}"),
        finish(f"{quant[:1].upper()}{quant[1:]} {'has' if dated == 1 else 'have'} a recorded period: {join_and(period_bits)}"),
    ]
    return pick(p["key"], "dating", options)


def reliability_sentence(p):
    k = p["reliable"]
    if k < 3:
        return None
    if p["dated"] and k / p["dated"] < 0.25 and k < 8:
        return None
    return finish(f"Dating reliability is recorded as high or medium for {nforts(k)}")


def morph_sentence(p):
    buckets = p["morph_buckets"]
    partial = p["morph_partial"]
    present = [key for key in ("univallate", "bivallate", "multivallate") if buckets.get(key)]
    if not present:
        return None
    bits = []
    for key in present:
        count = buckets[key]
        part = partial.get(key, 0)
        if count == 1:
            word = f"partial {key}" if part else key
            bits.append(f"{word} on one hillfort")
        elif part <= 0:
            bits.append(f"{key} on {comma(count)} hillforts")
        elif part == count:
            bits.append(f"partial {key} on {comma(count)} hillforts")
        else:
            bits.append(f"{key} on {comma(count)} hillforts, {comma(part)} of them partial")
    paren = []
    for key in present:
        count = buckets[key]
        part = partial.get(key, 0)
        if count == 1:
            paren.append(f"{'partial ' if part else ''}{key} on one hillfort")
        elif part and part != count:
            paren.append(f"{key} on {comma(count)} hillforts ({comma(part)} partial)")
        elif part == count:
            paren.append(f"partial {key} on {comma(count)} hillforts")
        else:
            paren.append(f"{key} on {comma(count)} hillforts")
    if len(bits) == 1:
        forms = [finish("Rampart form is " + bits[0])]
    else:
        forms = [
            finish("Rampart form is " + "; ".join(bits[:-1]) + "; and " + bits[-1]),
            finish("The rampart record shows " + join_and(paren)),
        ]
    return pick(p["key"], "morph", forms)


def scheduled_sentence(p):
    count = p["scheduled"]
    if count <= 0:
        return None
    if count == p["n"] and count > 1:
        return finish(f"A scheduled monument number is recorded for each of the {comma(count)} hillforts")
    return finish(f"A scheduled monument number is recorded for {nforts(count)}")


def topo_sentence(p):
    tables = _tables()
    ranked = p["topo_counts"].most_common(2)
    if not ranked:
        return None
    if ranked[0][1] < 2 and p["n"] > 4:
        return None

    def bit(code, count):
        label = tables.TOPO_LABELS[code]
        if code == "lowland":
            return f"a lowland setting for {nforts(count)}"
        return f"{label} for {nforts(count)}"

    options = [finish("Topographic positions are recorded as " + join_and(bit(code, count) for code, count in ranked))]
    code, count = ranked[0]
    label = tables.TOPO_LABELS[code]
    if code == "lowland":
        lead = f"A lowland setting is the position most often recorded, for {nforts(count)}"
    else:
        lead = f"{label.capitalize()} is the position most often recorded, for {nforts(count)}"
    if len(ranked) > 1 and ranked[1][1] >= 2:
        lead += ", followed by " + bit(ranked[1][0], ranked[1][1])
    options.append(finish(lead))
    return pick(p["key"], "topo", options)


def landuse_sentence(p):
    tables = _tables()
    ranked = p["land_counts"].most_common(2)
    if not ranked:
        return None
    if ranked[0][1] < 2 and p["n"] > 3:
        return None
    code, count = ranked[0]
    label = tables.LANDUSE_LABELS[code]
    if len(ranked) == 1 or ranked[1][1] < 2:
        return finish(f"The land use most often recorded is {label}, on {nforts(count)}")
    code2, count2 = ranked[1]
    return finish(
        f"Recorded land use is most often {label} ({nforts(count)}), then {tables.LANDUSE_LABELS[code2]} ({nforts(count2)})"
    )


def surface_sentence(p):
    tables = _tables()
    ranked = [(code, count) for code, count in p["surface_counts"].most_common() if code != "vitrification"]
    if not ranked:
        return None
    if ranked[0][1] < 2 and p["n"] > 3:
        return None
    bits = []
    for code, count in ranked[:2]:
        if count < 2 and len(bits) > 0:
            continue
        bits.append(f"{tables.SURFACE_LABELS[code]} on {nforts(count)}")
    if not bits:
        return None
    return finish("Visible enclosing works include " + join_and(bits))


def altitude_sentence(p):
    altitudes = p["altitudes"]
    if not altitudes:
        return None
    lo, hi = min(altitudes), max(altitudes)
    if len(altitudes) == 1 or lo == hi:
        return finish(f"The recorded altitude is {format_number(lo)} m")
    if hi - lo < 40 and len(altitudes) >= 4:
        options = [
            finish(f"Recorded altitudes sit between {format_number(lo)} m and {format_number(hi)} m"),
            finish(f"The altitudes on record run only from {format_number(lo)} m to {format_number(hi)} m"),
        ]
        return pick(p["key"], "alt", options)
    return finish(f"Recorded altitudes run from {format_number(lo)} m to {format_number(hi)} m")


def investigation_sentence(p):
    n = p["n"]
    exc, geo, earth = p["excavation"], p["geophysical"], p["earthwork"]
    if exc >= 1 and (exc >= 3 or exc / n >= 0.08 or n <= 25):
        return finish(f"An excavation is listed for {nforts(exc)}")
    if geo >= 2:
        return finish(f"A geophysical survey is listed for {nforts(geo)}")
    if earth >= 8 and earth / n >= 0.25:
        return finish(f"An earthwork survey is listed for {nforts(earth)}")
    return None


def feature_sentence(p):
    options = []
    if p["vitrification"]:
        options.append(finish(f"Vitrification is recorded on {nforts(p['vitrification'])}"))
    if p["chevaux"]:
        options.append(finish(f"Chevaux de frise are recorded at {nforts(p['chevaux'])}"))
    if p["guards"]:
        options.append(finish(f"Guard chambers are recorded at {nforts(p['guards'])}"))
    if not options:
        return None
    return pick(p["key"], "feature", options)


def describe_named(site, group) -> str:
    tables = _tables()
    name = distinctive_name(site, group)
    type_labels = labels(site.get("types"), tables.TYPE_LABELS)
    morphs = [label for label in labels(site.get("morph"), tables.MORPH_LABELS) if label != "unknown"]
    kind_parts = []
    if morphs:
        kind_parts.append(join_and(morphs))
    if type_labels:
        kind_parts.append(join_and(type_labels))
    kind = " ".join(kind_parts) or "hillfort"
    sentence = f"{name} is {article(kind)}"
    cond = condition_phrase(site.get("condition"))
    if cond:
        sentence += f", {cond}"
    if isinstance(site.get("enclosed"), (int, float)):
        sentence += f", with an enclosed area of {format_number(site['enclosed'])} hectares"
    setting = setting_phrase(site, tables.TOPO_LABELS)
    if setting:
        sentence += f", {setting}"
    sentence = finish(sentence)
    periods = period_labels(site, tables.PERIOD_LABELS)
    if periods:
        sentence += " " + finish(f"Dating is recorded for {join_and(periods)}")
    if site.get("scheduled"):
        sentence += " " + finish(f"Scheduled monument number {site['scheduled']} is recorded")
    return sentence


def named_sentence(p):
    ordered = sorted(p["sites"], key=lambda site: site["name"].lower())
    return " ".join(describe_named(site, p["sites"]) for site in ordered)


def choose_frame(p) -> str:
    options = ["catalogue"]
    n = p["n"]
    if n >= 80:
        options.append("scale")
    if p["max_area"] and p["median_area"] and p["max_area"] >= 10 and p["max_area"] >= 4 * p["median_area"]:
        options.append("monument")
    if p["cropmark"] / n >= 0.28 or p["destroyed"] / n >= 0.28:
        options.append("survival")
    if p["promontory_share"] >= 0.4 or p["coastal_share"] >= 0.35:
        options.append("coast")
    if p["dated"] >= 5 and p["dated"] / n >= 0.35:
        options.append("dating")
    if p["stone"] >= 3 and p["stone"] / n >= 0.3:
        options.append("stone")
    return pick(p["key"], "frame", options)


def slot_sentences(p, tiny: bool) -> dict:
    slots = {
        "open": opening_sentence(p),
        "introductions": introductions_sentence(p),
        "size": None if tiny else size_sentence(p),
        "second": None if tiny else second_sentence(p),
        "types": None if tiny else type_sentence(p),
        "condition": None if tiny else condition_sentence(p),
        "dating": None if tiny else dating_sentence(p),
        "reliability": None if tiny else reliability_sentence(p),
        "morph": None if tiny else morph_sentence(p),
        "scheduled": None if tiny else scheduled_sentence(p),
        "topo": None if tiny else topo_sentence(p),
        "landuse": None if tiny else landuse_sentence(p),
        "surface": None if tiny else surface_sentence(p),
        "altitude": None if tiny else altitude_sentence(p),
        "investigation": None if tiny else investigation_sentence(p),
        "feature": None if tiny else feature_sentence(p),
        "named": named_sentence(p) if tiny else None,
    }
    return slots


def assemble(p) -> tuple[list[str], int]:
    full = p["indexed_n"] >= FULL_INDEXED_MIN
    tiny = p["n"] <= 2
    frame = choose_frame(p)
    slots = slot_sentences(p, tiny)
    frame_order = {
        "catalogue": ["open", "introductions", "size", "types", "condition", "morph", "dating"],
        "scale": ["open", "size", "types", "condition", "introductions", "morph", "dating"],
        "monument": ["open", "size", "second", "types", "condition", "introductions", "dating", "morph"],
        "survival": ["open", "condition", "types", "size", "introductions", "dating", "morph"],
        "coast": ["open", "types", "topo", "size", "condition", "introductions", "morph", "dating"],
        "dating": ["open", "dating", "size", "types", "condition", "introductions", "morph"],
        "stone": ["open", "surface", "types", "size", "condition", "introductions", "morph", "dating"],
    }[frame]
    if full:
        core = {"open", "introductions", "size", "types", "condition", "morph", "dating"}
        if frame == "monument":
            core.add("second")
        if frame == "coast":
            core.add("topo")
        if frame == "stone":
            core.add("surface")
        soft_lo, hard_hi = WORD_FULL
        target = 148 + crc(p["key"], "len") % 36
    elif tiny:
        core = {"open", "named", "introductions"}
        soft_lo, hard_hi = 24, WORD_SHORT_MAX
        target = 64
    elif p["n"] >= 12:
        core = {"open", "introductions", "size", "types", "condition"}
        soft_lo, hard_hi = 70, WORD_SHORT_MAX
        target = 84 + crc(p["key"], "len") % 22
    else:
        core = {"open", "introductions", "size", "types", "condition"}
        soft_lo, hard_hi = 40, WORD_SHORT_MAX
        target = 58 + crc(p["key"], "len") % 24

    rest = [
        "second", "dating", "morph", "scheduled", "topo", "landuse", "surface",
        "altitude", "investigation", "feature", "reliability", "named",
    ]
    rot = crc(p["key"], "rot") % len(rest)
    rest = rest[rot:] + rest[:rot]
    ordered = []
    for slot in ["open"] + frame_order + rest:
        if slot not in ordered:
            ordered.append(slot)

    chosen = []
    for slot in ordered:
        if slot not in core:
            continue
        sentence = slots.get(slot)
        if sentence and sentence not in chosen:
            chosen.append(sentence)
    words = word_count(" ".join(chosen))
    for slot in ordered:
        if slot in core:
            continue
        sentence = slots.get(slot)
        if not sentence or sentence in chosen:
            continue
        extra = word_count(sentence)
        if words >= target or words + extra > hard_hi:
            continue
        chosen.append(sentence)
        words += extra
    while words > hard_hi and len(chosen) > 1:
        words -= word_count(chosen[-1])
        chosen.pop()
    if words < soft_lo:
        for slot in ordered:
            sentence = slots.get(slot)
            if not sentence or sentence in chosen:
                continue
            extra = word_count(sentence)
            if words + extra <= hard_hi:
                chosen.append(sentence)
                words += extra
            if words >= soft_lo:
                break
    paragraphs = paragraphise(chosen, p["key"])
    text = " ".join(paragraphs)
    return paragraphs, word_count(text)


def paragraphise(sentences, key) -> list[str]:
    sentences = [sentence.strip() for sentence in sentences if sentence and sentence.strip()]
    if not sentences:
        return []
    if len(sentences) <= 3:
        return [" ".join(sentences)]
    if len(sentences) <= 5:
        cut = 3 if crc(key, "para") % 2 and len(sentences) >= 4 else 2
        cut = min(cut, len(sentences) - 1)
        return [" ".join(sentences[:cut]), " ".join(sentences[cut:])]
    if len(sentences) >= 7 and crc(key, "three") % 2 == 0:
        first = 2 + (crc(key, "c1") % 2)
        second = first + max(2, (len(sentences) - first) // 2)
        second = min(second, len(sentences) - 1)
        if second <= first:
            second = first + 1
        return [
            " ".join(sentences[:first]),
            " ".join(sentences[first:second]),
            " ".join(sentences[second:]),
        ]
    cut = 2 + (crc(key, "cut") % 3)
    cut = min(max(2, cut), len(sentences) - 2)
    return [" ".join(sentences[:cut]), " ".join(sentences[cut:])]


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
    tables = _tables()
    type_labels = labels(site.get("types"), tables.TYPE_LABELS)
    morphs = [label for label in labels(site.get("morph"), tables.MORPH_LABELS) if label != "unknown"]
    both_partial = (
        len(morphs) == 1
        and len(type_labels) == 1
        and morphs[0].startswith("partial")
        and type_labels[0].startswith("partial")
    )
    if len(morphs) == 1 and len(type_labels) == 1 and not both_partial:
        kind = f"{morphs[0]} {type_labels[0]}"
    elif morphs and type_labels:
        kind = f"{join_and(type_labels)} with {join_and(morphs)} ramparts"
    elif type_labels:
        kind = join_and(type_labels)
    elif morphs:
        kind = join_and(morphs) + " hillfort"
    else:
        kind = "hillfort"
    cond = condition_phrase(site.get("condition"))
    setting = setting_phrase(site, tables.TOPO_LABELS)
    periods = period_labels(site, tables.PERIOD_LABELS)
    surfaces = labels(site.get("surface"), tables.SURFACE_LABELS)[:2]
    entrances = site.get("entrances")
    extras = []
    if periods:
        extras.append("with dating recorded for " + join_and(periods))
    if isinstance(entrances, int) and entrances > 0:
        noun = "entrance" if entrances == 1 else "entrances"
        small = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
        number = small[entrances - 1] if 1 <= entrances <= 9 else comma(entrances)
        extras.append(f"with {number} possible original {noun}")
    if surfaces:
        mass = {"rubble", "vitrification", "timber", "other burning", "unfinished work"}
        bits = [surface if surface in mass else article(surface) for surface in surfaces]
        extras.append("with " + join_and(bits))
    extra = pick(site["slug"], "fact-extra", extras + [None]) if extras else None
    use_lead = pick(site["slug"], "fact-shape", ("it", "recorded"))
    if use_lead == "recorded" and cond:
        sentence = f"{cond[:1].upper()}{cond[1:]}, it is {article(kind)}"
    else:
        sentence = f"It is {article(kind)}"
        if cond:
            sentence += f", {cond}"
    if setting:
        sentence += f", {setting}"
    if extra and word_count(sentence + " " + extra) <= 40:
        sentence += f", {extra}"
    return finish(sentence)


def size_label(site) -> str:
    if isinstance(site.get("enclosed"), (int, float)):
        return f"{format_number(site['enclosed'])} ha"
    if isinstance(site.get("footprint"), (int, float)):
        return f"footprint {format_number(site['footprint'])} ha"
    return ""


def stats_rows(p) -> list[tuple[str, str, str]]:
    rows = [("Hillforts", comma(p["n"]), "")]
    if p["indexed_n"]:
        rows.append(("With an introduction", comma(p["indexed_n"]), ""))
    if p["largest"]:
        rows.append((
            "Largest enclosed area",
            f"{format_number(p['max_area'])} ha",
            name_list(p["largest"], p["sites"], limit=2),
        ))
    if p["extant"]:
        rows.append(("Recorded as extant", comma(p["extant"]), ""))
    if p["scheduled"]:
        rows.append(("Scheduled monument", comma(p["scheduled"]), ""))
    return rows


def meta_description(p, has_best: bool) -> str:
    where = where_plain(p["kind"], p["name"], p["country"])
    lead_n = nforts(p["n"])
    visit = " Includes hillforts to visit." if has_best else ""
    largest = ""
    if p["largest"]:
        largest = f" Largest enclosed area: {name_list(p['largest'], p['sites'], limit=1)}, {format_number(p['max_area'])} ha."
    options = [
        f"Directory of {lead_n} in {where} from the Atlas of Hillforts of Britain and Ireland.{largest}{visit}",
        f"{lead_n.capitalize()} in {where}, with type, condition, and enclosed area from the Atlas of Hillforts.{visit}",
        f"{heading(p['kind'], p['name'])}: {lead_n} from the Atlas of Hillforts of Britain and Ireland.{largest}",
    ]
    text = pick(p["key"], "meta", options)
    if len(text) > 185:
        text = f"{lead_n.capitalize()} in {where} from the Atlas of Hillforts of Britain and Ireland.{visit}"
    return " ".join(text.split())


def json_ld(p, best, description, canonical, h1) -> dict:
    code = COUNTRY_CODE[p["country"] if p["kind"] == "county" else p["name"]]
    place = {"@type": "Place", "name": p["name"]}
    if p["kind"] == "county":
        place["address"] = {
            "@type": "PostalAddress",
            "addressRegion": p["name"],
            "addressCountry": code,
        }
        place["containedInPlace"] = {"@type": "Place", "name": p["country"]}
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
            "name": best_heading(p["name"]),
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


def hub_content(sites, *, kind, name, country, slug, nation_slug, canonical) -> dict:
    profile = build_profile(sites, kind=kind, name=name, country=country, slug=slug)
    paragraphs, words = assemble(profile)
    full = profile["indexed_n"] >= FULL_INDEXED_MIN
    if full and not (WORD_FULL[0] <= words <= WORD_FULL[1]):
        raise RuntimeError(f"{slug} intro is {words} words; expected {WORD_FULL[0]}–{WORD_FULL[1]}")
    if not full and not (20 <= words <= WORD_SHORT_MAX):
        raise RuntimeError(f"{slug} short intro is {words} words")
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
    prose = '<div class="hub-intro">' + "".join(f"<p>{esc(paragraph)}</p>" for paragraph in paragraphs) + "</div>"
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
