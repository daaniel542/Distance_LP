# lane_distance.py
#!/usr/bin/env python3
"""
Lane Distance Calculator (Mapbox + Coordinates Edition)
-------------------------------------------------------
Reads a CSV/XLSX with columns 'Origin' and 'Destination',
geocodes each via Mapbox to get latitude & longitude,
computes straight-line distances in miles,
and outputs a file with Origin, Destination,
origin_lat, origin_lon, destination_lat, destination_lon, and Distance_mi.
"""

import os
from dotenv import load_dotenv
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
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        sys.exit("❌ MAPBOX_TOKEN not set. Put it in a .env file or environment.")
    mb = Geocoder(access_token=token)
    forward = RateLimiter(mb.forward, min_delay_seconds=1, max_retries=2, error_wait_seconds=5)

    def _forward(place: str):
        try:
            resp = forward(place, limit=1)
            data = resp.geojson()
            feats = data.get("features") or []
            if not feats:
                return None, None
            lon, lat = feats[0]["geometry"]["coordinates"]
            return lat, lon
        except Exception as e:
            logging.warning(f"[geocode] error for '{place}': {e}")
            return None, None

    return _forward


def process_file(infile: pathlib.Path, outfile: pathlib.Path = None) -> pathlib.Path:
    suffix = infile.suffix.lower()
    # read input
    if suffix in (".xls", ".xlsx"):
        df = pd.read_excel(infile)
    else:
        df = pd.read_csv(infile)

    geocode = make_mapbox_geocoder()

    # apply geocoding: latitude & longitude
    orig_coords = df["Origin"].apply(
        lambda p: pd.Series(geocode(p), index=["origin_lat", "origin_lon"])
    )
    dest_coords = df["Destination"].apply(
        lambda p: pd.Series(geocode(p), index=["destination_lat", "destination_lon"])
    )
    df = pd.concat([df, orig_coords, dest_coords], axis=1)

    # compute distances
    def compute_distance(row):
        if None in (
            row.origin_lat, row.origin_lon,
            row.destination_lat, row.destination_lon
        ):
            return None
        return geodesic(
            (row.origin_lat, row.origin_lon),
            (row.destination_lat, row.destination_lon)
        ).miles

    df["Distance_mi"] = df.apply(compute_distance, axis=1)

    # select required columns
    out_df = df[[
        "Origin", "Destination",
        "origin_lat", "origin_lon",
        "destination_lat", "destination_lon",
        "Distance_mi"
    ]]

    # determine output path
    if outfile is None:
        outfile = infile.with_name(f"{infile.stem}_processed{infile.suffix}")

    # write output
    if outfile.suffix.lower() in (".xls", ".xlsx"):
        out_df.to_excel(outfile, index=False)
    else:
        out_df.to_csv(outfile, index=False)

    return outfile


def main():
    parser = argparse.ArgumentParser(description="Compute lane distances with coords.")
    parser.add_argument("infile", type=pathlib.Path, help="CSV or XLSX input file")
    parser.add_argument("-o", "--out", type=pathlib.Path, help="Output file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s | %(message)s"
    )

    if not args.infile.exists():
        sys.exit(f"❌ Input not found: {args.infile}")

    out = process_file(args.infile, args.out)
    logging.info(f"✅ Written to {out}")


if __name__ == "__main__":
    main()