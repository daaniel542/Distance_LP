# tests/test_lookup_order.py
import pytest
import lane_distance as ld

def test_unlocode_precedence_over_mapbox(monkeypatch):
    called = []

    # 1) Make try_unlocode succeed for code “GOOD”
    monkeypatch.setattr(
        ld,
        "try_unlocode",
        lambda c: (1.23, 4.56, False) if c == "GOOD" else None
    )

    # 2) Stub out Mapbox so that if we ever fall back, we record it
    monkeypatch.setattr(
        ld,
        "get_candidates",
        lambda name, **kw: (_ for _ in ()).throw(Exception("Mapbox called"))
    )

    # 3) Now call resolve_place with a name *and* code of “GOOD”
    lat, lon, ambiguous, used = ld.resolve_place("Anything", "GOOD")

    # 4) Assert we got back our UN/LOCODE coords…
    assert (lat, lon) == (1.23, 4.56)
    # …and that we marked used_unlocode=True
    assert used is True

    # If Mapbox were called, resolve_place would have thrown above.

