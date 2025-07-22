#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

# ───────────────────────────────────────────────────────────────────────────────
# 1) Point at your files
# ───────────────────────────────────────────────────────────────────────────────
MASTER_CSV = Path("data/unlocode_master.csv")
FILLS_CSV  = Path("data/mapbox_filled_coords.csv")
OUTPUT_CSV = Path("data/unlocode_master_updated.csv")  # we’ll write a new one to be safe

# ───────────────────────────────────────────────────────────────────────────────
# 2) Load both as DataFrames
# ───────────────────────────────────────────────────────────────────────────────
master = pd.read_csv(MASTER_CSV, dtype=str)
fills  = pd.read_csv(FILLS_CSV,  dtype=str)

# Ensure lat/lon columns are numeric (so blanks become NaN)
master["Latitude"]  = pd.to_numeric(master["Latitude"],  errors="coerce")
master["Longitude"] = pd.to_numeric(master["Longitude"], errors="coerce")
fills["Latitude"]   = pd.to_numeric(fills["Latitude"],   errors="coerce")
fills["Longitude"]  = pd.to_numeric(fills["Longitude"],  errors="coerce")

# ───────────────────────────────────────────────────────────────────────────────
# 3) Merge them on your LOCODE key (here it’s named "code")
# ───────────────────────────────────────────────────────────────────────────────
merged = master.merge(
    fills,
    on="code",
    how="left",
    suffixes=("", "_filled")
)

# ───────────────────────────────────────────────────────────────────────────────
# 4) Wherever master was blank, pull in the filled values
# ───────────────────────────────────────────────────────────────────────────────
merged["Latitude"]  = merged["Latitude"].fillna(merged["Latitude_filled"])
merged["Longitude"] = merged["Longitude"].fillna(merged["Longitude_filled"])

# ───────────────────────────────────────────────────────────────────────────────
# 5) Drop the helper columns we no longer need
# ───────────────────────────────────────────────────────────────────────────────
merged.drop(columns=["Latitude_filled", "Longitude_filled"], inplace=True)

# ───────────────────────────────────────────────────────────────────────────────
# 6) Save out the updated master
# ───────────────────────────────────────────────────────────────────────────────
merged.to_csv(OUTPUT_CSV, index=False)
print(f"Wrote updated master with baked coords → {OUTPUT_CSV}")
