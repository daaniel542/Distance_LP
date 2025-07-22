import os
import argparse
import pandas as pd
import re
import math
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2
from typing import Optional, Tuple, List
from mapbox import Geocoder, Directions
import streamlit as st

# Clear Streamlit cache if loaded in-app
if 'cache_data' in dir(st):
    st.cache_data.clear()

# ─── UN/LOCODE setup ────────────────────────────────────────────────────────────
UNLOCODE_CSV = Path("unlocode_clean.csv")

if UNLOCODE_CSV.exists():
    _unloc_df = (
        pd.read_csv(UNLOCODE_CSV, dtype=str, encoding='latin-1')
          .assign(locode=lambda df: df["LOCODE"].str.strip().str.upper())
    )
    _unloc_lookup = {
        idx: (float(row["Latitude"]), float(row["Longitude"]))
        for idx, row in _unloc_df.set_index("locode").iterrows()
        if row.get("Latitude") and row.get("Longitude")
    }
else:
    _unloc_lookup = {}

LOCODE_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}$")


def try_unlocode(s: Optional[str]) -> Optional[Tuple[float, float, bool]]:
    """
    Return (lat, lon, False) if s is a valid LOCODE with both coords;
    otherwise return None.
    """
    if not isinstance(s, str):
        return None
    code = s.strip().upper()
    if LOCODE_RE.match(code) and code in _unloc_lookup:
        lat, lon = _unloc_lookup[code]
        # if either coordinate is missing/NaN, treat as not found
        if lat is None or lon is None or math.isnan(lat) or math.isnan(lon):
            return None
        return lat, lon, False
    return None


def split_city_country(place: str) -> Tuple[str, str]:
    if ',' in place:
        parts = [p.strip() for p in place.split(',')]
        return parts[0], parts[-1]
    return place, ""


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


def make_directions():
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        raise ValueError("MAPBOX_TOKEN not set")
    return Directions(access_token=token)


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
            cat = f.get("properties", {}).get("category", "") or ""
            if any(tag in cat.lower() for tag in categories):
                filtered.append(f)
        features = filtered
    # dedupe by rounded coords
    seen = {}
    for f in features:
        lon, lat = f["geometry"]["coordinates"]
        key = (round(lat, 3), round(lon, 3))
        seen.setdefault(key, []).append(f)
    return [v[0] for v in seen.values()]


def guess_port_type(text: str) -> Optional[str]:
    hints = {
        "airport": ("AIRPORT", "APT", "INT", "IAA", "IAP", "AEROPUERTO"),
        "seaport": ("PORT", "HARBOR", "HARBOUR", "MARINE", "TERMINAL", "MUELLE"),
    }
    up = text.upper()
    for ptype, tags in hints.items():
        if any(tag in up for tag in tags):
            return ptype
    return None


def great_circle(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Returns the straight-line (great-circle) distance in miles.
    """
    R = 3958.8  # Earth’s radius in miles
    φ1, φ2 = radians(lat1), radians(lat2)
    dφ = radians(lat2 - lat1)
    dλ = radians(lon2 - lon1)
    a = sin(dφ / 2)**2 + cos(φ1) * cos(φ2) * sin(dλ / 2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def mapbox_distance(lat1, lon1, lat2, lon2) -> float:
    """
    Uses Mapbox Directions API (driving) to get route distance.
    Returns miles.
    """
    dirs = make_directions()
    response = dirs.directions(
        [(lon1, lat1), (lon2, lat2)],
        profile="driving",
        geometries="geojson",
        alternatives=False
    )
    data = response.geojson()
    feat = data.get("features", [])
    if not feat:
        raise ValueError("No route found via Mapbox")
    dist_m = feat[0]["properties"]["distance"]
    return dist_m / 1609.344


def resolve_place(name: Optional[str], code: Optional[str] = None) -> Tuple[float, float, bool, bool]:
    # 1) Try by LOCODE code field
    res = try_unlocode(code)
    if res:
        lat, lon, _ = res
        print(f"[DEBUG] used UNLOCODE for code={code!r}")
        return lat, lon, False, True

    # 2) Try by LOCODE name field
    res2 = try_unlocode(name)
    if res2:
        lat, lon, _ = res2
        print(f"[DEBUG] used UNLOCODE for name={name!r}")
        return lat, lon, False, True

    # 3) Mapbox geocoding fallback
    print(f"[DEBUG] falling back to Mapbox for name={name!r}")
    cand = get_candidates(name)

    if len(cand) == 1:
        lon, lat = cand[0]["geometry"]["coordinates"]
        return lat, lon, False, False

    ptype = guess_port_type(name)
    if ptype:
        cat_map = {"airport": ("airport",), "seaport": ("seaport","harbour","port")}
        pc = get_candidates(name, types=("poi",), categories=cat_map[ptype])
        if pc:
            lon, lat = pc[0]["geometry"]["coordinates"]
            amb = len(pc) > 1
            return lat, lon, amb, False

    if cand:
        lon, lat = cand[0]["geometry"]["coordinates"]
        amb = len(cand) > 1
        return lat, lon, amb, False

    raise ValueError(f"No candidates for '{name}' / '{code}'")


def main():
    parser = argparse.ArgumentParser(description="Calculate distances.")
    parser.add_argument("input_file", help="CSV or Excel with origin/destination")
    parser.add_argument("-o", "--output", required=True, help="Output CSV/XLSX")
    args = parser.parse_args()

    ext = Path(args.input_file).suffix.lower()
    df = (
        pd.read_excel(args.input_file, dtype=str)
        if ext in (".xls", ".xlsx")
        else pd.read_csv(args.input_file, dtype=str)
    )

    for col in [
        "origin_latitude", "origin_longitude",
        "destination_latitude", "destination_longitude",
        "is_origin_ambiguous", "is_destination_ambiguous",
        "distance_miles", "used_UNLOCODEs", "error_msg"
    ]:
        df[col] = None

    cols_l = [c.lower() for c in df.columns]
    origin_code_col = next(
        (c for lc, c in zip(cols_l, df.columns) if "origin" in lc and "locode" in lc),
        None
    )
    dest_code_col = next(
        (c for lc, c in zip(cols_l, df.columns)
         if ("dest" in lc or "destination" in lc) and "locode" in lc),
        None
    )

    results = []
    for _, row in df.iterrows():
        # origin
        name_o = row.get("Origin") or row.get("origin")
        code_o = row.get(origin_code_col) if origin_code_col else None
        try:
            lat_o, lon_o, amb_o, used_o = resolve_place(name_o, code_o)
            err_o = ""
        except Exception as e:
            lat_o = lon_o = None
            amb_o = True
            used_o = False
            err_o = str(e)

        # destination
        name_d = row.get("Destination") or row.get("destination")
        code_d = row.get(dest_code_col) if dest_code_col else None
        try:
            lat_d, lon_d, amb_d, used_d = resolve_place(name_d, code_d)
            err_d = ""
        except Exception as e:
            lat_d = lon_d = None
            amb_d = True
            used_d = False
            err_d = str(e)

        # flag unambiguous if both from LOCODE
        used_both = bool(used_o and used_d)
        if used_both:
            amb_o = amb_d = False

        # distance: LOCODE both → great_circle; else mapbox → fallback to great_circle
        distance = None
        err_any = err_o or err_d
        if not err_any and None not in (lat_o, lon_o, lat_d, lon_d):
            if used_both:
                distance = great_circle(lat_o, lon_o, lat_d, lon_d)
            else:
                try:
                    distance = mapbox_distance(lat_o, lon_o, lat_d, lon_d)
                except Exception:
                    distance = great_circle(lat_o, lon_o, lat_d, lon_d)

        results.append({
            "origin_latitude": lat_o,
            "origin_longitude": lon_o,
            "destination_latitude": lat_d,
            "destination_longitude": lon_d,
            "is_origin_ambiguous": amb_o,
            "is_destination_ambiguous": amb_d,
            "distance_miles": distance,
            "used_UNLOCODEs": used_both,
            "error_msg": err_any
        })

    out_df = pd.concat([df, pd.DataFrame(results)], axis=1)
    out_path = Path(args.output)
    if out_path.suffix.lower() in (".xls", ".xlsx"):
        out_df.to_excel(out_path, index=False)
    else:
        out_df.to_csv(out_path, index=False)


if __name__ == "__main__":
    main()
