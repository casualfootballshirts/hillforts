#!/usr/bin/env python3
"""Cache nearest OpenStreetMap access facts for each hillfort.

One-off script. It reads Geofabrik extracts (Great Britain, Ireland and
Northern Ireland, and the Isle of Man), keeps public car parks, nearby
paths, and towns or villages, and writes data/access.json. The site build
reads that file and does not call Overpass.

Download the extracts first, or pass their paths. A polite User-Agent is
sent if this script downloads them. Re-runs reuse files already on disk.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import osmium

ROOT = Path(__file__).resolve().parents[1]
SITES = ROOT / "data" / "sites.json"
OUTPUT = ROOT / "data" / "access.json"
CACHE = Path("/tmp/osm")
USER_AGENT = "hillfortsmap-access-fetch/1.0 (one-off static site cache; privacy@hillfortsmap.co.uk)"

EXTRACTS = {
    "great-britain": "https://download.geofabrik.de/europe/great-britain-latest.osm.pbf",
    "ireland": "https://download.geofabrik.de/europe/ireland-and-northern-ireland-latest.osm.pbf",
    "isle-of-man": "https://download.geofabrik.de/europe/isle-of-man-latest.osm.pbf",
}

CELL = 0.02
PARKING_RADIUS = 2000
WAY_RADIUS = 250
PLACE_CELL = 0.1
FORBIDDEN_ACCESS = {"private", "no", "customers", "customer"}
# Names that mark a car park as not for the general public, even when the
# access tag itself was left off the OpenStreetMap object.
NON_PUBLIC_NAME = ("customer", "staff only", "staff car", "staff parking", "private", "resident")


def haversine(lat1, lon1, lat2, lon2) -> float:
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlng = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlng / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def segment_distance(lat, lon, lat1, lon1, lat2, lon2) -> float:
    """Distance in metres from a point to a short segment, in a local projection."""
    metres_lat = 111320
    metres_lon = 111320 * math.cos(math.radians(lat))
    x1 = (lon1 - lon) * metres_lon
    y1 = (lat1 - lat) * metres_lat
    x2 = (lon2 - lon) * metres_lon
    y2 = (lat2 - lat) * metres_lat
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x1, y1)
    t = max(0.0, min(1.0, -(x1 * dx + y1 * dy) / (dx * dx + dy * dy)))
    return math.hypot(x1 + t * dx, y1 + t * dy)


def cell_of(lat, lon, size=CELL):
    return (math.floor(lat / size), math.floor(lon / size))


def clean_name(value) -> str:
    if not value:
        return ""
    text = " ".join(str(value).split())
    if len(text) > 80:
        return ""
    return text


def forbidden_access(tags) -> bool:
    raw = (tags.get("access") or "").lower().replace("|", ";")
    parts = [part.strip() for part in raw.split(";") if part.strip()]
    return any(part in FORBIDDEN_ACCESS for part in parts)


def non_public_parking_name(name: str) -> bool:
    low = name.lower()
    return any(token in low for token in NON_PUBLIC_NAME)


def way_kind(tags):
    """Return (kind, priority) or (None, None). Lower priority is preferred.

    Public footpath and public bridleway are used only for those designation
    tags, or for highway=bridleway. A permissive or private path is not
    described as a public right of way.
    """
    highway = tags.get("highway") or ""
    designation = (tags.get("designation") or "").lower().replace(" ", "_").replace("-", "_")
    public_foot = "public_footpath" in designation or designation == "public_footway"
    public_bridle = "public_bridleway" in designation
    if forbidden_access(tags) and not public_foot and not public_bridle:
        return None, None
    if public_foot:
        return "public-footpath", 1
    if public_bridle or (
        highway == "bridleway" and "permissive" not in designation and "private" not in designation
    ):
        return "public-bridleway", 2
    if highway == "footway":
        return "footway", 3
    if highway == "path":
        return "path", 4
    if highway == "track":
        return "track", 5
    return None, None


def download(name: str, url: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f"{name}.osm.pbf"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"reuse {dest} ({dest.stat().st_size} bytes)")
        return dest
    print(f"download {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    delay = 8
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=120) as response, dest.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
            return dest
        except Exception as exc:
            print(f"download failed ({attempt + 1}/5): {exc}")
            if dest.exists():
                dest.unlink()
            if attempt == 4:
                raise
            time.sleep(delay)
            delay *= 2
    return dest


def filter_extract(source: Path) -> Path:
    filtered = CACHE / "filtered" / f"{source.stem}-access.osm.pbf"
    filtered.parent.mkdir(parents=True, exist_ok=True)
    if filtered.exists() and filtered.stat().st_size > 0:
        print(f"reuse {filtered}")
        return filtered
    expressions = CACHE / "access-filters.txt"
    expressions.write_text(
        "\n".join([
            "n/amenity=parking",
            "w/amenity=parking",
            "n/place=town",
            "n/place=village",
            "w/highway=footway",
            "w/highway=path",
            "w/highway=bridleway",
            "w/highway=track",
            "w/designation",
        ]) + "\n",
        encoding="utf-8",
    )
    print(f"filter {source.name}")
    subprocess.run(
        [
            "osmium", "tags-filter", "--overwrite", "--progress",
            "-e", str(expressions),
            "-o", str(filtered),
            str(source),
        ],
        check=True,
    )
    return filtered


class Collector(osmium.SimpleHandler):
    def __init__(self, forts, grid):
        super().__init__()
        self.forts = forts
        self.grid = grid
        self.parking = defaultdict(list)
        self.ways = {}
        self.places = []
        self.nodes_seen = 0
        self.ways_seen = 0
        self.way_cells = set()
        self.parking_cells = set()
        for cx, cy in grid:
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    self.way_cells.add((cx + dx, cy + dy))
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    self.parking_cells.add((cx + dx, cy + dy))

    def forts_near(self, lat, lon, radius):
        span = int(radius / (CELL * 100000)) + 1
        cx, cy = cell_of(lat, lon)
        found = []
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                for index in self.grid.get((cx + dx, cy + dy), ()):
                    fort = self.forts[index]
                    distance = haversine(lat, lon, fort["lat"], fort["lon"])
                    if distance <= radius:
                        found.append((distance, index))
        return found

    def node(self, node):
        self.nodes_seen += 1
        if self.nodes_seen % 500000 == 0:
            print(f"  nodes {self.nodes_seen}", flush=True)
        tags = node.tags
        if not node.location.valid():
            return
        amenity = tags.get("amenity")
        place = tags.get("place")
        if amenity == "parking":
            if cell_of(node.location.lat, node.location.lon) in self.parking_cells:
                self.add_parking_point(node.location.lat, node.location.lon, tags, None)
        elif place in {"town", "village"}:
            name = clean_name(tags.get("name"))
            if name:
                self.places.append({
                    "name": name,
                    "kind": place,
                    "lat": node.location.lat,
                    "lon": node.location.lon,
                })

    def way(self, way):
        self.ways_seen += 1
        if self.ways_seen % 100000 == 0:
            print(f"  ways {self.ways_seen}", flush=True)
        tags = way.tags
        try:
            coords = [(node.lat, node.lon) for node in way.nodes if node.location.valid()]
        except osmium.InvalidLocationError:
            return
        if len(coords) < 1:
            return
        if tags.get("amenity") == "parking":
            self.add_parking_way(coords, tags)
            return
        kind, priority = way_kind(tags)
        if not kind or len(coords) < 2:
            return
        if not self.way_could_pass(coords):
            return
        name = clean_name(tags.get("name"))
        for start, end in zip(coords, coords[1:]):
            self.consider_segment(start, end, priority, kind, name)

    def way_could_pass(self, coords) -> bool:
        prev = None
        for lat, lon in coords:
            if cell_of(lat, lon) in self.way_cells:
                return True
            if prev is not None and (abs(lat - prev[0]) > 0.03 or abs(lon - prev[1]) > 0.05):
                steps = int(max(abs(lat - prev[0]), abs(lon - prev[1])) / 0.02)
                for step in range(1, steps):
                    t = step / steps
                    if cell_of(prev[0] + (lat - prev[0]) * t, prev[1] + (lon - prev[1]) * t) in self.way_cells:
                        return True
            prev = (lat, lon)
        return False

    def consider_segment(self, start, end, priority, kind, name):
        mid_lat = (start[0] + end[0]) / 2
        mid_lon = (start[1] + end[1]) / 2
        length = math.hypot(
            (end[0] - start[0]) * 111320,
            (end[1] - start[1]) * 111320 * math.cos(math.radians(mid_lat)),
        )
        samples = [(mid_lat, mid_lon)]
        if length > 400:
            steps = max(2, int(length // 200))
            for step in range(steps + 1):
                t = step / steps
                samples.append((
                    start[0] + (end[0] - start[0]) * t,
                    start[1] + (end[1] - start[1]) * t,
                ))
        seen = set()
        for lat, lon in samples:
            for _distance, index in self.forts_near(lat, lon, 500):
                if index in seen:
                    continue
                seen.add(index)
                fort = self.forts[index]
                metres = segment_distance(fort["lat"], fort["lon"], start[0], start[1], end[0], end[1])
                if metres > WAY_RADIUS:
                    continue
                current = self.ways.get(index)
                candidate = (priority, metres, kind, name)
                if current is None or candidate < (current[0], current[1], current[2], current[3]):
                    self.ways[index] = candidate

    def add_parking_point(self, lat, lon, tags, identity):
        if tags.get("amenity") != "parking" or forbidden_access(tags):
            return
        name = clean_name(tags.get("name"))
        if non_public_parking_name(name):
            return
        for distance, index in self.forts_near(lat, lon, PARKING_RADIUS):
            bucket = self.parking[index]
            bucket.append({
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "name": name,
                "metres": distance,
                "id": identity,
            })
            if len(bucket) > 12:
                bucket.sort(key=lambda item: item["metres"])
                del bucket[8:]

    def add_parking_way(self, coords, tags):
        if forbidden_access(tags):
            return
        name = clean_name(tags.get("name"))
        if non_public_parking_name(name):
            return
        best = {}
        for lat, lon in coords:
            if cell_of(lat, lon) not in self.parking_cells:
                continue
            for distance, index in self.forts_near(lat, lon, PARKING_RADIUS):
                current = best.get(index)
                if current is None or distance < current[0]:
                    best[index] = (distance, lat, lon)
        for index, (distance, lat, lon) in best.items():
            bucket = self.parking[index]
            bucket.append({
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "name": name,
                "metres": distance,
                "id": ("way", round(lat, 4), round(lon, 4), name),
            })


def dedupe_parking(items):
    items = sorted(items, key=lambda item: (item["metres"], 0 if item.get("name") else 1))
    kept = []
    for item in items:
        if any(haversine(item["lat"], item["lon"], other["lat"], other["lon"]) < 30 for other in kept):
            continue
        kept.append({
            "lat": item["lat"],
            "lon": item["lon"],
            "name": item["name"],
            "metres": int(round(item["metres"])),
        })
        if len(kept) == 2:
            break
    return kept


def nearest_place(fort, place_grid):
    lat, lon = fort["lat"], fort["lon"]
    cx, cy = cell_of(lat, lon, PLACE_CELL)
    best = None
    for span in range(0, 25):
        found = []
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                if span and max(abs(dx), abs(dy)) != span:
                    continue
                for place in place_grid.get((cx + dx, cy + dy), ()):
                    metres = haversine(lat, lon, place["lat"], place["lon"])
                    if best is None or metres < best[0]:
                        found.append((metres, place))
        if found:
            found.sort(key=lambda item: item[0])
            if best is None or found[0][0] < best[0]:
                best = found[0]
        if best is not None:
            min_outside = span * PLACE_CELL * 90000
            if best[0] <= min_outside or span == 24:
                break
    if not best:
        return None
    metres, place = best
    return {
        "name": place["name"],
        "kind": place["kind"],
        "lat": round(place["lat"], 5),
        "lon": round(place["lon"], 5),
        "metres": int(round(metres)),
    }


def main():
    forts = json.loads(SITES.read_text(encoding="utf-8"))
    grid = defaultdict(list)
    for index, fort in enumerate(forts):
        grid[cell_of(fort["lat"], fort["lon"])].append(index)
    sources = [download(name, url) for name, url in EXTRACTS.items()]
    collector = Collector(forts, grid)
    for source in sources:
        filtered = filter_extract(source)
        print(f"read {filtered.name}")
        collector.apply_file(str(filtered), locations=True)
    place_grid = defaultdict(list)
    for place in collector.places:
        place_grid[cell_of(place["lat"], place["lon"], PLACE_CELL)].append(place)
    payload = {}
    with_parking = with_way = with_place = 0
    for index, fort in enumerate(forts):
        record = {}
        parking = dedupe_parking(collector.parking.get(index, []))
        if parking:
            record["parking"] = parking
            with_parking += 1
        way = collector.ways.get(index)
        if way:
            _priority, metres, kind, name = way
            record["way"] = {"kind": kind, "name": name, "metres": int(round(metres))}
            with_way += 1
        place = nearest_place(fort, place_grid)
        if place:
            record["place"] = place
            with_place += 1
        payload[fort["slug"]] = record
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT} forts={len(payload)} parking={with_parking} ways={with_way} places={with_place}")
    print(f"places collected {len(collector.places)}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"osmium failed: {exc}", file=sys.stderr)
        sys.exit(1)
