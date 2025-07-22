import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import math
import pytest
import lane_distance


# --- Test great_circle distance ---
def test_great_circle_zero():
    # Distance between identical points should be zero
    assert lane_distance.great_circle(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0)

def test_great_circle_equator_1deg():
    # At equator, 1° of longitude is ~ (2πR/360) miles
    R = 3958.8
    expected = 2 * math.pi * R / 360.0
    result = lane_distance.great_circle(0.0, 0.0, 0.0, 1.0)
    assert result == pytest.approx(expected, rel=1e-6)

# --- Test try_unlocode lookup ---
@pytest.fixture(autouse=True)
def dummy_unloc_lookup(monkeypatch):
    # Monkey-patch the internal lookup table for tests
    monkeypatch.setattr(lane_distance, '_unloc_lookup', {
        'TEST1': (12.34, 56.78),
        'AB123': (9.87, 65.43),
    })

def test_try_unlocode_found():
    # Valid code present in lookup
    res = lane_distance.try_unlocode('TEST1')
    assert res == (12.34, 56.78, False)

def test_try_unlocode_not_found():
    # Non-existent code returns None
    assert lane_distance.try_unlocode('XXXX1') is None

# --- Test resolve_place behavior ---

def test_resolve_place_with_code(monkeypatch):
    # Code hits UNLOCODE path
    monkeypatch.setattr(lane_distance, 'get_candidates', lambda name: (_ for _ in ()).__next__())
    lat, lon, amb, used = lane_distance.resolve_place('Irrelevant', 'AB123')
    assert (lat, lon) == (9.87, 65.43)
    assert amb is False
    assert used is True

def test_resolve_place_name_as_code(monkeypatch):
    # Name field matches LOCODE
    monkeypatch.setattr(lane_distance, 'get_candidates', lambda name: (_ for _ in ()).__next__())
    lat, lon, amb, used = lane_distance.resolve_place('TEST1', None)
    assert (lat, lon) == (12.34, 56.78)
    assert amb is False
    assert used is True

def test_resolve_place_mapbox_single(monkeypatch):
    # Fallback to Mapbox: single candidate
    dummy_feat = {'geometry': {'coordinates': [77.0, 11.0]}}
    monkeypatch.setattr(lane_distance, 'get_candidates', lambda name: [dummy_feat])
    lat, lon, amb, used = lane_distance.resolve_place('City, CT', None)
    assert (lat, lon) == (11.0, 77.0)
    assert amb is False
    assert used is False

def test_resolve_place_mapbox_ambiguous(monkeypatch):
    # Fallback to Mapbox: multiple candidates -> ambiguous
    dummy_feats = [
        {'geometry': {'coordinates': [10.0, 20.0]}},
        {'geometry': {'coordinates': [10.0, 20.0]}}
    ]
    monkeypatch.setattr(lane_distance, 'get_candidates', lambda name: dummy_feats)
    lat, lon, amb, used = lane_distance.resolve_place('AmbiguousCity', None)
    assert (lat, lon) == (20.0, 10.0)
    assert amb is True
    assert used is False
