# generate_master.py

import pandas as pd
from lane_distance import _merged

def main():
    """Dump the merged UN/LOCODE + WKT lookup to a single master CSV."""
    master = _merged.copy()
    master.to_csv("unlocode_master.csv", index=False)
    print(f"✅ wrote unlocode_master.csv with {len(master)} rows")

if __name__ == "__main__":
    main()
