import sqlite3
import pytest
import pandas as pd
from geopy.distance import geodesic

import lane_distance as ld

# Dummy geopy Location stub
class DummyLocation:
    def __init__(self, lat, lon):
        self.latitude = lat
        self.longitude = lon

# 1. clean_place
def test_clean_place_variations():
    assert ld.clean_place("  New   York, US.. ") == "NEW YORK, US"
    assert ld.clean_place("paris.fr;") == "PARIS.FR"
    assert ld.clean_place("") is None
    assert ld.clean_place(None) is None

# 2. distance_miles
def test_distance_miles_computation():
    a = (40.0, -75.0)
    b = (41.0, -74.0)
    expected = geodesic(a, b).miles
    assert pytest.approx(ld.distance_miles(a, b), rel=1e-6) == expected

def test_distance_miles_nan():
    nan = ld.distance_miles(None, (0,0))
    assert nan != nan  # NaN

# 3. open_cache error handling
def test_open_cache_bad_path(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("simulated"))
    )
    with pytest.raises(SystemExit) as exc:
        ld.open_cache("/nonexistent/path/cache.db")
    assert "Cannot open cache DB" in str(exc.value)

# 4. geocode_place caching logic + failures
def test_geocode_place_cache_and_miss(tmp_path):
    calls = []
    def stub(p):
        calls.append(p)
        return DummyLocation(1.0, 2.0)

    conn = ld.open_cache(tmp_path / "c1.db")
    # first call → stub
    assert ld.geocode_place("X", stub, conn) == (1.0, 2.0)
    # second call → cache, no extra stub calls
    assert ld.geocode_place("X", stub, conn) == (1.0, 2.0)
    assert calls == ["X"]

    # test stub returning None
    def miss(p): return None
    assert ld.geocode_place("Y", miss, conn) is None

# 5. calculate_distances end-to-end stub
def test_calculate_distances_monopoint():
    def stub(p): return DummyLocation(0,0)
    conn = sqlite3.connect(":memory:")
    origins = ["A","B","A"]
    destinations = ["C","A","C"]
    d = ld.calculate_distances(origins, destinations, stub, conn)
    assert all(x == pytest.approx(0.0) for x in d)

# 6. process_file CSV → CSV, with stub
def test_process_file_csv(tmp_path, monkeypatch):
    df_in = pd.DataFrame({
        "Origin": ["foo", "bad",   None],
        "Destination": ["bar", None, "baz"]
    })
    in_fp  = tmp_path / "in.csv"
    out_fp = tmp_path / "out.csv"
    df_in.to_csv(in_fp, index=False)

    # stub geocode: foo→(1,1), bar→(1,2)
    def stub(p):
        if p=="FOO": return DummyLocation(1,1)
        if p=="BAR": return DummyLocation(1,2)
        return None

    # monkey-patch RateLimiter & Nominatim & cache
    monkeypatch.setattr(ld, "open_cache", lambda db_path=None: sqlite3.connect(":memory:"))
    monkeypatch.setattr(ld, "Nominatim", lambda *args, **kwargs: None)
    monkeypatch.setattr(ld, "RateLimiter", lambda f, **kwargs: stub)

    df_out = ld.process_file(in_fp, out_fp)
    # Only the valid row remains, and distance is ~69 miles
    assert len(df_out) == 1
    assert df_out.iloc[0]["origin"] == "FOO"
    assert df_out.iloc[0]["destination"] == "BAR"
    assert pytest.approx(
        df_out.iloc[0]["lane_distance_mi"],
        rel=1e-2
    ) == geodesic((1,1),(1,2)).miles

    # output file exists
    df_chk = pd.read_csv(out_fp)
    assert "lane_distance_mi" in df_chk.columns

# 7. process_file Excel → Excel
def test_process_file_excel(tmp_path, monkeypatch):
    df_in = pd.DataFrame({"origin": ["X"], "destination": ["Y"]})
    in_fp  = tmp_path / "in.xlsx"
    out_fp = tmp_path / "out.xlsx"
    df_in.to_excel(in_fp, index=False)

    def stub(p): return DummyLocation(0,0)
    monkeypatch.setattr(ld, "open_cache", lambda db_path=None: sqlite3.connect(":memory:"))
    monkeypatch.setattr(ld, "Nominatim", lambda *args, **kwargs: None)
    monkeypatch.setattr(ld, "RateLimiter", lambda f, **kwargs: stub)

    df_out = ld.process_file(in_fp, out_fp)
    assert out_fp.exists()
    assert df_out.loc[0, "lane_distance_mi"] == 0.0
