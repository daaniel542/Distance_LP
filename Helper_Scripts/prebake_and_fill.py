#!/usr/bin/env python3
import os
import time
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from lane_distance import get_candidates

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()  # loads MAPBOX_TOKEN from .env
if not os.getenv("MAPBOX_TOKEN"):
    raise RuntimeError("MAPBOX_TOKEN not set in environment or .env")

MASTER_CSV    = Path("unlocode_master.csv")          # your merged clean+WKT
FILLS_CSV     = Path("mapbox_filled_coords.csv")     # persistent store of past fills
OUTPUT_CSV    = Path("unlocode_master_prebaked.csv") # final output
PAUSE_SECONDS = 0.2                                  # avoid rate‐limit

# ─────────────────────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────
df_master = pd.read_csv(MASTER_CSV, dtype=str)
# coerce blanks to NaN so merge/fill works
df_master["Latitude"]  = pd.to_numeric(df_master["Latitude"],  errors="coerce")
df_master["Longitude"] = pd.to_numeric(df_master["Longitude"], errors="coerce")

if FILLS_CSV.exists():
    df_fills = pd.read_csv(FILLS_CSV, dtype=str)
    df_fills["Latitude"]  = pd.to_numeric(df_fills["Latitude"],  errors="coerce")
    df_fills["Longitude"] = pd.to_numeric(df_fills["Longitude"], errors="coerce")
else:
    df_fills = pd.DataFrame(columns=["code","Latitude","Longitude"])

# ─────────────────────────────────────────────────────────────────────────────
# MERGE IN EXISTING FILLS
# ─────────────────────────────────────────────────────────────────────────────
df = df_master.merge(
    df_fills,
    on="code",
    how="left",
    suffixes=("", "_fill")
)
df["Latitude"]  = df["Latitude"].fillna(df["Latitude_fill"])
df["Longitude"] = df["Longitude"].fillna(df["Longitude_fill"])
df.drop(columns=["Latitude_fill","Longitude_fill"], inplace=True)

# ─────────────────────────────────────────────────────────────────────────────
# FIND CODES STILL MISSING
# ─────────────────────────────────────────────────────────────────────────────
mask_missing = df["Latitude"].isna() | df["Longitude"].isna()
missing_codes = pd.unique(df.loc[mask_missing, "code"])
print(f"→ {len(missing_codes)} unique codes still need coords")

# ─────────────────────────────────────────────────────────────────────────────
# CALL MAPBOX FOR JUST THOSE
# ─────────────────────────────────────────────────────────────────────────────
new_rows = []
for code in missing_codes:
    time.sleep(PAUSE_SECONDS)
    try:
        feats = get_candidates(code)
        if not feats:
            print(f"  ✗ {code}: no Mapbox result")
            continue

        lon, lat = feats[0]["geometry"]["coordinates"]
        print(f"  ✓ {code}: {lat:.5f}, {lon:.5f}")
        # fill DataFrame
        df.loc[df["code"] == code, ["Latitude","Longitude"]] = (lat, lon)
        # remember for next time
        new_rows.append({"code":code, "Latitude":lat, "Longitude":lon})

    except Exception as e:
        print(f"  ✗ {code}: error {e}")

# ─────────────────────────────────────────────────────────────────────────────
# UPDATE FILLS CSV (append only brand‐new ones)
# ─────────────────────────────────────────────────────────────────────────────
if new_rows:
    df_new = pd.DataFrame(new_rows)
    df_fills = pd.concat([df_fills, df_new], ignore_index=True)
    df_fills.drop_duplicates(subset=["code"], keep="first", inplace=True)
    df_fills.to_csv(FILLS_CSV, index=False)
    print(f"\n✅ Appended {len(new_rows)} new fills → {FILLS_CSV}")

# ─────────────────────────────────────────────────────────────────────────────
# WRITE FINAL PRE-BAKED MASTER
# ─────────────────────────────────────────────────────────────────────────────
df.to_csv(OUTPUT_CSV, index=False)
print(f"✅ Wrote full pre-baked master → {OUTPUT_CSV} ({len(df)} rows)")
