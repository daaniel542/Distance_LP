# fill_master.py

from dotenv import load_dotenv
load_dotenv()                # ← loads MAPBOX_TOKEN (and any other vars) from .env

import pandas as pd
from pathlib import Path
from lane_distance import get_candidates
import time

INPUT  = Path("unlocode_master.csv")
OUTPUT = Path("unlocode_master_filled.csv")

def main():
    df = pd.read_csv(INPUT, dtype=str)
    df["Latitude"]  = pd.to_numeric(df["Latitude"],  errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # Find codes missing coords
    missing_codes = df.loc[df["Latitude"].isna() | df["Longitude"].isna(), "code"].unique()
    print(f"Found {len(missing_codes)} codes to fill via Mapbox.")

    for code in missing_codes:
        time.sleep(0.2)  # avoid rate‐limit
        try:
            feats = get_candidates(code)
            if feats:
                lon, lat = feats[0]["geometry"]["coordinates"]
                df.loc[df["code"] == code, ["Latitude","Longitude","src"]] = lat, lon, "MAPBOX"
                print(f"  ✓ {code}: {lat:.5f}, {lon:.5f}")
            else:
                print(f"  ✗ {code}: no Mapbox result")
        except Exception as e:
            print(f"  ✗ {code}: error {e}")

    df.to_csv(OUTPUT, index=False)
    print(f"\n✅ Wrote {OUTPUT} ({len(df)} rows).")

if __name__ == "__main__":
    main()
