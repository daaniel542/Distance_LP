# lane_distance.py

import os
import argparse
import pandas as pd
import re
import sys
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2
from typing import Optional, Tuple, List
from mapbox import Geocoder
import streamlit as st

# ─── Streamlit cache clear (if you ever import this in your app) ───
if 'cache_data' in dir(st):
    st.cache_data.clear()
if 'cache_resource' in dir(st):
    st.cache_resource.clear()

# ─── UN/LOCODE integration ───
UNLOCODE_CSV = Path("unlocode_clean.csv")

if UNLOCODE_CSV.exists():
    # Read with latin-1 to handle all special characters
    _unloc_df = pd.read_csv(UNLOCODE_CSV, dtype=str, encoding='latin-1') \
                  .assign(locode=lambda df: df["LOCODE"].str.strip().str.upper())
    _unloc_lookup = {
        idx: (
            float(row["Latitude"]),
            float(row["Longitude"])
        )
        for idx, row in _unloc_df.set_index("locode").iterrows()
        if row.get("Latitude") and row.get("Longitude")
    }
else:
    _unloc_lookup = {}

LOCODE_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}$")


def try_unlocode(s: Optional[str]) -> Optional[Tuple[float, float, bool]]:
    """
    Try to parse a UN/LOCODE string s and return (lat, lon, False)
    if successful, else None.
    """
    if not isinstance(s, str):
        return None
    code = s.strip().upper()
    if LOCODE_RE.match(code) and code in _unloc_lookup:
        lat, lon = _unloc_lookup[code]
        return lat, lon, False
    return None


# ─── Helpers for Mapbox fallback ───

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


def make_forwarder():
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        raise ValueError("MAPBOX_TOKEN not set")
    return Geocoder(access_token=token)

PORT_HINTS = {
    "airport": ("AIRPORT", "APT", "INT", "IAA", "IAP", "AEROPUERTO"),
    "seaport": ("PORT", "HARBOR", "HARBOUR", "MARINE", "TERMINAL", "MUELLE"),
}


def guess_port_type(text: str) -> Optional[str]:
    up = text.upper()
    for ptype, hints in PORT_HINTS.items():
        if any(h in up for h in hints):
            return ptype
    return None


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
    resp = forward.forward(city, **params)
    features = resp.geojson().get("features", [])
    if categories:
        filtered = []
        for f in features:
            cat_field = f.get("properties", {}).get("category", "") or ""
            if any(cat in cat_field.lower() for cat in categories):
                filtered.append(f)
        features = filtered
    seen = {}
    for f in features:
        lon, lat = f["geometry"]["coordinates"]
        key = (round(lat, 3), round(lon, 3))
        seen.setdefault(key, []).append(f)
    return [v[0] for v in seen.values()]


# ─── Great‐circle distance ───

def great_circle(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8  # Earth radius in miles
    φ1, φ2 = radians(lat1), radians(lat2)
    dφ = radians(lat2 - lat1)
    dλ = radians(lon2 - lon1)
    a = sin(dφ/2) ** 2 + cos(φ1) * cos(φ2) * sin(dλ/2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


# ─── Resolver: prefer UN/LOCODE, then Mapbox (with debug) ───

def resolve_place(name: Optional[str], code: Optional[str] = None) -> Tuple[Optional[float], Optional[float], bool, bool]:
    """
    Returns (lat, lon, ambiguous_flag, used_unlocode_flag)
    """
    # 1) Try on the LOCODE field
    res = try_unlocode(code)
    if res is not None:
        lat, lon, _ = res
        print(f"[DEBUG] used UNLOCODE for code={code!r}")  # Debug log
        return lat, lon, False, True

    # 2) Try on the name field itself
    res2 = try_unlocode(name)
    if res2 is not None:
        lat, lon, _ = res2
        print(f"[DEBUG] used UNLOCODE for name={name!r}")  # Debug log
        return lat, lon, False, True

    # 3) City‐level Mapbox lookup
    print(f"[DEBUG] falling back to Mapbox for name={name!r}")  # Debug log
    general = get_candidates(name)
    if len(general) == 1:
        lon, lat = general[0]["geometry"]["coordinates"]
        return lat, lon, False, False

    # 4) Port hint lookup
    ptype = guess_port_type(name)
    if ptype:
        cat_map = {"airport": ("airport",), "seaport": ("seaport", "harbour", "port")}
        port_cand = get_candidates(name, types=("poi",), categories=cat_map[ptype])
        if port_cand:
            lon, lat = port_cand[0]["geometry"]["coordinates"]
            return lat, lon, len(port_cand) > 1, False

    # 5) Fallback to top city candidate
    if general:
        lon, lat = general[0]["geometry"]["coordinates"]
        return lat, lon, len(general) > 1, False

    raise ValueError(f"No candidates for '{name}' / '{code}'")


# ─── Main CLI ───
def main():
    parser = argparse.ArgumentParser(description="Calculate great‐circle distances.")
    parser.add_argument("input_file", help="CSV or Excel file with origin/destination and optional LOCODEs")
    parser.add_argument("-o", "--output", required=True, help="Output path (CSV or XLSX)")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if input_path.suffix.lower() in [".xls", ".xlsx"]:
        df = pd.read_excel(input_path, dtype=str)
    else:
        df = pd.read_csv(input_path, dtype=str)

    # Prepare output columns
    for col in [
        "origin_latitude", "origin_longitude",
        "destination_latitude", "destination_longitude",
        "is_origin_ambiguous", "is_destination_ambiguous",
        "distance_miles", "used_UNLOCODEs", "error_msg"
    ]:
        df[col] = None

    # Identify LOCODE columns
    cols_lower = [c.lower() for c in df.columns]
    origin_code_col = next((c for lc, c in zip(cols_lower, df.columns) if "origin" in lc and "locode" in lc), None)
    dest_code_col   = next((c for lc, c in zip(cols_lower, df.columns) if ("dest" in lc or "destination" in lc) and "locode" in lc), None)

    results = []
    for idx, row in df.iterrows():
        name_o = row.get("Origin") or row.get("origin")
        code_o = row.get(origin_code_col) if origin_code_col else None
        name_d = row.get("Destination") or row.get("destination")
        code_d = row.get(dest_code_col) if dest_code_col else None

        try:
            lat_o, lon_o, amb_o, used_o = resolve_place(name_o, code_o)
            err_o = ""
        except Exception as e:
            lat_o = lon_o = None
            amb_o = True
            used_o = False
            err_o = str(e)

        try:
            lat_d, lon_d, amb_d, used_d = resolve_place(name_d, code_d)
            err_d = ""
        except Exception as e:
            lat_d = lon_d = None
            amb_d = True
            used_d = False
            err_d = str(e)

        used_both = bool(used_o and used_d)
        if used_both:
            amb_o = amb_d = ""

        distance = None
        if not (err_o or err_d) and None not in (lat_o, lon_o, lat_d, lon_d):
            distance = great_circle(lat_o, lon_o, lat_d, lon_d)

        results.append({
            "origin_latitude":      lat_o,
            "origin_longitude":     lon_o,
            "destination_latitude": lat_d,
            "destination_longitude":lon_d,
            "is_origin_ambiguous":  amb_o,
            "is_destination_ambiguous": amb_d,
            "distance_miles":       distance,
            "used_UNLOCODEs":       used_both,
            "error_msg":            err_o or err_d
        })

    out_df = pd.concat([df, pd.DataFrame(results)], axis=1)
    output_path = Path(args.output)
    if output_path.suffix.lower() in [".xls", ".xlsx"]:
        out_df.to_excel(output_path, index=False)
    else:
        out_df.to_csv(output_path, index=False)

if __name__ == "__main__":
    main()
