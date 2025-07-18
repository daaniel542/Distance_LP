#!/usr/bin/env python3
"""
Lane Distance Calculator (Mapbox Edition)
-----------------------------------------
Calculates crow-flight distances between origin and destination cities.
"""

import os
import sys
import re
import argparse
import logging
import pathlib
import sqlite3
from typing import Optional, Tuple, List, Callable, Dict, Union

import pandas as pd
from mapbox import Geocoder
from geopy.distance import geodesic
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderUnavailable

DEFAULT_CACHE_DB = pathlib.Path("city_cache.sqlite")
EXPECTED_COLS = ["origin", "destination", "lane_distance_mi"]

# --------------------------------------------------
def open_cache(db_path: Union[str, pathlib.Path] = DEFAULT_CACHE_DB
) -> sqlite3.Connection:
    """Open or create the SQLite cache."""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coords (
                place TEXT PRIMARY KEY,
                lat   REAL,
                lon   REAL
            )
        """)
        return conn
    except sqlite3.OperationalError as e:
        sys.exit(f"❌ Cannot open cache DB '{db_path}': {e}")

# --------------------------------------------------
def clean_place(raw: object) -> Optional[str]:
    """Standardize place names: trim, uppercase, remove punctuation."""
    if pd.isna(raw):
        return None
    s = re.sub(r"\s+", " ", str(raw).strip()).upper().strip(".,;:")
    return s or None

# --------------------------------------------------
def make_mapbox_geocoder() -> Callable[[str], Optional[object]]:
    """Build a RateLimiter-wrapped Mapbox geocoder."""
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        sys.exit("❌ Please set your Mapbox token via export MAPBOX_TOKEN=...")
    mb = Geocoder(access_token=token)

    def _forward(place: str):
        try:
            resp = mb.forward(place, limit=1)
            data = resp.geojson()
            features = data.get("features") or []
            if not features:
                return None
            lon, lat = features[0]["geometry"]["coordinates"]
            class Loc: pass
            loc = Loc()
            loc.latitude = lat
            loc.longitude = lon
            return loc
        except Exception as e:
            raise GeocoderUnavailable(f"Mapbox error: {e}")

    return RateLimiter(_forward, min_delay_seconds=1, max_retries=2, error_wait_seconds=5)

# ----------------------------------------
def geocode_place(
    place: Optional[str],
    geocode_func: Callable[[str], Optional[object]],
    cache_conn: sqlite3.Connection
) -> Optional[Tuple[float, float]]:
    """Geocode place from cache or via Mapbox."""
    if place is None:
        return None

    cache_conn.execute("""
        CREATE TABLE IF NOT EXISTS coords (
            place TEXT PRIMARY KEY,
            lat   REAL,
            lon   REAL
        )
    """)

    cur = cache_conn.execute("SELECT lat, lon FROM coords WHERE place = ?", (place,))
    row = cur.fetchone()
    if row:
        logging.debug(f"[cache] {place} → {row}")
        return row

    try:
        loc = geocode_func(place)
    except GeocoderUnavailable as e:
        logging.warning(f"[geocode] unavailable for '{place}': {e}")
        return None
    except Exception as e:
        logging.warning(f"[geocode] error for '{place}': {e}")
        return None

    if loc is None:
        logging.warning(f"[geocode] no result for '{place}'")
        return None

    cache_conn.execute(
        "INSERT OR REPLACE INTO coords(place, lat, lon) VALUES (?,?,?)",
        (place, loc.latitude, loc.longitude)
    )
    cache_conn.commit()
    logging.debug(f"[cache] saved {place} → ({loc.latitude}, {loc.longitude})")
    return (loc.latitude, loc.longitude)

# --------------------------------------------------
def distance_miles(
    p1: Optional[Tuple[float, float]],
    p2: Optional[Tuple[float, float]]
) -> float:
    """Calculate geodesic distance or return NaN."""
    if p1 is None or p2 is None:
        return float("nan")
    return geodesic(p1, p2).miles

# --------------------------------------------------
def calculate_distances(
    origins: List[str],
    destinations: List[str],
    geocode_func: Callable[[str], Optional[object]],
    cache_conn: sqlite3.Connection
) -> List[float]:
    """Core logic: map origin/destination → geocode → compute distance."""
    coords: Dict[str, Optional[Tuple[float, float]]] = {}
    for place in set(origins) | set(destinations):
        coords[place] = geocode_place(place, geocode_func, cache_conn)

    return [
        distance_miles(coords.get(o), coords.get(d))
        for o, d in zip(origins, destinations)
    ]

# --------------------------------------------------
def process_file(
    path_in: pathlib.Path,
    path_out: pathlib.Path,
) -> pd.DataFrame:
    """End-to-end file processor: clean, geocode, compute, write."""
    logging.info(f"▶ Reading {path_in}")
    
    ext = path_in.suffix.lower()
    try:
        df = pd.read_excel(path_in) if ext in (".xls", ".xlsx") else pd.read_csv(path_in)
    except Exception as e:
        sys.exit(f"❌ Failed to read '{path_in}': {e}")

    if df.shape[1] < 2:
        sys.exit(f"❌ Need at least 2 columns (origin, destination)")

    df = df.iloc[:, :2]
    df.columns = EXPECTED_COLS[:2]
    df["origin"]      = df["origin"].map(clean_place)
    df["destination"] = df["destination"].map(clean_place)

    before = len(df)
    df.dropna(subset=["origin", "destination"], inplace=True)
    # --- Reset index so distances align properly when assigned ---
    df.reset_index(drop=True, inplace=True)
    dropped = before - len(df)
    if dropped:
        logging.warning(f"Dropped {dropped} row(s) with blank city names")

    geocode_func = make_mapbox_geocoder()
    cache_conn   = open_cache()

    logging.info("▶ Geocoding & computing distances...")
    dists = calculate_distances(
        df["origin"].tolist(),
        df["destination"].tolist(),
        geocode_func,
        cache_conn
    )
    df["lane_distance_mi"] = pd.Series(dists).round(1)

    path_out.parent.mkdir(parents=True, exist_ok=True)
    logging.info(f"▶ Writing {path_out}")
    try:
        if ext == ".csv":
            df.to_csv(path_out, index=False)
        else:
            df.to_excel(path_out, index=False)
    except Exception as e:
        sys.exit(f"❌ Failed to write '{path_out}': {e}")

    cache_conn.close()
    return df

# --------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Crow-flight Lane Distance Calculator (Mapbox)")
    p.add_argument("infile", type=pathlib.Path, help="Input file (CSV or Excel)")
    p.add_argument("-o", "--out",   type=pathlib.Path, default=pathlib.Path("lane_output.csv"),
                   help="Output file (default: lane_output.csv)")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args = p.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s | %(message)s")

    if not args.infile.exists():
        sys.exit(f"❌ Input file not found: {args.infile}")

    try:
        process_file(args.infile, args.out)
        logging.info("✅ Done.")
    except KeyboardInterrupt:
        logging.error("❌ Interrupted.")
        sys.exit(1)

if __name__ == "__main__":
    main()
