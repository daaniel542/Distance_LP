# lane_distance.py
#!/usr/bin/env python3
"""
Lane Distance Calculator (Mapbox Hybrid Disambiguation)
------------------------------------------------------
– Uses Mapbox to look up up to 5 candidates per city/query
– Filters to only `place` / `locality` types (drops regions/districts)
– CLI always picks the first (largest) filtered match
– Outputs Origin, Destination, origin_lat, origin_lon,
  destination_lat, destination_lon, Distance_mi
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


def make_forwarder():
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        sys.exit("❌ MAPBOX_TOKEN not set. Put it in your .env or env vars.")
    mb = Geocoder(access_token=token)
    return RateLimiter(mb.forward, min_delay_seconds=1, max_retries=2, error_wait_seconds=5)


def get_candidates(place: str):
    forward = make_forwarder()
    resp = forward(place, limit=5)
    feats = resp.geojson().get("features") or []
    places = [f for f in feats if f.get("place_type", [None])[0] in ("place","locality")]
    return places if places else feats


def geocode_primary(place: str):
    cands = get_candidates(place)
    if not cands:
        return None, None
    lon, lat = cands[0]["geometry"]["coordinates"]
    return lat, lon


def process_file(infile: pathlib.Path, outfile: pathlib.Path = None) -> pathlib.Path:
    if infile.suffix.lower() in (".xls",".xlsx"):
        df = pd.read_excel(infile)
    else:
        df = pd.read_csv(infile)

    df["origin_lat"], df["origin_lon"] = zip(*df["Origin"].apply(geocode_primary))
    df["destination_lat"], df["destination_lon"] = zip(*df["Destination"].apply(geocode_primary))

    def compute(r):
        if None in (r.origin_lat, r.origin_lon, r.destination_lat, r.destination_lon):
            return None
        return geodesic((r.origin_lat, r.origin_lon), (r.destination_lat, r.destination_lon)).miles
    df["Distance_mi"] = df.apply(compute, axis=1)

    out_df = df[[
        "Origin","Destination",
        "origin_lat","origin_lon",
        "destination_lat","destination_lon",
        "Distance_mi"
    ]]

    if not outfile:
        outfile = infile.with_name(f"{infile.stem}_processed{infile.suffix}")
    if outfile.suffix.lower() in (".xls",".xlsx"):
        out_df.to_excel(outfile, index=False)
    else:
        out_df.to_csv(outfile, index=False)
    return outfile


def main():
    p = argparse.ArgumentParser(description="Compute lane distances (hybrid disambiguation).")
    p.add_argument("infile", type=pathlib.Path, help="CSV/XLSX input file")
    p.add_argument("-o","--out", type=pathlib.Path, help="Output file path")
    p.add_argument("-v","--verbose", action="store_true", help="Verbose logging")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s | %(message)s"
    )
    if not args.infile.exists():
        sys.exit(f"❌ Input file not found: {args.infile}")
    out = process_file(args.infile, args.out)
    logging.info(f"✅ Written results to {out}")


if __name__ == "__main__":
    main()
