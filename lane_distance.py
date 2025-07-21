# lane_distance.py

import argparse
import pandas as pd
import re
import os
import sys
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2
from mapbox import Geocoder

# ─── Mapbox forwarder ───

def make_forwarder():
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        raise ValueError("MAPBOX_TOKEN not set")
    return Geocoder(access_token=token)

# ─── Utility functions ───

def split_city_country(place: str):
    parts = [p.strip() for p in place.split(",")]
    city = parts[0]
    country = parts[1] if len(parts) > 1 else ""
    return city, country

def to_iso2(country: str) -> str:
    try:
        import pycountry
        return pycountry.countries.lookup(country).alpha_2
    except Exception:
        return ""

# ─── UN/LOCODE integration (optional) ───
UNLOCODE_CSV = Path("unlocode_2024-2.csv")
if UNLOCODE_CSV.exists():
    _unloc_df = (
        pd.read_csv(UNLOCODE_CSV, dtype=str)
          .assign(locode=lambda df: df["LOCODE"].str.strip().str.upper())
          .set_index("locode")
    )
    _unloc_lookup = {
        idx: (float(row["Latitude"]), float(row["Longitude"]))
        for idx, row in _unloc_df.iterrows()
    }
else:
    _unloc_lookup = {}

LOCODE_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}$")

def is_unlocode(s: str) -> bool:
    return bool(LOCODE_RE.match(s.strip().upper()))

def try_unlocode(s: str):
    code = s.strip().upper()
    if is_unlocode(code) and code in _unloc_lookup:
        lat, lon = _unloc_lookup[code]
        return lat, lon, False
    return None

# ─── Mapbox geocoding (with collapse logic) ───

def get_candidates(place: str, limit: int = 5):
    forward = make_forwarder()
    city, country = split_city_country(place)
    iso2 = to_iso2(country)
    params = {"limit": limit, "types": ["place", "locality"]}
    if iso2:
        params["country"] = [iso2.lower()]
    resp = forward.forward(city, **params)
    features = resp.geojson().get("features", [])
    seen = {}
    for f in features:
        lon, lat = f["geometry"]["coordinates"]
        key = (round(lat, 3), round(lon, 3))
        seen.setdefault(key, []).append(f)
    return [v[0] for v in seen.values()]

def geocode_with_mapbox(place: str):
    candidates = get_candidates(place)
    if not candidates:
        raise ValueError(f"No mapbox candidates for '{place}'")
    f = candidates[0]
    lon, lat = f["geometry"]["coordinates"]
    ambiguous = len(candidates) > 1
    return lat, lon, ambiguous

# ─── Distance formula ───

def great_circle(lat1, lon1, lat2, lon2):
    r = 3958.8
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))

# ─── Resolver ───

def resolve_place(place: str):
    un = try_unlocode(place)
    if un is not None:
        return un
    return geocode_with_mapbox(place)

# ─── CLI Entry Point ───

def main():
    parser = argparse.ArgumentParser(description="Calculate great-circle distances.")
    parser.add_argument("input_file", help="CSV or Excel with 'origin' and 'destination'")
    parser.add_argument("-o", "--output", required=True, help="Output path (CSV or Excel)")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if input_path.suffix.lower() in [".xls", ".xlsx"]:
        df = pd.read_excel(input_path)
    else:
        df = pd.read_csv(input_path)

    for col in ["origin", "destination"]:
        if col not in df.columns:
            print(f"Missing column '{col}'", file=sys.stderr)
            sys.exit(1)

    for col in [
        "origin_latitude", "origin_longitude",
        "destination_latitude", "destination_longitude",
        "is_origin_ambiguous", "is_destination_ambiguous",
        "distance_miles"
    ]:
        df[col] = None

    for idx, row in df.iterrows():
        lat_o, lon_o, amb_o = resolve_place(row['origin'])
        lat_d, lon_d, amb_d = resolve_place(row['destination'])
        df.at[idx, 'origin_latitude'] = lat_o
        df.at[idx, 'origin_longitude'] = lon_o
        df.at[idx, 'destination_latitude'] = lat_d
        df.at[idx, 'destination_longitude'] = lon_d
        df.at[idx, 'is_origin_ambiguous'] = amb_o
        df.at[idx, 'is_destination_ambiguous'] = amb_d
        df.at[idx, 'distance_miles'] = great_circle(lat_o, lon_o, lat_d, lon_d)

    output_path = Path(args.output)
    if output_path.suffix.lower() in [".xls", ".xlsx"]:
        df.to_excel(output_path, index=False)
    else:
        df.to_csv(output_path, index=False)

if __name__ == "__main__":
    main()