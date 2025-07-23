#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

# ───────────────────────────────────────────────────────────────────────────────
# Adjust this if your file lives elsewhere
# ───────────────────────────────────────────────────────────────────────────────
IN_CSV  = Path("data/unlocode_master_updated.csv")
OUT_CSV = Path("data/unlocode_master_updated.csv")  # overwrite in place

# ───────────────────────────────────────────────────────────────────────────────
# Load
# ───────────────────────────────────────────────────────────────────────────────
df = pd.read_csv(IN_CSV, dtype=str)

# ───────────────────────────────────────────────────────────────────────────────
# Clean
# ───────────────────────────────────────────────────────────────────────────────
# 1) Drop the old, empty LOCODE column
if "LOCODE" in df.columns:
    df.drop(columns=["LOCODE"], inplace=True)

# 2) Rename 'code' → 'LOCODE'
df.rename(columns={"code": "LOCODE"}, inplace=True)

# 3) Reorder so LOCODE is the very first column
cols = df.columns.tolist()
cols.insert(0, cols.pop(cols.index("LOCODE")))
df = df[cols]

# ───────────────────────────────────────────────────────────────────────────────
# Save
# ───────────────────────────────────────────────────────────────────────────────
df.to_csv(OUT_CSV, index=False)
print(f"✅ Cleaned LOCODE in place → {OUT_CSV}")
