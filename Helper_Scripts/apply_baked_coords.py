#!/usr/bin/env python3
"""
apply_baked_coords.py

Merge your Mapbox‐filled lat/lon cache into your master UN/LOCODE file,
so that LOCODE is never empty and you combine both WKT and Mapbox coords
into a single, final master.
"""

import pandas as pd
from pathlib import Path

# ───────────────────────────────────────────────────────────────────────────────
# CONFIGURATION: adjust these paths if your folder layout differs
# ───────────────────────────────────────────────────────────────────────────────
HERE       = Path(__file__).parent
MASTER_CSV = HERE / "data" / "unlocode_master.csv"          # your current master (with WKT coords)
FILLS_CSV  = HERE / "data" / "mapbox_filled_coords.csv"      # your Mapbox cache
OUTPUT_CSV = HERE / "data" / "unlocode_master_filled.csv"    # merged result

# ───────────────────────────────────────────────────────────────────────────────
# LOAD
# ───────────────────────────────────────────────────────────────────────────────
master = pd.read_csv(MASTER_CSV, dtype=str)
fills  = pd.read_csv(FILLS_CSV,  dtype=str)

# ───────────────────────────────────────────────────────────────────────────────
# NORMALIZE & RENAME
# ───────────────────────────────────────────────────────────────────────────────
# 1) Make sure latitude/longitude are numeric
master["Latitude"]  = pd.to_numeric(master.get("Latitude"),  errors="coerce")
master["Longitude"] = pd.to_numeric(master.get("Longitude"), errors="coerce")
fills["Latitude"]   = pd.to_numeric(fills.get("Latitude"),   errors="coerce")
fills["Longitude"]  = pd.to_numeric(fills.get("Longitude"),  errors="coerce")

# 2) Rename the cache’s key column “code” → “LOCODE” so it matches master
if "code" in fills.columns:
    fills = fills.rename(columns={"code": "LOCODE"})

# ───────────────────────────────────────────────────────────────────────────────
# MERGE & FILL
# ───────────────────────────────────────────────────────────────────────────────
merged = master.merge(
    fills,
    on="LOCODE",
    how="left",
    suffixes=("", "_baked")
)

# For any rows where master has no lat/lon but fills does, take the baked values
merged["Latitude"]  = merged["Latitude"].fillna(merged["Latitude_baked"])
merged["Longitude"] = merged["Longitude"].fillna(merged["Longitude_baked"])

# Drop the temporary “_baked” columns
merged.drop(columns=["Latitude_baked", "Longitude_baked"], inplace=True)

# ───────────────────────────────────────────────────────────────────────────────
# SAVE
# ───────────────────────────────────────────────────────────────────────────────
merged.to_csv(OUTPUT_CSV, index=False)
print(f"✅ Wrote merged master → {OUTPUT_CSV}")
