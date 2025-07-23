#!/usr/bin/env python3
import pandas as pd

# 1) your full master list
master = pd.read_csv("unlocode_master.csv", dtype=str)

# 2) what Mapbox has already returned
fills  = pd.read_csv("mapbox_filled_coords.csv", dtype=str)

# 3) merge on the correct key ("code", not "UNLOCODE")
master = master.merge(
    fills,
    on="code",
    how="left",
    suffixes=("", "_new")
)

# 4) fill only where master was blank
master["Latitude"] = master["Latitude"].fillna(master["Latitude_new"])
master["Longitude"] = master["Longitude"].fillna(master["Longitude_new"])

# 5) drop the auxiliary columns
master.drop(columns=["Latitude_new", "Longitude_new"], inplace=True)

# 6) write out your pre-baked master
master.to_csv("unlocode_master_prebaked.csv", index=False)

# 7) report how many still missing
missing = master["Latitude"].isna().sum() + master["Longitude"].isna().sum()
print(f"{missing} rows still missing either latitude or longitude.")
