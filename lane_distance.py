# lane_distance.py

import argparse
import pandas as pd
import re
import os
import sys
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2
from typing import Optional, Tuple, List
from mapbox import Geocoder

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

def try_unlocode(s: str) -> Optional[Tuple[float, float, bool]]:
    code = s.strip().upper()
    if is_unlocode(code) and code in _unloc_lookup:
        lat, lon = _unloc_lookup[code]
        return lat, lon, False
    return None

# ─── Utility functions ───

def split_city_country(place: str) -> Tuple[str, str]:
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

# ─── Mapbox forwarder ───

def make_forwarder():
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        raise ValueError("MAPBOX_TOKEN not set")
    return Geocoder(access_token=token)

# ─── Port-specific hints ───
PORT_HINTS = {
    "airport": ("AIRPORT", "APT", "INTL", "IAA", "IAP", "AEROPUERTO"),
    "seaport": ("PORT", "HARBOR", "HARBOUR", "MARINE", "TERMINAL", "MUELLE"),
}

def guess_port_type(text: str) -> Optional[str]:
    up = text.upper()
    for ptype, hints in PORT_HINTS.items():
        if any(h in up for h in hints):
            return ptype
    return None

# ─── Geocoding candidates with manual category filtering ───

def get_candidates(
    place: str,
    limit: int = 5,
    types: Tuple[str, ...] = ("place", "locality"),
    categories: Optional[Tuple[str, ...]] = None
) -> List[dict]:
    forward = make_forwarder()
    city, country = split_city_country(place)
    iso2 = to_iso2(country)
    params = {"limit": limit, "types": list(types)}
    if iso2:
        params["country"] = [iso2.lower()]
    # Perform forward geocoding without categories
    resp = forward.forward(city, **params)
    features = resp.geojson().get("features", [])
    # If categories provided, filter locally by feature.properties.category
    if categories:
        filtered = []
        for f in features:
            cat_field = f.get("properties", {}).get("category", "") or ""
            if any(cat in cat_field.lower() for cat in categories):
                filtered.append(f)
        features = filtered
    # collapse near-duplicate coordinates (~100m)
    seen = {}
    for f in features:
        lon, lat = f["geometry"]["coordinates"]
        key = (round(lat, 3), round(lon, 3))
        seen.setdefault(key, []).append(f)
    return [v[0] for v in seen.values()]

# ─── Distance formula ───

def great_circle(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.8
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))

# ─── Resolver with port-specific funnel ───

def resolve_place(place: str) -> Tuple[Optional[float], Optional[float], bool]:
    un = try_unlocode(place)
    if un is not None:
        return un

    general = get_candidates(place)
    if len(general) == 1:
        lon, lat = general[0]["geometry"]["coordinates"]
        return lat, lon, False

    ptype = guess_port_type(place)
    if ptype:
        cat_map = {
            "airport": ("airport",),
            "seaport": ("seaport", "harbour", "port"),
        }
        port_cand = get_candidates(place, types=("poi",), categories=cat_map[ptype])
        if port_cand:
            lon, lat = port_cand[0]["geometry"]["coordinates"]
            return lat, lon, len(port_cand) > 1

    if general:
        lon, lat = general[0]["geometry"]["coordinates"]
        return lat, lon, len(general) > 1

    raise ValueError(f"No Mapbox candidates for '{place}'")

# ─── Main CLI ───

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
        "distance_miles",
        "error_msg"
    ]:
        df[col] = None

    for idx, row in df.iterrows():
        try:
            lat_o, lon_o, o_amb = resolve_place(row['origin'])
            error_o = None
        except Exception as e:
            lat_o = lon_o = None
            o_amb = True
            error_o = str(e)
        try:
            lat_d, lon_d, d_amb = resolve_place(row['destination'])
            error_d = None
        except Exception as e:
            lat_d = lon_d = None
            d_amb = True
            error_d = str(e)

        error_msg = error_o or error_d or ""
        distance = None
        if not error_msg:
            distance = great_circle(lat_o, lon_o, lat_d, lon_d)

        df.at[idx, 'origin_latitude'] = lat_o
        df.at[idx, 'origin_longitude'] = lon_o
        df.at[idx, 'destination_latitude'] = lat_d
        df.at[idx, 'destination_longitude'] = lon_d
        df.at[idx, 'is_origin_ambiguous'] = o_amb
        df.at[idx, 'is_destination_ambiguous'] = d_amb
        df.at[idx, 'distance_miles'] = distance
        df.at[idx, 'error_msg'] = error_msg

    output_path = Path(args.output)
    if output_path.suffix.lower() in [".xls", ".xlsx"]:
        df.to_excel(output_path, index=False)
    else:
        df.to_csv(output_path, index=False)

if __name__ == "__main__":
    main()

