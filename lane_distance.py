# lane_distance.py

import logging

# ─── QUIET DOWN OTHER LIBRARIES ───────────────────────────────────────────────
for lib in (
    'watchdog',               # Streamlit’s file‐watcher core
    'watchdog.events',        # file‐watcher events
    'watchdog.observers',     # file‐watcher observers
    'urllib3',                # HTTP connection logging
    'http.client',            # lower‐level HTTP
    'mapbox',                 # Mapbox SDK
    'streamlit',              # Streamlit framework itself
):
    logging.getLogger(lib).setLevel(logging.WARNING)

# ─── NOW ENABLE YOUR DEBUG LOGGING ────────────────────────────────────────────
logging.basicConfig(format='[DEBUG] %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

import os
import argparse
import pandas as pd
import re
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2
from typing import Optional, Tuple

from shapely import wkt
from mapbox import Geocoder, Directions
import streamlit as st

# ─── Clear Streamlit cache if loaded in-app ──────────────────────────────────
if 'cache_data' in dir(st):
    st.cache_data.clear()

# ─── STATIC MASTER LOOKUP ────────────────────────────────────────────────────
MASTER_CSV = Path("data/unlocode_master_updated.csv")

_master_df = (
    pd.read_csv(MASTER_CSV, dtype=str, encoding="latin-1")
      .assign(
         code      = lambda df: df["LOCODE"].str.strip().str.upper(),
         Latitude  = lambda df: pd.to_numeric(df["Latitude"], errors="coerce"),
         Longitude = lambda df: pd.to_numeric(df["Longitude"], errors="coerce"),
         src       = lambda df: df["src"].astype(str),
      )
)

_unloc_lookup = {
    row["code"]: (row["Latitude"], row["Longitude"], row["src"])
    for _, row in _master_df.iterrows()
    if pd.notna(row["Latitude"]) and pd.notna(row["Longitude"])
}

LOCODE_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}$")

# ─── COORD EXTRACTION HELPERS ─────────────────────────────────────────────────

def extract_lon_lat(wkt_str: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract (lon, lat) from a WKT POINT string, or (None, None) if invalid.
    """
    try:
        geom = wkt.loads(wkt_str)
        if geom.geom_type == 'Point':
            return geom.x, geom.y
    except Exception:
        pass
    return None, None

def try_unlocode(s: Optional[str]) -> Optional[Tuple[float, float, str]]:
    """
    If `s` looks like a valid UN/LOCODE and is in the master lookup,
    return (lat, lon, source), else None.
    """
    if not isinstance(s, str):
        return None
    code = s.strip().upper()
    if LOCODE_RE.match(code) and code in _unloc_lookup:
        return _unloc_lookup[code]
    return None

# ─── MAPBOX CLIENTS ──────────────────────────────────────────────────────────

def make_geocoder():
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        raise ValueError("MAPBOX_TOKEN not set")
    return Geocoder(access_token=token)

def make_directions():
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        raise ValueError("MAPBOX_TOKEN not set")
    return Directions(access_token=token)

# ─── GEOCODING & DISTANCE ─────────────────────────────────────────────────────

def get_candidates(name: str) -> list:
    geocoder = make_geocoder()
    resp = geocoder.forward(name, limit=5)
    resp.raise_for_status()
    return resp.json().get("features", [])

def great_circle(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Haversine formula: returns distance in miles.
    """
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def mapbox_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Use Mapbox Directions API to compute driving distance, then convert meters→miles.
    """
    directions = make_directions()
    resp = directions.directions([lon1, lat1], [lon2, lat2], profile="driving")
    resp.raise_for_status()
    data = resp.json()
    routes = data.get("routes", [])
    if not routes:
        raise ValueError("No route found")
    dist_m = routes[0]["distance"]  # in meters
    return dist_m * 0.000621371  # meters → miles

# ─── RESOLUTION LOGIC ─────────────────────────────────────────────────────────

def resolve_place(
    name: Optional[str],
    code: Optional[str] = None
) -> Tuple[float, float, bool, bool, str]:
    """
    Return (lat, lon, ambiguous_flag, used_unlocode_flag, source).
      - source is one of "UNLOCODE" or "MAPBOX".
    """
    # 1) Try explicit LOCODE
    r = try_unlocode(code)
    if r:
        lat, lon, src = r
        logger.debug(f"used UNLOCODE for code='{code.strip().upper()}'")
        return lat, lon, False, True, src

    # 2) Try LOCODE from name string
    r2 = try_unlocode(name)
    if r2:
        lat, lon, src = r2
        logger.debug(f"used UNLOCODE for code derived from name='{name.strip().upper()}'")
        return lat, lon, False, True, src

    # 3) Fallback to Mapbox
    logger.debug(f"falling back to Mapbox for name='{name}'")
    candidates = get_candidates(name)
    if len(candidates) == 1:
        lon_m, lat_m = candidates[0]["geometry"]["coordinates"]
        return lat_m, lon_m, False, False, "MAPBOX"

    # 4) Handle multiple candidates
    if candidates:
        lon_m, lat_m = candidates[0]["geometry"]["coordinates"]
        return lat_m, lon_m, True, False, "MAPBOX"

    # 5) No result at all
    raise ValueError(f"Could not geocode '{name}'")

# ─── COMMAND-LINE ENTRYPOINT ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input CSV/XLSX file")
    parser.add_argument("-o", "--output", required=True, help="Output path")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    inp = Path(args.input)
    df = (
        pd.read_csv(inp, dtype=str)
        if inp.suffix.lower() == ".csv"
        else pd.read_excel(inp, dtype=str)
    )

    results = []
    for _, row in df.iterrows():
        name_o, code_o = row.get("Origin"), row.get("Origin_LOCODE")
        name_d, code_d = row.get("Destination"), row.get("Dest_LOCODE")

        lat_o, lon_o, amb_o, used_o, src_o = resolve_place(name_o, code_o)
        lat_d, lon_d, amb_d, used_d, src_d = resolve_place(name_d, code_d)

        used_both = used_o and used_d
        if used_both:
            dist = great_circle(lat_o, lon_o, lat_d, lon_d)
        else:
            try:
                dist = mapbox_distance(lat_o, lon_o, lat_d, lon_d)
            except Exception:
                dist = great_circle(lat_o, lon_o, lat_d, lon_d)

        # Determine combined source tag
        source = src_o if src_o == src_d else ",".join(filter(None, [src_o, src_d]))

        out = row.to_dict()
        out.update({
            "Origin_latitude":       lat_o,
            "Origin_longitude":      lon_o,
            "Destination_latitude":  lat_d,
            "Destination_longitude": lon_d,
            "Distance_miles":        dist,
            "Used_UNLOCODEs":        used_both,
            "Source":                source,
            "Ambiguous_Origin":      amb_o,
            "Ambiguous_Destination": amb_d,
        })
        results.append(out)

    out_df = pd.DataFrame(results)
    out_path = Path(args.output)
    if out_path.suffix.lower() == ".csv":
        out_df.to_csv(out_path, index=False)
    else:
        out_df.to_excel(out_path, index=False)

if __name__ == "__main__":
    main()
