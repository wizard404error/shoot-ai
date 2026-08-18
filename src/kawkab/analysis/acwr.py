"""Acute:Chronic Workload Ratio (ACWR) computation.

ACWR measures whether a player's current training load (acute, 7-day
rolling) relative to their chronic baseline (28-day rolling) is in a
safe zone. Based on Gabbett (2016): "The training-injury prevention
paradox: should athletes be training smarter and harder?"

Ranges (Gabbett 2016):
  - < 0.8:   Low / Under-training (may be deconditioned)
  - 0.8-1.3: Sweet spot (safe)
  - 1.3-1.5: High (increased risk)
  - > 1.5:   Very high (danger zone)

The acute load is the exponentially-weighted moving average of daily
loads over the last 7 days. Chronic load is over the last 28 days.

Player load metric options:
  - total_distance_m (most common)
  - player_load (accelerometer-derived, Catapult PL units)
  - high_intensity_distance_m (sprint / HI running)
  - sRPE (session Rating of Perceived Exertion) — requires manual input
  - custom_weighted (combination)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

logger = logging.getLogger("acwr")


def compute_acwr(
    daily_loads: list[dict[str, Any]],
    load_field: str = "total_distance_m",
) -> list[dict[str, Any]]:
    """Compute ACWR for a player over a timeline of daily loads.

    Args:
        daily_loads: List of dicts with 'date' (str/date) and load_field (float).
                     Must be sorted by date ascending.
        load_field: Which field to use for load.
        decay_factor: Exponential decay weight per day (0.1 = 10% weight/day).

    Returns:
        List with same length as input, each dict augmented with:
          acute_load, chronic_load, acwr, load_category
    """
    if not daily_loads:
        return []

    results = []
    acute_window = 7
    chronic_window = 28

    for i, entry in enumerate(daily_loads):
        load = entry.get(load_field, 0) or 0

        # Acute load: rolling 7-day simple average
        start = max(0, i - acute_window + 1)
        acute_vals = [daily_loads[j].get(load_field, 0) or 0 for j in range(start, i + 1)]
        acute = sum(acute_vals) / len(acute_vals) if acute_vals else load

        # Chronic load: rolling 28-day simple average
        start = max(0, i - chronic_window + 1)
        chronic_vals = [daily_loads[j].get(load_field, 0) or 0 for j in range(start, i + 1)]
        chronic = sum(chronic_vals) / len(chronic_vals) if chronic_vals else load

        ratio = acute / max(chronic, 0.001)

        if ratio > 1.5:
            category = "very_high"
        elif ratio > 1.3:
            category = "high"
        elif ratio < 0.8:
            category = "low"
        else:
            category = "normal"

        results.append({
            **entry,
            "acute_load": round(acute, 1),
            "chronic_load": round(chronic, 1),
            "acwr": round(ratio, 3),
            "load_category": category,
        })

    return results


def compute_acwr_from_sessions(
    sessions: list[dict[str, Any]],
    load_field: str = "total_distance_m",
    date_field: str = "start_time",
) -> list[dict[str, Any]]:
    """Compute ACWR from GPS session records, aggregating load by date.

    Args:
        sessions: List of GPS session dicts with date_field and load_field.
        load_field: 'total_distance_m', 'player_load', 'hi_distance_m', etc.
        date_field: Field name for the date.

    Returns:
        List of daily ACWR results (one per day with data).
    """
    if not sessions:
        return []

    daily: dict[str, float] = defaultdict(float)
    for s in sessions:
        raw_date = s.get(date_field, "")
        if isinstance(raw_date, datetime):
            date_key = raw_date.strftime("%Y-%m-%d")
        elif isinstance(raw_date, str):
            date_key = raw_date[:10]
        else:
            continue
        load = s.get(load_field, 0) or 0
        daily[date_key] += load

    daily_loads = [
        {"date": date, load_field: load}
        for date, load in sorted(daily.items())
    ]

    return compute_acwr(daily_loads, load_field=load_field)


def assess_injury_risk(acwr_data: list[dict[str, Any]]) -> dict[str, Any]:
    """Assess overall injury risk from ACWR trend data.

    Returns dict with risk level, dangerous days, and recommendations.
    """
    if not acwr_data:
        return {"risk_level": "unknown", "danger_days": 0, "recommendations": []}

    total = len(acwr_data)
    high_days = sum(1 for d in acwr_data if d.get("load_category") in ("high", "very_high"))
    low_days = sum(1 for d in acwr_data if d.get("load_category") == "low")
    sweet_days = total - high_days - low_days

    high_ratio = high_days / max(total, 1)
    latest = acwr_data[-1] if acwr_data else {}

    if latest.get("load_category") in ("high", "very_high"):
        if high_ratio > 0.3:
            risk = "critical"
        else:
            risk = "elevated"
    elif low_days > total * 0.5:
        risk = "deconditioned"
    else:
        risk = "normal"

    recommendations = []
    if risk == "critical":
        recommendations.extend([
            "Reduce training load by 30-50% for 3-5 days",
            "Consider rest day or active recovery",
            "Monitor for early injury signs",
        ])
    elif risk == "elevated":
        recommendations.extend([
            "Maintain current load but avoid spikes",
            "Monitor player-reported fatigue",
        ])
    elif risk == "deconditioned":
        recommendations.extend([
            "Gradually increase load by 10% per week",
            "Focus on building base fitness",
        ])
    else:
        recommendations.append("Continue current training load")

    return {
        "risk_level": risk,
        "total_days": total,
        "sweet_spot_days": sweet_days,
        "high_days": high_days,
        "low_days": low_days,
        "high_ratio": round(high_ratio, 2),
        "latest_acwr": latest.get("acwr"),
        "latest_category": latest.get("load_category"),
        "recommendations": recommendations,
    }
