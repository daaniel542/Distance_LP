#!/usr/bin/env python3
"""
Lane Distance Calculator (Mapbox Edition)
-----------------------------------------
Reads a CSV/XLSX with columns 'Origin' and 'Destination',
geocodes each via Mapbox, computes straight-line (great-circle)
distances in miles, and writes out a new file with a 'Distance_mi' column.
"""

import os
from dotenv import load_dotenv      # ← load .env at import time
load_dotenv()

import sys
import argparse
import logging
import pathlib

import pandas as pd
from mapbox import Geocoder
from geopy.distance import geodesic
from geopy.extra.rate_limiter import RateLimiter

def make_mapbox_geocoder():
    """Return a rate-limited Mapbox forward geocoder."""
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        sys.exit("❌ MAPBOX_TOKEN not set. Put it in a .env file or env vars.")
    mb = Geocoder(access_token=token)
    return RateLimiter(mb.forward, min_delay_seconds=1, max_retries=2, error_wait_seconds=5)

def process_file(infile: pathlib.Path, outfile: pathlib.Path = None) -> pathlib.Path:
    """
    Read infile (CSV or Excel), compute distances, write to outfile,
    and return outfile path.
    """
    suffix = infile.suffix.lower()
    if suffix in (".xls", ".xlsx"):
        df = pd.read_excel(infile)
    else:
        df = pd.read_csv(infile)

    geocode = make_mapbox_geocoder()

    # helper to get (lat,lon) or (None, None)
    def coords(place: str):
        try:
            resp = geocode(place, limit=1)
            data = resp.geojson()
            feats = data.get("features") or []
            if not feats:
                return None, None
            lng, lat = feats[0]["geometry"]["coordinates"]
            return lat, lng
        except Exception as e:
            logging.warning(f"Geocode error for '{place}': {e}")
            return None, None

    # apply geocoding
    df[["orig_lat", "orig_lon"]] = df["Origin"].apply(lambda s: pd.Series(coords(s)))
    df[["dest_lat", "dest_lon"]] = df["Destination"].apply(lambda s: pd.Series(coords(s)))

    # compute distance
    def compute(row):
        if None in (row.orig_lat, row.orig_lon, row.dest_lat, row.dest_lon):
            return None
        return geodesic((row.orig_lat, row.orig_lon), (row.dest_lat, row.dest_lon)).miles

    df["Distance_mi"] = df.apply(compute, axis=1)

    # determine output path
    if outfile is None:
        outfile = infile.with_name(f"{infile.stem}_processed{infile.suffix}")

    # write
    if outfile.suffix.lower() in (".xls", ".xlsx"):
        df.to_excel(outfile, index=False)
    else:
        df.to_csv(outfile, index=False)

    return outfile

def main():
    p = argparse.ArgumentParser(description="Compute lane distances.")
    p.add_argument("infile", type=pathlib.Path, help="CSV or XLSX input")
    p.add_argument("-o", "--out", type=pathlib.Path, help="Output file path")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s | %(message)s"
    )

    if not args.infile.exists():
        sys.exit(f"❌ Input not found: {args.infile}")

    out = process_file(args.infile, args.out)
    logging.info(f"✅ Written results to {out}")

if __name__ == "__main__":
    main()
