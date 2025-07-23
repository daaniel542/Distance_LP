#!/usr/bin/env python3
"""
dedupe_master_updated.py

Remove any duplicate rows in data/unlocode_master_updated.csv
based on the LOCODE column, keeping only the first instance.
"""

import pandas as pd
from pathlib import Path

# ───────────────────────────────────────────────────────────────────────────────
# Adjust this path if your file lives elsewhere
# ───────────────────────────────────────────────────────────────────────────────
IN_CSV  = Path("data/unlocode_master_updated.csv")
OUT_CSV = IN_CSV   # overwrite in place; change if you want a separate file

# ───────────────────────────────────────────────────────────────────────────────
# LOAD
# ───────────────────────────────────────────────────────────────────────────────
df = pd.read_csv(IN_CSV, dtype=str)

# ───────────────────────────────────────────────────────────────────────────────
# DEDUPE
# ───────────────────────────────────────────────────────────────────────────────
total_before = len(df)
df = df.drop_duplicates(subset=["LOCODE"], keep="first")
total_after  = len(df)

print(f"Dropped {total_before - total_after} duplicate rows; {total_after} remain.")

# ───────────────────────────────────────────────────────────────────────────────
# SAVE
# ───────────────────────────────────────────────────────────────────────────────
df.to_csv(OUT_CSV, index=False)
print(f"✅ Wrote deduped file → {OUT_CSV}")
