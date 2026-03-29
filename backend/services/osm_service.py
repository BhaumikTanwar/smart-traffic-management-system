"""
osm_service.py
--------------
Fetches a real road network for a bounding box from the Overpass API.
Nodes  = OSM intersections (ways sharing ≥2 roads)
Edges  = road segments between those intersections
Cached in memory after first fetch so the app doesn't hammer Overpass.

Generators = high-traffic origin points (markets, stations, stadiums)
Sinks      = highways / ring roads that absorb outbound traffic
"""

import logging
import math
import requests
from collections import defaultdict

log = logging.getLogger("osm_service")

# ── Delhi bounding box (south, west, north, east) ─────
BBOX = "28.60,77.18,28.65,77.24"   # central Delhi, manageable size

# ── Known generator / sink node names (partial match) ─
GENERATOR_KEYWORDS = [
    "connaught", "market", "station", "terminal",
    "hospital", "mall", "stadium", "school", "college",
]
SINK_KEYWORDS = [
    "ring road", "highway", "expressway", "bypass", "flyover",
]

_cache: dict | None = None   # cached result


def _haversine(lat1, lng1, lat2, lng2) -> float:
    """Approximate distance in metres between two lat/lng points."""
    R  = 6_371_000
    p1 = math.radians(lat1); p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a  = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _classify(name: str) -> str:
    """Return 'generator', 'sink', or 'normal'."""
    n = (name or "").lower()
    if any(k in n for k in GENERATOR_KEYWORDS): return "generator"
    if any(k in n for k in SINK_KEYWORDS):      return "sink"
    return "normal"


def fetch_osm_network(force: bool = False) -> dict:
    """
    Returns:
        {
          "nodes": { id: {lat, lng, name, role} },
          "edges": { id: [id, ...] },
          "generators": [id, ...],
          "sinks":      [id, ...]
        }
    """
    global _cache
    if _cache and not force:
        return _cache

    log.info("Fetching OSM road network for bbox=%s …", BBOX)

    query = f"""
    [out:json][timeout:25];
    (
      way["highway"~"primary|secondary|tertiary|residential"]({BBOX});
    );
    out body;
    >;
    out skt qt;
    """

    try:
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=30,
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    except Exception as e:
        log.error("Overpass fetch failed: %s — using fallback", e)
        return _fallback_network()

    # ── Parse OSM elements ────────────────────────────
    osm_nodes: dict[int, dict] = {}   # node_id → {lat, lng}
    ways:      list[list[int]] = []   # list of [node_id, ...]

    for el in elements:
        if el["type"] == "node":
            osm_nodes[el["id"]] = {
                "lat":  el["lat"],
                "lng":  el["lon"],
                "name": el.get("tags", {}).get("name", ""),
            }
        elif el["type"] == "way":
            nds = el.get("nodes", [])
            if len(nds) >= 2:
                ways.append(nds)

    if not osm_nodes or not ways:
        log.warning("OSM returned empty data — using fallback")
        return _fallback_network()

    # ── Find intersections (nodes shared by ≥2 ways) ──
    node_way_count: dict[int, int] = defaultdict(int)
    for way in ways:
        for nid in way:
            node_way_count[nid] += 1

    # also always include endpoints of every way
    intersection_ids = {
        nid for nid, cnt in node_way_count.items() if cnt >= 2
    }
    for way in ways:
        if way:
            intersection_ids.add(way[0])
            intersection_ids.add(way[-1])

    # keep only intersection nodes that exist in osm_nodes
    intersection_ids = {nid for nid in intersection_ids if nid in osm_nodes}

    # ── Limit to a reasonable number for the UI ───────
    # Pick up to 40 intersections spread across the bbox
    if len(intersection_ids) > 40:
        sorted_ids = sorted(intersection_ids)
        step = max(1, len(sorted_ids) // 40)
        intersection_ids = set(sorted_ids[::step][:40])

    # ── Build node dict with short labels ─────────────
    id_map = {}   # osm_id → short label like "N0", "N1", ...
    nodes  = {}
    for i, nid in enumerate(sorted(intersection_ids)):
        raw  = osm_nodes[nid]
        key  = f"N{i}"
        role = _classify(raw["name"])
        id_map[nid] = key
        nodes[key]  = {
            "lat":  round(raw["lat"], 6),
            "lng":  round(raw["lng"], 6),
            "name": raw["name"] or key,
            "role": role,
        }

    # ── Build edges from ways ─────────────────────────
    edges: dict[str, list[str]] = {k: [] for k in nodes}

    for way in ways:
        # collect intersection nodes along this way in order
        inter = [id_map[nid] for nid in way if nid in id_map]
        for a, b in zip(inter, inter[1:]):
            if a != b:
                if b not in edges[a]: edges[a].append(b)
                if a not in edges[b]: edges[b].append(a)

    # ── Remove isolated nodes ─────────────────────────
    connected = {k for k, nb in edges.items() if nb}
    nodes  = {k: v for k, v in nodes.items() if k in connected}
    edges  = {k: [n for n in v if n in connected]
              for k, v in edges.items() if k in connected}

    generators = [k for k, v in nodes.items() if v["role"] == "generator"]
    sinks      = [k for k, v in nodes.items() if v["role"] == "sink"]

    # If OSM names gave us nothing, auto-assign a few generators/sinks
    if not generators:
        keys = list(nodes.keys())
        # highest-degree nodes → generators (busy intersections)
        by_degree = sorted(keys, key=lambda k: len(edges.get(k,[])), reverse=True)
        for k in by_degree[:2]:
            nodes[k]["role"] = "generator"
            generators.append(k)

    if not sinks:
        keys = list(nodes.keys())
        by_degree = sorted(keys, key=lambda k: len(edges.get(k,[])), reverse=True)
        # peripheral nodes (low degree) → sinks
        by_degree_asc = sorted(keys, key=lambda k: len(edges.get(k,[])))
        for k in by_degree_asc[:2]:
            if k not in generators:
                nodes[k]["role"] = "sink"
                sinks.append(k)

    log.info(
        "OSM network ready: %d nodes, %d generators, %d sinks",
        len(nodes), len(generators), len(sinks)
    )

    _cache = {"nodes": nodes, "edges": edges,
              "generators": generators, "sinks": sinks}
    return _cache


def _fallback_network() -> dict:
    """Hardcoded Delhi-area network used when Overpass is unreachable."""
    nodes = {
        "CP":   {"lat": 28.6315, "lng": 77.2167, "name": "Connaught Place",   "role": "generator"},
        "ITO":  {"lat": 28.6277, "lng": 77.2410, "name": "ITO",               "role": "normal"},
        "IP":   {"lat": 28.6363, "lng": 77.2501, "name": "IP Extension",      "role": "normal"},
        "KG":   {"lat": 28.6139, "lng": 77.2090, "name": "Khan Market",       "role": "generator"},
        "RK":   {"lat": 28.5677, "lng": 77.2000, "name": "RK Puram",          "role": "normal"},
        "NH48": {"lat": 28.5921, "lng": 77.1577, "name": "NH-48 Entry",       "role": "sink"},
        "RR":   {"lat": 28.6500, "lng": 77.2300, "name": "Ring Road North",   "role": "sink"},
        "PH":   {"lat": 28.6450, "lng": 77.1950, "name": "Patel Chowk",      "role": "normal"},
        "MG":   {"lat": 28.5921, "lng": 77.2300, "name": "MGRoad",            "role": "normal"},
    }
    edges = {
        "CP":   ["ITO", "PH", "KG"],
        "ITO":  ["CP", "IP", "MG"],
        "IP":   ["ITO", "RR"],
        "KG":   ["CP", "MG", "RK"],
        "RK":   ["KG", "NH48", "MG"],
        "NH48": ["RK"],
        "RR":   ["IP", "PH"],
        "PH":   ["CP", "RR"],
        "MG":   ["ITO", "KG", "RK"],
    }
    generators = ["CP", "KG"]
    sinks      = ["NH48", "RR"]
    log.info("Using fallback Delhi network")
    _cache_val = {"nodes": nodes, "edges": edges,
                  "generators": generators, "sinks": sinks}
    return _cache_val
