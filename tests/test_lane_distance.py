import pytest
from lane_distance import extract_lon_lat, try_unlocode, resolve_place, _unloc_lookup

def test_extract_lon_lat_valid():
    lon, lat = extract_lon_lat("POINT (4.5 51.9)")
    assert lat == pytest.approx(51.9)
    assert lon == pytest.approx(4.5)

def test_extract_lon_lat_invalid():
    lon, lat = extract_lon_lat("LINESTRING (0 0,1 1)")
    assert lon is None and lat is None

def test_try_unlocode_present():
    # grab any existing LOCODE entry
    code, (lat, lon, src) = next((_k,_v) for _k,_v in _unloc_lookup.items())
    res = try_unlocode(code)
    assert res == (lat, lon, src)

def test_resolve_place_unlocode():
    code, (lat_exp, lon_exp, src_exp) = next((_k,_v) for _k,_v in _unloc_lookup.items())
    lat, lon, amb, used, src = resolve_place(None, code)
    assert not amb and used
    assert (lat, lon, src) == (lat_exp, lon_exp, src_exp)

def test_resolve_place_mapbox(monkeypatch):
    import lane_distance as ld
    # stub get_candidates to return a single result
    monkeypatch.setattr(ld, 'get_candidates', lambda name: [{"geometry":{"coordinates":[10,20]}}])
    lat, lon, amb, used, src = resolve_place("X", None)
    assert (lat, lon) == (20, 10)
    assert not amb and not used and src == "MAPBOX"
