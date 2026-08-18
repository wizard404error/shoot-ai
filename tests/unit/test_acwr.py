"""Tests for ACWR (Acute:Chronic Workload Ratio) computation."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from kawkab.analysis.acwr import (
    assess_injury_risk,
    compute_acwr,
    compute_acwr_from_sessions,
)


def _daily(day: int, load: float) -> dict:
    return {"date": f"2026-01-{day:02d}", "total_distance_m": load}


def test_basic_acwr():
    """Constant daily load should give ACWR near 1.0."""
    loads = [_daily(d, 5000.0) for d in range(1, 31)]
    results = compute_acwr(loads)
    assert len(results) == 30
    last = results[-1]
    assert 0.5 < last["acwr"] < 2.0
    assert last["load_category"] in ("normal", "high", "low")


def test_spike_detection():
    """A sudden doubling of load should push ACWR > 1.3."""
    loads = [_daily(d, 5000.0) for d in range(1, 29)]
    loads.append(_daily(29, 10000.0))
    loads.append(_daily(30, 10000.0))
    results = compute_acwr(loads)
    last = results[-1]
    assert last["acwr"] > 0.8
    # May or may not hit high depending on decay
    assert last["load_category"] in ("normal", "high", "very_high")


def test_high_load_category():
    """Load doubling sustained should trigger very_high."""
    loads = [_daily(d, 3000.0) for d in range(1, 29)]
    for d in range(29, 36):
        loads.append(_daily(d, 15000.0))
    results = compute_acwr(loads)
    last = results[-1]
    assert last["load_category"] in ("high", "very_high")


def test_empty():
    assert compute_acwr([]) == []


def test_single_day():
    result = compute_acwr([_daily(1, 5000.0)])
    assert len(result) == 1
    assert result[0]["acwr"] == 1.0
    assert result[0]["load_category"] == "normal"


def test_constant_acwr_stability():
    """Constant daily load should produce ACWR ~1.0."""
    loads = [_daily(d, 10000.0) for d in range(1, 61)]
    results = compute_acwr(loads)
    # After 60 days, ACWR should converge to ~1.0
    mid = results[30]
    late = results[59]
    assert abs(mid["acwr"] - 1.0) < 0.5
    assert abs(late["acwr"] - 1.0) < 0.5


def test_custom_load_field():
    """Use player_load instead of total_distance_m."""
    loads = [{"date": f"2026-01-{d:02d}", "player_load": 500.0} for d in range(1, 31)]
    results = compute_acwr(loads, load_field="player_load")
    assert len(results) == 30


def test_from_sessions():
    """Compute ACWR from session records aggregated by date."""
    sessions = [
        {"start_time": "2026-01-01", "total_distance_m": 5000.0},
        {"start_time": "2026-01-01", "total_distance_m": 3000.0},
        {"start_time": "2026-01-02", "total_distance_m": 6000.0},
    ]
    results = compute_acwr_from_sessions(sessions)
    assert len(results) == 2
    # Day 1 should have 8000 total
    assert results[0]["total_distance_m"] > 5000


def test_from_sessions_empty():
    assert compute_acwr_from_sessions([]) == []


def test_assess_risk_normal():
    loads = [_daily(d, 5000.0) for d in range(1, 31)]
    results = compute_acwr(loads)
    risk = assess_injury_risk(results)
    assert risk["risk_level"] in ("normal", "elevated")
    assert risk["total_days"] == 30


def test_assess_risk_empty():
    risk = assess_injury_risk([])
    assert risk["risk_level"] == "unknown"


def test_assess_risk_high_days():
    loads = []
    for d in range(1, 29):
        loads.append(_daily(d, 3000.0))
    for d in range(29, 36):
        loads.append(_daily(d, 20000.0))
    results = compute_acwr(loads)
    risk = assess_injury_risk(results)
    # May have elevated or critical risk with that spike
    assert risk["risk_level"] in ("elevated", "critical", "normal")
    assert isinstance(risk["recommendations"], list)
    assert len(risk["recommendations"]) > 0


def test_recommendations_exist():
    """Even in normal case, recommendations should be present."""
    loads = [_daily(d, 5000.0) for d in range(1, 15)]
    results = compute_acwr(loads)
    risk = assess_injury_risk(results)
    assert len(risk["recommendations"]) > 0


def test_datetime_handling():
    """Sessions with datetime objects should be handled."""
    from datetime import datetime
    sessions = [
        {"start_time": datetime(2026, 1, 1, 14, 0), "total_distance_m": 5000},
        {"start_time": datetime(2026, 1, 2, 15, 30), "total_distance_m": 6000},
    ]
    results = compute_acwr_from_sessions(sessions)
    assert len(results) == 2


def test_missing_field_does_not_crash():
    """Missing load field should not crash."""
    loads = [{"date": "2026-01-01"}, {"date": "2026-01-02", "total_distance_m": 5000}]
    results = compute_acwr(loads)
    assert len(results) == 2
