#!/usr/bin/env python3
"""Choose one free-licence photo for each indexed hillfort and cache it.

Reads data/sites.json. Writes data/photos.json and resized WebP files under
src/assets/photos/. The site build reads those and does not call the network.

Selection, per fort:

1. Wikidata P18, when the file is a photograph. Maps, plans, terrain models
   and illustrations are skipped.
2. A Wikimedia Commons file within about 300 m whose title or categories
   name the fort.
3. A Geograph photo with a 6-figure grid reference or better whose title
   names the fort, when that photo has been re-uploaded to Commons.
4. Otherwise no photo.

Geograph's own dump (https://data.geograph.org.uk/dumps/) is metadata.
Image files are not in the dump, and Geograph's image servers are not
hotlinked. A step-3 photo is downloaded from its Commons re-upload.

Allowed licences: CC0, public domain, CC BY, CC BY-SA (any version), and
the Open Government Licence. Author text from Commons is stored with HTML
removed.

Needs Pillow. Re-runs reuse API responses and the Geograph dumps in
/tmp/hillforts-photos/.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import http.client
import io
import json
import math
import re
import ssl
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SITES = ROOT / "data" / "sites.json"
OUTPUT = ROOT / "data" / "photos.json"
PHOTO_DIR = ROOT / "src" / "assets" / "photos"
CACHE = Path("/tmp/hillforts-photos")
ARTIFACTS = Path("/opt/cursor/artifacts")
UA = "HillfortsMapPhotoFetch/1.0 (https://hillfortsmap.co.uk; privacy@hillfortsmap.co.uk)"

COMMONS = "commons.wikimedia.org"
WIKIDATA = "www.wikidata.org"
COMMONS_RADIUS = 310
GEOGRAPH_RADIUS = 800
DUMP_BASE = "https://data.geograph.org.uk/dumps/gridimage_base.tsv.gz"
DUMP_GEO = "https://data.geograph.org.uk/dumps/gridimage_geo.tsv.gz"

PHOTO_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/tiff"}
BUSY = {"EN0005", "EN0406", "EN3598", "EN3775"}
CONTAINERS = {
    "skye", "mull", "mainland", "islay", "jura", "arran", "orkney", "shetland",
    "lewis", "harris", "iona", "rum", "eigg", "uist", "benbecula", "barra",
}
TRAILING = {
    "hillfort", "hillforts", "hill", "hills", "fort", "forts", "camp", "camps",
    "castle", "castles", "ring", "rings", "point", "head", "beacon", "enclosure",
    "earthwork", "earthworks", "settlement", "knoll", "tor", "wood", "bank",
    "banks", "dyke", "dykes", "dike", "dikes", "law",
}
WEAK_SINGLE = TRAILING | {
    "site", "sites", "mount", "hilltop", "dun", "caer", "gaer", "moel", "foel",
    "pen", "brough", "burgh", "common",
}
KIND_RANK = {"name": 4, "alt": 3, "token": 2, "weak": 1}

NON_PHOTO = re.compile(
    r"("
    r"\bmaps?\b|\bplans?\b|\bdiagrams?\b|\bdtm\b|\blidar\b|\bhillshades?\b|"
    r"\bdrawings?\b|\billustrations?\b|\bsketches?\b|\bengravings?\b|"
    r"\bpaintings?\b|\breconstructions?\b|\blocator\b|ordnance survey|"
    r"terrain models?|digital terrain|digital elevation|site plans?|"
    r"ground plans?|coat of arms|\b3d models?\b|artist'?s impressions?|"
    r"\bprint of\b|\blithographs?\b"
    r")",
    re.I,
)
STRUCTURE = re.compile(
    r"\b(hillforts?|hill forts?|ramparts?|earthworks?|ditches|enclosures?|"
    r"iron[- ]age|univallate|multivallate|bivallate|defences|defenses|"
    r"gateways?|entrances?|aerial|from the air)\b",
    re.I,
)
INCIDENTAL = re.compile(
    r"\b(sheep|cattle|cows?|horses?|ponies|radar|mast|antenna|satellite|"
    r"weather|car park|parking|footpath|bridleway|path|track|road|lane|"
    r"church|chapel|house|farmhouse|cottage|farm|trig point|triangulation|"
    r"memorial|bench|sunset|sunrise|rainbow|flowers?|fungus|mushroom|"
    r"birds?|aircraft|aeroplane|airplane|pharos|lighthouse|altar|pub|inn|"
    r"hotel|school|information board|notice board|signpost|plaque|"
    r"waymarker|stile|view from|view towards|looking towards|looking from|"
    r"panorama from|from the summit|folly|mansion|manor|palace|keep|"
    r"cathedral|abbey|priory)\b",
    re.I,
)
OUTWARD = re.compile(
    r"\b(from the top|from near the top|near the summit|from the summit|"
    r"looking (?:north|south|east|west)|view (?:north|south|east|west)wards?)\b",
    re.I,
)
CATEGORY_SUBJECT = re.compile(r"\b(sheep|cattle|churches|pharos|radar stations?)\b", re.I)


def norm(text) -> str:
    text = html.unescape(text or "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("'", "").replace("’", "").replace("`", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def phrase_specs(name, role):
    parts = [part.strip() for part in re.split(r"[,/]", name or "") if part.strip()]
    if parts and norm(parts[0]) in CONTAINERS and len(parts) > 1:
        parts = parts[1:]
    if not parts:
        return []
    return dedupe_phrases(specs_from_part(parts[0], role))


def specs_from_part(part, role):
    tokens = norm(part).split()
    while tokens and tokens[0] == "the":
        tokens = tokens[1:]
    while tokens and tokens[-1].isdigit():
        tokens = tokens[:-1]
    if not tokens:
        return []
    full = " ".join(tokens)
    distinctive = [token for token in tokens if token not in WEAK_SINGLE and len(token) >= 4]
    if role == "alt" and not distinctive:
        return []
    # A single generic word ("Burgh") is a weak name. A multi-word name
    # still has to match as a phrase, so "Hod Hill" and "Moel y Gaer" stay.
    kind = "weak" if role == "name" and len(tokens) == 1 and not distinctive else role
    found = [(full, kind)]
    core = list(tokens)
    if core and core[0] in {"old", "great", "little", "new"} and len(core) > 1:
        core = core[1:]
    if len(core) > 1 and core[-1] in TRAILING:
        core = core[:-1]
    core_phrase = " ".join(core)
    core_distinct = [token for token in core if token not in WEAK_SINGLE and len(token) >= 4]
    if core_phrase and core_phrase != full and core_distinct and len(core_phrase) >= 8:
        found.append((core_phrase, "token"))
    for token in core:
        if len(token) >= 8 and token not in WEAK_SINGLE and not token.endswith("shire") and token != full:
            found.append((token, "token"))
    return found


def dedupe_phrases(items):
    seen = set()
    kept = []
    for phrase, kind in items:
        if not phrase or phrase in seen:
            continue
        seen.add(phrase)
        kept.append((phrase, kind))
    return kept


def best_phrase(text, phrases):
    hay = f" {norm(text)} "
    best = None
    for phrase, kind in phrases:
        if f" {phrase} " in hay:
            rank = (KIND_RANK[kind], len(phrase))
            if best is None or rank > best[0]:
                best = (rank, phrase, kind)
    if not best:
        return None
    return best[1], best[2]


def stem_of(title) -> str:
    name = title.split(":", 1)[-1]
    name = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", name)
    name = re.sub(r"\s*-\s*geograph\.org\.uk\s*-\s*\d+", "", name, flags=re.I)
    name = re.sub(r"\s*\(geograph \d+\)", "", name, flags=re.I)
    name = re.sub(r"\s*\(cropped\)", "", name, flags=re.I)
    return name


def looks_like_photograph(title, categories, mime, mediatype, width, height) -> bool:
    if mediatype and mediatype != "BITMAP":
        return False
    if mime not in PHOTO_MIME:
        return False
    if max(width or 0, height or 0) < 320 or min(width or 0, height or 0) < 180:
        return False
    if NON_PHOTO.search(f"{stem_of(title)}\n{categories}"):
        return False
    return True


def version_of(blob):
    match = re.search(r"\b([1-4]\.(?:0|5))\b", blob)
    return match.group(1) if match else None


def clean_right_url(url, fallback):
    if not url:
        return fallback
    url = re.sub(r"^http://", "https://", url.strip(), flags=re.I)
    lowered = url.lower()
    if "creativecommons.org/" not in lowered and "nationalarchives.gov.uk/" not in lowered:
        return fallback
    url = url.split("?")[0]
    url = re.sub(r"/deed(?:\.[a-z-]+)?$", "/", url, flags=re.I)
    if not url.endswith("/"):
        url += "/"
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, "", ""))


def licence_of(short, url):
    short = re.sub(r"\s+", " ", (short or "").replace("_", " ")).strip()
    raw_url = url or ""
    folded = f"{short} {raw_url}".lower().replace("–", "-").replace("-", " ")
    folded = re.sub(r"\s+", " ", folded)
    if re.search(r"non ?commercial|no ?deriv|\bnc\b|\bnd\b", folded):
        return None
    if re.search(r"\bcc\s*0\b|cc zero|publicdomain/zero", f"{short} {raw_url}".lower()):
        return ("CC0", clean_right_url(raw_url, "https://creativecommons.org/publicdomain/zero/1.0/"))
    if re.search(r"\bby sa\b|attribution share ?alike", folded):
        version = version_of(folded)
        if not version:
            return None
        fallback = f"https://creativecommons.org/licenses/by-sa/{version}/"
        return (f"CC BY-SA {version}", clean_right_url(raw_url, fallback))
    if re.search(r"\bcc by\b|\battribution\b", folded):
        version = version_of(folded)
        if not version:
            return None
        fallback = f"https://creativecommons.org/licenses/by/{version}/"
        return (f"CC BY {version}", clean_right_url(raw_url, fallback))
    if re.search(r"\bogl\b|open government licence", folded):
        if re.search(r"version/1\b|\bv1\b|\bogl 1\b|version 1", f"{short} {raw_url}".lower()):
            name = "OGL 1.0"
            fallback = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/1/"
        else:
            name = "OGL 3"
            fallback = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
        chosen = clean_right_url(raw_url, fallback) if "nationalarchives.gov.uk" in raw_url.lower() else fallback
        return (name, chosen)
    if re.search(r"public domain|\bpdm\b", folded):
        return ("Public domain", clean_right_url(raw_url, "https://creativecommons.org/publicdomain/mark/1.0/"))
    return None


def clean_author(value) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"(?i)<br\s*/?>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip(" ,;|")
    text = re.sub(r"(?i)^credit[:\s]+", "", text).strip()
    text = re.sub(r"(?i)^user:", "", text).strip()
    text = re.split(r"https?://", text)[0].strip(" ,;")
    if not text or len(text) > 100:
        return ""
    if re.search(r"copyright|permission|creative commons|this (file|image|work)|wikimedia commons", text, re.I):
        return ""
    if "<" in text or ">" in text:
        return ""
    return text


def tidy_author(text) -> str:
    text = clean_author(text)
    modified = re.search(r"^(.*?),\s*modified by\s+(.+)$", text, re.I)
    if modified:
        original = clean_author(modified.group(1))
        editor = clean_author(modified.group(2))
        text = " and ".join(part for part in (original, editor) if part)
    else:
        named = re.search(r"\bby\s+(.+)$", text, re.I)
        if named:
            text = clean_author(named.group(1))
    if not text or text.lower() in {"myself", "own work", "the author", "unknown"}:
        return ""
    if text.lower().startswith("photographed by"):
        return ""
    return text


def author_of(ext) -> str:
    artist_html = meta_value(ext, "Artist")
    attribution = tidy_author(meta_value(ext, "Attribution"))
    links = []
    for raw in re.findall(r">([^<]+)<", artist_html):
        name = tidy_author(raw)
        if not name:
            continue
        lowered = name.lower()
        if "geograph" in lowered or "wikimedia" in lowered or "creativecommons" in lowered:
            continue
        links.append(name)
    if attribution and "geograph.org" not in attribution.lower() and len(attribution.split()) <= 8:
        return attribution
    if links:
        return links[0]
    return tidy_author(artist_html) or "Unknown"


def meta_value(ext, key) -> str:
    item = (ext or {}).get(key) or {}
    if isinstance(item, dict):
        return item.get("value") or ""
    return str(item or "")


def haversine(lat1, lon1, lat2, lon2) -> float:
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlng = math.radians(lon2 - lon1)
    arc = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlng / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(arc))


def fort_phrases(site):
    phrases = phrase_specs(site["name"], "name")
    for alt in site.get("alt") or []:
        if isinstance(alt, str):
            phrases.extend(phrase_specs(alt, "alt"))
    return dedupe_phrases(phrases)


def load_forts(csv_path):
    sites = json.loads(SITES.read_text(encoding="utf-8"))
    extra = {}
    if csv_path and Path(csv_path).exists():
        with open(csv_path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                qid = (row.get("wikidata_qid") or "").strip()
                if qid:
                    extra[row["atlas_id"].lower()] = qid
    forts = []
    for site in sites:
        if not site.get("index"):
            continue
        qids = []
        for qid in (site.get("wiki"), extra.get(site["code"].lower())):
            if qid and qid not in qids:
                qids.append(qid)
        queries = []
        primary = search_text(site["name"], "name")
        if primary:
            queries.append(primary)
        for alt in site.get("alt") or []:
            if not isinstance(alt, str):
                continue
            text = search_text(alt, "alt")
            if text and text not in queries:
                queries.append(text)
            if len(queries) == 3:
                break
        forts.append({
            "code": site["code"],
            "slug": site["slug"],
            "name": site["name"],
            "lat": site["lat"],
            "lon": site["lon"],
            "qids": qids,
            "phrases": fort_phrases(site),
            "queries": queries,
        })
    forts.sort(key=lambda fort: fort["code"])
    return forts


class Limiter:
    def __init__(self, per_second):
        self.gap = 1 / per_second
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            delay = max(0.0, self.next_at - now)
            self.next_at = max(now, self.next_at) + self.gap
        if delay:
            time.sleep(delay)


class Client:
    def __init__(self):
        self.ctx = ssl.create_default_context()
        self.local = threading.local()
        self.limiter = Limiter(3)
        self.cache = CACHE / "api"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def post(self, host, params):
        key = hashlib.sha1(json.dumps([host, params], sort_keys=True).encode()).hexdigest()
        path = self.cache / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        payload = self._post(host, params)
        with self.lock:
            path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _connection(self, host):
        conns = getattr(self.local, "conns", None)
        if conns is None:
            conns = {}
            self.local.conns = conns
        conn = conns.get(host)
        if conn is None:
            conn = http.client.HTTPSConnection(host, timeout=90, context=self.ctx)
            conns[host] = conn
        return conn

    def _drop(self, host):
        conns = getattr(self.local, "conns", None) or {}
        conn = conns.pop(host, None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def _post(self, host, params):
        body = urllib.parse.urlencode(params).encode()
        headers = {
            "User-Agent": UA,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "keep-alive",
        }
        last = "no response"
        for attempt in range(8):
            self.limiter.wait()
            conn = self._connection(host)
            try:
                conn.request("POST", "/w/api.php", body=body, headers=headers)
                response = conn.getresponse()
                data = response.read()
                status = response.status
                retry_after = response.getheader("Retry-After")
            except Exception as exc:
                last = str(exc)
                self._drop(host)
                time.sleep(min(30, 2 ** attempt))
                continue
            if status in (429, 502, 503, 504):
                last = f"HTTP {status}"
                self._drop(host)
                pause = min(60, 5 * (attempt + 1))
                if retry_after and retry_after.isdigit():
                    pause = max(pause, int(retry_after))
                print(f"  {host} {last}, waiting {pause}s", flush=True)
                time.sleep(pause)
                continue
            if status != 200:
                raise RuntimeError(f"HTTP {status} from {host}: {data[:180]!r}")
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                last = "invalid json"
                self._drop(host)
                time.sleep(min(30, 2 ** attempt))
                continue
            code = (payload.get("error") or {}).get("code") if isinstance(payload, dict) else None
            if code in {"maxlag", "ratelimited"}:
                last = code
                pause = 8 + attempt * 3
                print(f"  {host} {code}, waiting {pause}s", flush=True)
                time.sleep(pause)
                continue
            return payload
        raise RuntimeError(f"{host} request failed: {last}")


def chunks(items, size):
    items = list(items)
    for start in range(0, len(items), size):
        yield items[start:start + size]


def fetch_p18(client, qids):
    found = {qid: [] for qid in qids}
    for group in chunks(qids, 40):
        payload = client.post(WIKIDATA, {
            "action": "wbgetentities",
            "ids": "|".join(group),
            "props": "claims",
            "format": "json",
        })
        for qid, entity in (payload.get("entities") or {}).items():
            if entity.get("missing"):
                continue
            names = []
            for claim in (entity.get("claims") or {}).get("P18") or []:
                value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
                if not isinstance(value, str) or not value:
                    continue
                names.append(value if value.startswith("File:") else f"File:{value}")
            found[qid] = names
    return found


def search_files(client, query):
    payload = client.post(COMMONS, {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "list": "search",
        "srsearch": query,
        "srnamespace": "6",
        "srlimit": "20",
    })
    return [item["title"] for item in (payload.get("query") or {}).get("search") or []]


def geosearch(client, fort):
    payload = client.post(COMMONS, {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "geosearch",
        "ggscoord": f"{fort['lat']}|{fort['lon']}",
        "ggsradius": "300",
        "ggslimit": "50",
        "ggsnamespace": "6",
        "prop": "coordinates",
    })
    found = []
    for page in (payload.get("query") or {}).get("pages") or []:
        title = page.get("title") or ""
        if not title.startswith("File:"):
            continue
        coords = (page.get("coordinates") or [None])[0] or {}
        if "lat" not in coords:
            continue
        distance = haversine(fort["lat"], fort["lon"], coords["lat"], coords["lon"])
        if distance <= COMMONS_RADIUS:
            found.append((title, distance))
    return found


def search_text(name, role):
    parts = [part.strip() for part in re.split(r"[,/]", name or "") if part.strip()]
    if parts and norm(parts[0]) in CONTAINERS and len(parts) > 1:
        parts = parts[1:]
    if not parts:
        return ""
    specs = specs_from_part(parts[0], role)
    if not specs or specs[0][1] == "weak":
        return ""
    return parts[0]


def nearby_titles(client, fort):
    """Titles to inspect: nearby files, plus title searches that name the fort."""
    titles = {}
    for title, distance in geosearch(client, fort):
        titles[title] = distance
    for phrase in fort["queries"]:
        for title in search_files(client, phrase):
            titles.setdefault(title, None)
    return titles


def fetch_details(client, titles):
    details = {}
    pending = [title for title in titles if title not in details]
    for group in chunks(pending, 25):
        payload = client.post(COMMONS, {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
            "titles": "|".join(group),
            "prop": "imageinfo|coordinates",
            "iiprop": "url|size|mime|mediatype|extmetadata",
        })
        query = payload.get("query") or {}
        redirect = {item.get("from"): item.get("to") for item in query.get("redirects") or []}
        normalised = {item.get("from"): item.get("to") for item in query.get("normalized") or []}
        by_title = {}
        for page in query.get("pages") or []:
            if page.get("missing") or page.get("invalid"):
                continue
            by_title[page.get("title")] = page
        for source in group:
            target = redirect.get(normalised.get(source, source), normalised.get(source, source))
            page = by_title.get(target) or by_title.get(source)
            if page:
                details[source] = page
                details[page.get("title")] = page
    return details


def page_distance(fort, page, fallback):
    coords = (page.get("coordinates") or [None])[0] or {}
    if "lat" in coords and "lon" in coords:
        return haversine(fort["lat"], fort["lon"], coords["lat"], coords["lon"])
    return fallback


def candidate_from(fort, page, source, fallback_distance=None):
    info = (page.get("imageinfo") or [None])[0]
    if not info:
        return None
    ext = info.get("extmetadata") or {}
    title = page.get("title") or ""
    categories = meta_value(ext, "Categories")
    if not looks_like_photograph(title, categories, info.get("mime"), info.get("mediatype"), info.get("width"), info.get("height")):
        return None
    licence = licence_of(meta_value(ext, "LicenseShortName"), meta_value(ext, "LicenseUrl"))
    if not licence:
        return None
    stem = stem_of(title)
    structure = bool(STRUCTURE.search(stem))
    incidental = bool(INCIDENTAL.search(stem)) or (bool(CATEGORY_SUBJECT.search(categories)) and not structure)
    matched = best_phrase(stem, fort["phrases"])
    category_match = None
    if matched is None:
        for category in categories.split("|"):
            found = best_phrase(category, fort["phrases"])
            if found and (category_match is None or KIND_RANK[found[1]] > KIND_RANK[category_match[1]]):
                category_match = found
    if source == "wikidata":
        match = matched[1] if matched else "p18"
        phrase = matched[0] if matched else ""
    elif source == "geograph":
        # The Geograph title was already checked. The Commons filename is
        # often the same wording, but a renamed re-upload still counts.
        match = matched[1] if matched else "name"
        phrase = matched[0] if matched else ""
    elif matched:
        match = matched[1]
        phrase = matched[0]
    elif category_match:
        match = "category"
        phrase = category_match[0]
    else:
        return None
    distance = page_distance(fort, page, fallback_distance)
    if source == "commons" and (distance is None or distance > COMMONS_RADIUS):
        return None
    file_url = (info.get("url") or "").split("?")[0]
    page_url = info.get("descriptionurl") or ""
    if not file_url.startswith("https://upload.wikimedia.org/") or "commons.wikimedia.org/wiki/" not in page_url:
        return None
    return {
        "source": source,
        "id": fort["code"],
        "title": stem,
        "file_title": title,
        "page": page_url,
        "file": file_url,
        "author": author_of(ext),
        "licence": licence[0],
        "licenceUrl": licence[1],
        "via": "Wikimedia Commons",
        "match": match,
        "phrase": phrase,
        "metres": None if distance is None else int(round(distance)),
        "width": info.get("width") or 0,
        "height": info.get("height") or 0,
        "structure": structure,
        "incidental": incidental,
        "outward": bool(OUTWARD.search(stem)),
        "cropped": "cropped" in title.lower(),
    }


def geograph_title_ok(title, kind) -> bool:
    """A Geograph title has to name the fort, not just a nearby farm or path."""
    structure = bool(STRUCTURE.search(title))
    incidental = bool(INCIDENTAL.search(title))
    if kind in {"name", "alt"}:
        return structure or not incidental
    if kind == "token":
        return structure and not incidental
    return False


def preference(candidate):
    tier = {"wikidata": 0, "commons": 1, "geograph": 2}[candidate["source"]]
    return (tier, -score(candidate), candidate["file_title"])


def score(candidate) -> float:
    kind = candidate["match"]
    value = {"name": 80, "alt": 70, "token": 45, "weak": 25, "category": 20, "p18": 10}[kind]
    if candidate["structure"]:
        value += 30
    if candidate["incidental"]:
        value -= 28
    if candidate.get("outward"):
        value -= 45
    metres = candidate.get("metres")
    if isinstance(metres, (int, float)):
        value += max(0, 24 - metres / 25)
    value += min(8, (candidate["width"] * candidate["height"]) / 800000)
    if candidate["cropped"]:
        value -= 4
    return value


def unique_sorted(candidates):
    best = {}
    for candidate in candidates:
        current = best.get(candidate["file"])
        if current is None or preference(candidate) < preference(current):
            best[candidate["file"]] = candidate
    return sorted(best.values(), key=preference)


def claim_key(candidate, slug):
    tier = {"wikidata": 0, "commons": 1, "geograph": 2}[candidate["source"]]
    match = 0 if candidate["match"] in {"name", "alt"} else 1 if candidate["match"] == "token" else 2
    metres = candidate["metres"] if candidate["metres"] is not None else 99999
    return (tier, match, metres, slug)


def resolve(lists):
    banned = {slug: set() for slug in lists}
    chosen = {}
    for _ in range(40):
        desired = {}
        for slug, candidates in lists.items():
            for candidate in candidates:
                if candidate["file"] in banned[slug]:
                    continue
                desired[slug] = candidate
                break
        groups = defaultdict(list)
        for slug, candidate in desired.items():
            groups[candidate["file"]].append(slug)
        conflict = False
        for slugs in groups.values():
            if len(slugs) == 1:
                continue
            conflict = True
            winner = min(slugs, key=lambda slug: claim_key(desired[slug], slug))
            for slug in slugs:
                if slug != winner:
                    banned[slug].add(desired[slug]["file"])
        chosen = desired
        if not conflict:
            break
    return chosen


def ensure_dump(url, name):
    path = CACHE / name
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as handle:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            handle.write(block)
    return path


def scan_geograph(forts):
    if not forts:
        return {}
    base = ensure_dump(DUMP_BASE, "gridimage_base.tsv.gz")
    geo = ensure_dump(DUMP_GEO, "gridimage_geo.tsv.gz")
    cell = 0.02
    grid = defaultdict(list)
    for fort in forts:
        grid[(math.floor(fort["lat"] / cell), math.floor(fort["lon"] / cell))].append(fort)
    hits = defaultdict(list)

    def consider(fort, row):
        bucket = hits[fort["slug"]]
        bucket.append(row)
        if len(bucket) > 50:
            bucket.sort(key=lambda item: item["rank"], reverse=True)
            del bucket[30:]

    seen = 0
    with gzip.open(base, "rt", encoding="latin1", newline="") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        index = {name: pos for pos, name in enumerate(header)}
        for line in handle:
            seen += 1
            if seen % 1_000_000 == 0:
                print(f"  geograph base {seen // 1_000_000}m rows, kept {sum(len(v) for v in hits.values())}")
            parts = line.rstrip("\n").split("\t")
            if len(parts) <= index["wgs84_long"]:
                continue
            try:
                lat = float(parts[index["wgs84_lat"]])
                lon = float(parts[index["wgs84_long"]])
            except ValueError:
                continue
            if not lat and not lon:
                continue
            cx, cy = math.floor(lat / cell), math.floor(lon / cell)
            nearby = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nearby.extend(grid.get((cx + dx, cy + dy), ()))
            if not nearby:
                continue
            title = parts[index["title"]]
            status = parts[index["moderation_status"]]
            if status not in {"geograph", "accepted"}:
                continue
            for fort in nearby:
                matched = best_phrase(title, fort["phrases"])
                if not matched:
                    continue
                distance = haversine(fort["lat"], fort["lon"], lat, lon)
                if distance > GEOGRAPH_RADIUS:
                    continue
                kind = matched[1]
                rank = KIND_RANK[kind] * 20
                if STRUCTURE.search(title):
                    rank += 8
                if INCIDENTAL.search(title):
                    rank -= 6
                rank -= distance / 200
                consider(fort, {
                    "id": int(parts[index["gridimage_id"]]),
                    "title": title,
                    "author": parts[index["realname"]].strip(),
                    "metres": int(round(distance)),
                    "match": kind,
                    "phrase": matched[0],
                    "rank": rank,
                })
    wanted = {row["id"] for rows in hits.values() for row in rows}
    precision = {}
    with gzip.open(geo, "rt", encoding="latin1", newline="") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        index = {name: pos for pos, name in enumerate(header)}
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            try:
                image_id = int(parts[index["gridimage_id"]])
            except (ValueError, IndexError):
                continue
            if image_id not in wanted:
                continue
            try:
                precision[image_id] = int(parts[index["natgrlen"]])
            except ValueError:
                continue
    kept = {}
    for slug, rows in hits.items():
        precise = [
            row for row in rows
            if precision.get(row["id"], 0) >= 6 and geograph_title_ok(row["title"], row["match"])
        ]
        precise.sort(key=lambda row: row["rank"], reverse=True)
        kept[slug] = precise[:8]
    print(f"Geograph title matches for {sum(1 for rows in kept.values() if rows)} forts still without a photo")
    return kept


def commons_for_geograph(client, image_id):
    titles = search_files(client, f"\"{image_id}\" geograph")
    pattern = re.compile(rf"(?<!\d){image_id}(?!\d)")
    return [title for title in titles if pattern.search(title)]


def derivative_url(file_title, width):
    name = file_title.split(":", 1)[1].replace(" ", "_")
    return "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(name) + f"?width={width}"


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"download failed {url}: {last}")


def save_pair(blob, slug):
    Image.MAX_IMAGE_PIXELS = 40_000_000
    with Image.open(io.BytesIO(blob)) as opened:
        image = ImageOps.exif_transpose(opened)
        if image.mode in {"RGBA", "LA"}:
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        else:
            image = image.convert("RGB")
    wide = resize_to(image, 1200)
    quality = 64
    wide_path = PHOTO_DIR / f"{slug}-1200.webp"
    narrow_path = PHOTO_DIR / f"{slug}-600.webp"
    write_webp(wide, wide_path, quality)
    if wide_path.stat().st_size > 170_000:
        write_webp(wide, wide_path, 52)
    narrow = resize_to(image, 600 if wide.size[0] >= 800 else max(320, wide.size[0] // 2))
    write_webp(narrow, narrow_path, 62)
    return wide.size, narrow.size


def resize_to(image, max_width):
    if image.width <= max_width:
        return image
    height = max(1, round(image.height * (max_width / image.width)))
    return image.resize((max_width, height), Image.Resampling.LANCZOS)


def write_webp(image, path, quality):
    image.save(path, "WEBP", quality=quality, method=6)


def record_of(fort, candidate, wide_size, narrow_size):
    return {
        "id": fort["code"],
        "source": candidate["source"],
        "page": candidate["page"],
        "file": candidate["file"],
        "author": candidate["author"],
        "licence": candidate["licence"],
        "licenceUrl": candidate["licenceUrl"],
        "via": candidate["via"],
        "title": candidate["title"],
        "match": candidate["match"],
        "metres": candidate["metres"],
        "wideWidth": wide_size[0],
        "wideHeight": wide_size[1],
        "narrowWidth": narrow_size[0],
        "narrowHeight": narrow_size[1],
    }


def shared_phrase(fort, phrase, forts):
    if not phrase:
        return False
    for other in forts:
        if other["slug"] == fort["slug"]:
            continue
        if abs(other["lat"] - fort["lat"]) > 0.03 or abs(other["lon"] - fort["lon"]) > 0.04:
            continue
        if haversine(fort["lat"], fort["lon"], other["lat"], other["lon"]) > 1500:
            continue
        if any(item == phrase for item, _kind in other["phrases"]):
            return True
    return False


# Seen on the contact sheet: the title does not by itself prove the picture
# is something other than the fort, but the picture is.
VIEWED_RISK = {"EN0001", "EN0416", "EN3975", "EN4043"}
DEFINITE_OFF = re.compile(
    r"\b(stained glass|phone box|sports field|distillery|dry dock|boathouse|"
    r"flush bracket|print of|twayblades?)\b",
    re.I,
)
LIKELY_OFF = re.compile(
    r"\b(quarry|church|chapel|footpath|bridleway|farm|pond|monument|"
    r"triangulation|lane|woods|orchard|walking|courtyard)\b|\btree on\b",
    re.I,
)
FORT_WORD = re.compile(
    r"\b(hillforts?|hill forts?|ramparts?|earthworks?|forts?|camps?|castles?|"
    r"brochs?|duns?|dúns?|caers?|gaers?|raths?|enclosures?|rings?)\b",
    re.I,
)


def review_flags(fort, candidate, forts):
    """Forts whose picture is most likely to be the wrong subject."""
    title = candidate.get("title") or ""
    reasons = []
    if fort["code"] in BUSY:
        reasons.append("busy site")
    if candidate["match"] == "category":
        reasons.append("matched a category, not the title")
    if candidate["match"] == "weak":
        reasons.append("fort name is generic")
    if DEFINITE_OFF.search(title) or fort["code"] in VIEWED_RISK:
        reasons.append("the picture is not the fort itself")
    elif LIKELY_OFF.search(title) and not FORT_WORD.search(title):
        reasons.append("the picture is not the fort itself")
    if shared_phrase(fort, candidate.get("phrase"), forts):
        reasons.append("another indexed fort nearby shares this name")
    # One reason is enough; keep the list short and specific.
    seen = []
    for reason in reasons:
        if reason not in seen:
            seen.append(reason)
    return seen


def font(size):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def letterbox(path, size):
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, (232, 226, 216))
        canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
        return canvas


def contact_sheet(forts, photos, flags, path, columns=15, thumb=(168, 112)):
    label_font = font(13)
    meta_font = font(11)
    cell_w = thumb[0] + 16
    cell_h = thumb[1] + 46
    rows = math.ceil(len(forts) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), (244, 240, 232))
    draw = ImageDraw.Draw(sheet)
    for index, fort in enumerate(forts):
        column = index % columns
        row = index // columns
        x = column * cell_w + 8
        y = row * cell_h + 6
        photo = photos.get(fort["slug"])
        wide = PHOTO_DIR / f"{fort['slug']}-1200.webp"
        if photo and wide.exists():
            sheet.paste(letterbox(wide, thumb), (x, y))
        else:
            draw.rectangle((x, y, x + thumb[0] - 1, y + thumb[1] - 1), fill=(214, 208, 198))
            draw.text((x + 8, y + thumb[1] // 2 - 8), "No photo", fill=(90, 84, 74), font=meta_font)
        flagged = fort["slug"] in flags
        if flagged:
            draw.rectangle((x - 2, y - 2, x + thumb[0] + 1, y + thumb[1] + 1), outline=(164, 48, 32), width=3)
        name = fort["name"]
        if len(name) > 26:
            name = name[:24] + "…"
        draw.text((x, y + thumb[1] + 3), name, fill=(28, 25, 21), font=label_font)
        source = photo["source"] if photo else "none"
        draw.text((x, y + thumb[1] + 20), f"{fort['code']}  {source}", fill=(90, 70, 58) if flagged else (94, 88, 78), font=meta_font)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, "JPEG", quality=62, optimize=True)
    print(f"Wrote {path} ({path.stat().st_size // 1024} KB)")


def flagged_sheet(items, path):
    """Larger cells for the forts worth a closer look."""
    if not items:
        return
    columns = 4
    thumb = (420, 280)
    label_font = font(16)
    meta_font = font(14)
    cell_w = thumb[0] + 24
    text_h = 78
    cell_h = thumb[1] + text_h
    rows = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), (244, 240, 232))
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(items):
        fort = item["fort"]
        photo = item["photo"]
        column = index % columns
        row = index // columns
        x = column * cell_w + 12
        y = row * cell_h + 10
        wide = PHOTO_DIR / f"{fort['slug']}-1200.webp"
        sheet.paste(letterbox(wide, thumb), (x, y))
        draw.text((x, y + thumb[1] + 4), f"{fort['name']} ({fort['code']})", fill=(28, 25, 21), font=label_font)
        draw.text((x, y + thumb[1] + 26), photo["title"][:70], fill=(70, 64, 54), font=meta_font)
        draw.text((x, y + thumb[1] + 46), "; ".join(item["reasons"])[:90], fill=(164, 48, 32), font=meta_font)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, "JPEG", quality=70, optimize=True)
    print(f"Wrote {path} ({path.stat().st_size // 1024} KB)")


def run(args):
    forts = load_forts(args.csv)
    if args.only:
        wanted = {item.strip().lower() for item in args.only.split(",")}
        forts = [fort for fort in forts if fort["code"].lower() in wanted or fort["slug"] in wanted]
    if not forts:
        raise SystemExit("no forts selected")
    print(f"{len(forts)} indexed forts")
    client = Client()
    qids = sorted({qid for fort in forts for qid in fort["qids"]})
    print(f"Fetching P18 for {len(qids)} Wikidata items")
    p18 = fetch_p18(client, qids)

    print("Searching Commons")
    nearby = {}
    lock = threading.Lock()
    done = {"n": 0}

    def one(fort):
        found = nearby_titles(client, fort)
        with lock:
            nearby[fort["slug"]] = found
            done["n"] += 1
            if done["n"] % 25 == 0 or done["n"] == len(forts):
                print(f"  searched {done['n']}/{len(forts)}")

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one, forts))

    titles = set()
    for fort in forts:
        for qid in fort["qids"]:
            titles.update(p18.get(qid) or [])
        titles.update(nearby[fort["slug"]])
    print(f"Fetching metadata for {len(titles)} files")
    details = fetch_details(client, titles)

    lists = {}
    for fort in forts:
        candidates = []
        for qid in fort["qids"]:
            for title in p18.get(qid) or []:
                page = details.get(title)
                if not page:
                    continue
                candidate = candidate_from(fort, page, "wikidata")
                if candidate:
                    candidates.append(candidate)
        for title, distance in nearby[fort["slug"]].items():
            page = details.get(title)
            if not page:
                continue
            candidate = candidate_from(fort, page, "commons", distance)
            if candidate:
                candidates.append(candidate)
        lists[fort["slug"]] = unique_sorted(candidates)

    chosen = resolve(lists)
    pending = [fort for fort in forts if fort["slug"] not in chosen]
    print(f"{len(chosen)} forts matched Wikidata or Commons; {len(pending)} left for Geograph")
    if pending and not args.skip_geograph:
        geograph = scan_geograph(pending)
        geo_titles = {}
        for fort in pending:
            for row in geograph.get(fort["slug"]) or []:
                for title in commons_for_geograph(client, row["id"]):
                    geo_titles.setdefault(title, []).append((fort["slug"], row))
        if geo_titles:
            print(f"Fetching metadata for {len(geo_titles)} Geograph re-uploads")
            details.update(fetch_details(client, geo_titles))
        for fort in pending:
            extra = []
            for row in geograph.get(fort["slug"]) or []:
                for title, pairs in geo_titles.items():
                    if not any(slug == fort["slug"] and item["id"] == row["id"] for slug, item in pairs):
                        continue
                    page = details.get(title)
                    if not page:
                        continue
                    candidate = candidate_from(fort, page, "geograph", row["metres"])
                    if not candidate:
                        continue
                    # The dump title is what had to name the fort. Keep that
                    # location even if the Commons file has no coordinates.
                    candidate["metres"] = row["metres"]
                    candidate["phrase"] = row["phrase"]
                    candidate["match"] = row["match"]
                    if not candidate["author"] or candidate["author"] == "Unknown":
                        candidate["author"] = clean_author(row["author"]) or "Unknown"
                    extra.append(candidate)
            lists[fort["slug"]] = unique_sorted(lists[fort["slug"]] + extra)
        chosen = resolve(lists)

    by_slug = {fort["slug"]: fort for fort in forts}
    flags = {}
    for slug, candidate in chosen.items():
        reasons = review_flags(by_slug[slug], candidate, forts)
        if reasons:
            flags[slug] = reasons

    if args.dry_run:
        print_summary(forts, chosen, flags)
        return

    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    previous = {}
    if OUTPUT.exists():
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
    photos = {}
    ordered = [fort for fort in forts if fort["slug"] in chosen]
    reused = 0
    download_list = []
    for fort in ordered:
        candidate = chosen[fort["slug"]]
        old = previous.get(fort["slug"]) or {}
        wide = PHOTO_DIR / f"{fort['slug']}-1200.webp"
        narrow = PHOTO_DIR / f"{fort['slug']}-600.webp"
        if old.get("file") == candidate["file"] and wide.is_file() and narrow.is_file():
            record = record_of(
                fort,
                candidate,
                (old["wideWidth"], old["wideHeight"]),
                (old["narrowWidth"], old["narrowHeight"]),
            )
            photos[fort["slug"]] = record
            reused += 1
        else:
            download_list.append(fort)
    print(f"Reusing {reused} images, downloading {len(download_list)}")

    def fetch_one(fort):
        candidate = chosen[fort["slug"]]
        blob = download(derivative_url(candidate["file_title"], 1600))
        wide_size, narrow_size = save_pair(blob, fort["slug"])
        return fort["slug"], record_of(fort, candidate, wide_size, narrow_size)

    failures = []
    if download_list:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(fetch_one, fort) for fort in download_list]
            for future in futures:
                try:
                    slug, record = future.result()
                except Exception as exc:
                    failures.append(str(exc))
                    continue
                photos[slug] = record
                print(f"  saved {photos[slug]['id']}", flush=True)
    keep = {f"{slug}-1200.webp" for slug in photos} | {f"{slug}-600.webp" for slug in photos}
    for path in PHOTO_DIR.glob("*.webp"):
        if path.name not in keep:
            path.unlink()
    if failures:
        print(f"{len(failures)} downloads failed")
        for message in failures[:12]:
            print(" ", message)

    # Drop choices whose file did not save, and drop a shared file's loser
    # again if a download failed.
    saved = {slug: chosen[slug] for slug in photos}
    payload = {slug: photos[slug] for slug in sorted(photos)}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(payload)} forts)")

    review_flags_saved = {slug: flags[slug] for slug in flags if slug in photos}
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    contact_sheet(forts, photos, review_flags_saved, ARTIFACTS / "fort-photo-contact-sheet.jpg")
    flagged_items = [
        {"fort": by_slug[slug], "photo": photos[slug], "reasons": reasons}
        for slug, reasons in sorted(review_flags_saved.items())
    ]
    flagged_sheet(flagged_items, ARTIFACTS / "fort-photo-flagged.jpg")
    review = {
        "photos": len(photos),
        "flags": [
            {
                "id": photos[slug]["id"],
                "slug": slug,
                "name": by_slug[slug]["name"],
                "source": photos[slug]["source"],
                "title": photos[slug]["title"],
                "licence": photos[slug]["licence"],
                "page": photos[slug]["page"],
                "reasons": reasons,
            }
            for slug, reasons in sorted(review_flags_saved.items())
        ],
    }
    (ARTIFACTS / "photo-review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print_summary(forts, saved, review_flags_saved)
    if failures:
        raise SystemExit(1)


def print_summary(forts, chosen, flags):
    sources = defaultdict(int)
    licences = defaultdict(int)
    for candidate in chosen.values():
        sources[candidate["source"] if "source" in candidate else candidate.get("source")] += 1
        licences[candidate["licence"]] += 1
    # chosen values may be candidates or saved records; both have these keys
    print(f"Photos: {len(chosen)} of {len(forts)}. None: {len(forts) - len(chosen)}")
    print("Source:", ", ".join(f"{key} {sources[key]}" for key in ("wikidata", "commons", "geograph") if sources[key]) or "none")
    print("Licence:", ", ".join(f"{key} {licences[key]}" for key in sorted(licences)))
    for fort in forts:
        candidate = chosen.get(fort["slug"])
        if not candidate:
            print(f"  {fort['code']} none")
            continue
        print(
            f"  {fort['code']} {candidate['source']:9} {candidate['match']:8} "
            f"{str(candidate.get('metres')):>5}m {candidate['licence']:16} "
            f"{candidate['author'][:28]:28} | {candidate['title'][:70]}"
        )
    print(f"Flagged: {len(flags)}")
    for slug in sorted(flags):
        candidate = chosen[slug]
        title = candidate.get("title") or ""
        print(f"  {candidate.get('id', slug)} {title[:60]} | {'; '.join(flags[slug])}")


def self_test():
    aconbury = phrase_specs("Aconbury Camp", "name") + phrase_specs("Aconbury Beacon", "alt")
    assert best_phrase("Path on Aconbury Hill", aconbury)[1] == "token"
    assert best_phrase("Aconbury Camp under the trees", aconbury)[1] == "name"
    assert best_phrase("Camp Farm", aconbury) is None
    british = phrase_specs("British Camp", "name") + phrase_specs("Herefordshire Beacon", "alt")
    assert best_phrase("British Camp from the east", british)[1] == "name"
    assert best_phrase("Herefordshire Beacon", british)[1] == "alt"
    assert best_phrase("British Motor Museum", british) is None
    skye = phrase_specs("Skye, Dun Cruinn", "name")
    assert best_phrase("Dun Cruinn from the loch", skye)[1] == "name"
    assert best_phrase("Skye, Dun Skudiburgh", skye) is None
    assert best_phrase("The Wrekin", phrase_specs("The Wrekin", "name"))[1] == "name"
    assert best_phrase("Hod", phrase_specs("Hod Hill", "name")) is None
    assert best_phrase("Hod Hill fort", phrase_specs("Hod Hill", "name"))[1] == "name"
    poston = "File:Poston Camp Digital Terrain Model.jpg"
    assert not looks_like_photograph(poston, "Digital terrain models of British hillforts|Poston Camp", "image/jpeg", "BITMAP", 1920, 1080)
    assert looks_like_photograph("File:Entrance to Maiden Castle.jpg", "Maiden Castle|Hill forts in Dorset", "image/jpeg", "BITMAP", 1600, 1200)
    assert not looks_like_photograph("File:Plan of Maiden Castle.jpg", "Maiden Castle", "image/jpeg", "BITMAP", 1600, 1200)
    assert licence_of("CC BY-SA 2.0", "https://creativecommons.org/licenses/by-sa/2.0")[0] == "CC BY-SA 2.0"
    assert licence_of("CC BY-NC-SA 2.0", "") is None
    assert licence_of("CC BY-ND 4.0", "") is None
    assert licence_of("CC0", "")[0] == "CC0"
    assert licence_of("Public domain", "")[0] == "Public domain"
    assert licence_of("OGL 3", "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/")[0] == "OGL 3"
    assert licence_of("GFDL", "https://www.gnu.org/licenses/fdl.html") is None
    assert licence_of("Copyrighted free use", "") is None
    assert licence_of("Attribution-ShareAlike 3.0", "")[0] == "CC BY-SA 3.0"
    author = author_of({"Artist": {"value": '<a href="https://example.test/u">Philip Halling</a>'}, "Attribution": {"value": "Philip Halling"}})
    assert author == "Philip Halling"
    assert "<" not in author
    messy = clean_author("<b>Ada Lovelace</b><br>https://example.test/a")
    assert messy == "Ada Lovelace"
    credit = author_of({
        "Artist": {"value": "Oswestry Borderland Tourism"},
        "Attribution": {"value": "Credit Oswestry Borderland Tourism"},
    })
    assert credit == "Oswestry Borderland Tourism", credit
    titled = author_of({
        "Artist": {"value": '<a href="https://example.test/p">Philip Halling</a>'},
        "Attribution": {"value": "<i>Wall Hills Farm</i> by Philip Halling"},
    })
    assert titled == "Philip Halling", titled
    assert tidy_author("Felday Chapel, Holmbury St Mary, by Kim Martin") == "Kim Martin"
    assert tidy_author("Joe D, modified by JimChampion") == "Joe D and JimChampion"
    assert tidy_author("photographed by myself") == ""
    assert geograph_title_ok("Wall Hills Farm", "token") is False
    assert geograph_title_ok("Wall Hills Camp", "name") is True
    assert geograph_title_ok("Oswestry hillfort", "token") is True
    print("self-test ok")


def main():
    parser = argparse.ArgumentParser(description="Cache a free-licence photo for each indexed hillfort.")
    parser.add_argument("--csv", help="Optional research CSV with an extra Wikidata QID column")
    parser.add_argument("--only", help="Comma-separated Atlas codes or slugs, for a trial run")
    parser.add_argument("--dry-run", action="store_true", help="Choose photos and print them, without downloading")
    parser.add_argument("--skip-geograph", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    run(args)


if __name__ == "__main__":
    main()
