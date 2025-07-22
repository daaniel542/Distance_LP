#!/usr/bin/env python3
import re
import csv
from pathlib import Path

LOG     = Path("mapbox_fills.log")
OUTPUT  = Path("mapbox_filled_coords.csv")

pattern = re.compile(r"^✓\s+([A-Z0-9]+):\s+(-?\d+\.\d+),\s*(-?\d+\.\d+)$")

rows = []
with LOG.open() as fh:
    for line in fh:
        m = pattern.match(line.strip())
        if m:
            code, lat, lon = m.groups()
            rows.append((code, lat, lon, "MAPBOX"))

# write out CSV (no header if you prefer)
with OUTPUT.open("w", newline="") as out:
    writer = csv.writer(out)
    writer.writerow(["code","Latitude","Longitude","src"])
    writer.writerows(rows)

print(f"Wrote {len(rows)} filled entries to {OUTPUT}")
