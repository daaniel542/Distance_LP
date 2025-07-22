# clean_unlocode.py

import re
import pandas as pd
from pathlib import Path

SRC = Path("unlocode_2024-2.csv")
OUT = Path("unlocode_clean.csv")

# 1) Load the raw combined CSV (Latin-1 to handle accents)
df = pd.read_csv(SRC, dtype=str, encoding="latin-1", skip_blank_lines=True)

# 2) Detect the country code column (case-insensitive match on 'country')
country_col = next(c for c in df.columns if re.search(r"country", c, re.I))

# 3) Detect the location code column (e.g., 'LOCODE', 'Code', etc.), but not the coordinates
code_col = next(
    c for c in df.columns
    if re.search(r"locod?e|code", c, re.I) and c.lower() != country_col.lower()
)

# 4) Detect the DMS coordinate column (values like '4230N 00131E')
pattern = r"^\s*\d{2,3}\d{2}[NSWE]\s+\d{2,3}\d{2}[NSWE]\s*$"
coord_col = next(
    c for c in df.columns
    if df[c].astype(str).str.match(pattern, na=False).any()
)

# 5) Split DMS into two parts
series = df[coord_col].fillna("").astype(str)
parts = series.str.strip().str.split(r"\s+", expand=True)
parts.columns = ["lat_dms", "lon_dms"]

# 6) Helper: convert DMS string (e.g. '4230N') → decimal degrees
def dms_to_decimal(dms: str) -> float:
    if not isinstance(dms, str) or not dms.strip():
        return float('nan')
    m = re.match(r"^(?P<deg>\d{2,3})(?P<min>\d{2})(?P<dir>[NSEW])$", dms.strip())
    if not m:
        return float('nan')
    deg = int(m.group('deg'))
    minute = int(m.group('min')) / 60.0
    dec = deg + minute
    if m.group('dir') in ('S', 'W'):
        dec = -dec
    return dec

# 7) Build the full UN/LOCODE by concatenating country + locode part
df['LOCODE'] = (
    df[country_col].fillna('').str.strip().str.upper() +
    df[code_col].fillna('').str.strip().str.upper()
)

# 8) Convert DMS to decimal lat/lon
df['Latitude']  = parts['lat_dms'].apply(dms_to_decimal)
df['Longitude'] = parts['lon_dms'].apply(dms_to_decimal)

# 9) Keep only the combined LOCODE and decimal coords
clean = df[['LOCODE', 'Latitude', 'Longitude']].copy()
clean.to_csv(OUT, index=False)
print(f"✅ Wrote {len(clean)} entries to {OUT}")