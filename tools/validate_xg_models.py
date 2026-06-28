"""Validate all xG models against StatsBomb ground-truth xG data.

Usage:
    python tools/validate_xg_models.py <match_id>

Fetches shot events from StatsBomb Open Data, runs each xG model
(legacy, enhanced, DL), and reports RMSE, MAE, bias vs StatsBomb xG.

Example:
    python tools/validate_xg_models.py 3869151
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kawkab.services.statsbomb_service import StatsBombService
from kawkab.core.xg_model import compute_xg, compute_xg_enhanced
from kawkab.core.dl_xg_model import predict_dl_xg
from kawkab.core.game_constants import GAME


PITCH_LENGTH = GAME.PITCH_LENGTH_M
PITCH_WIDTH = GAME.PITCH_WIDTH_M
GOAL_CENTER_X = PITCH_LENGTH
GOAL_CENTER_Y = PITCH_WIDTH / 2.0
GOAL_WIDTH = 7.32
GOAL_HEIGHT = 2.44


def _get_distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def _get_angle(x, y, goal_center_x, goal_center_y, goal_width):
    dx = goal_center_x - x
    dy = goal_center_y - y
    distance = math.sqrt(dx * dx + dy * dy)
    if distance < 1.0:
        return 90.0
    angle_to_center = abs(math.degrees(math.atan2(dy, dx)))
    half_goal = math.degrees(math.atan2(goal_width / 2, distance))
    return min(angle_to_center + half_goal, 90.0)


def _body_part_to_str(bp_dict):
    if isinstance(bp_dict, dict):
        return bp_dict.get("name", "").lower()
    return str(bp_dict).lower() if bp_dict else "right_foot"


def _shot_type_to_str(type_dict):
    if isinstance(type_dict, dict):
        return type_dict.get("name", "").lower()
    return str(type_dict).lower() if type_dict else "open_play"


def _map_body_part(sb_part):
    m = {"head": "head", "left foot": "left_foot", "right foot": "right_foot", "other": "right_foot"}
    return m.get(sb_part, "right_foot")


def _map_shot_type(sb_type):
    m = {"open play": "open_play", "volley": "volley", "half volley": "half_volley",
         "free kick": "free_kick", "penalty": "penalty", "corner": "open_play",
         "set piece": "free_kick", "direct free kick": "free_kick"}
    return m.get(sb_type, "open_play")


async def validate(match_id: int) -> None:
    svc = StatsBombService()
    raw = await svc.get_raw_events(match_id)
    if not raw:
        print(f"No data for match {match_id}")
        return

    shot_count = 0
    legacy_errors = []
    enhanced_errors = []
    dl_errors = []

    for event in raw:
        type_info = event.get("type", {})
        if isinstance(type_info, dict):
            type_name = type_info.get("name", "")
        else:
            type_name = str(type_info)

        if type_name != "Shot":
            continue

        shot_info = event.get("shot", {}) or {}
        sb_xg = shot_info.get("statsbomb_xg")
        if sb_xg is None:
            continue
        sb_xg = float(sb_xg)

        location = event.get("location") or []
        if len(location) < 2:
            continue
        x = float(location[0])
        y = float(location[1])

        distance_m = _get_distance(x, y, GOAL_CENTER_X, GOAL_CENTER_Y)
        angle_deg = _get_angle(x, y, GOAL_CENTER_X, GOAL_CENTER_Y, GOAL_WIDTH)
        body_part = _map_body_part(_body_part_to_str(shot_info.get("body_part")))
        shot_type = _map_shot_type(_shot_type_to_str(shot_info.get("type")))

        try:
            legacy_xg = compute_xg(distance_m=distance_m, angle_deg=angle_deg,
                                   body_part=body_part, shot_type=shot_type)
            legacy_errors.append(legacy_xg - sb_xg)

            enhanced_xg = compute_xg_enhanced(distance_m=distance_m, angle_deg=angle_deg,
                                              is_header=(body_part == "head"),
                                              shot_type=shot_type)
            enhanced_errors.append(enhanced_xg - sb_xg)

            dl_xg = predict_dl_xg(distance_m=distance_m, angle_deg=angle_deg,
                                  is_header=(body_part == "head"),
                                  shot_type=shot_type)
            dl_errors.append(dl_xg - sb_xg)

            shot_count += 1
        except Exception as e:
            print(f"  Skipping shot at ({x:.1f}, {y:.1f}): {e}")

    print(f"\n=== xG Model Validation — Match {match_id} ===")
    print(f"Shots evaluated: {shot_count}")
    print()

    models = [
        ("Legacy (logistic)", legacy_errors),
        ("Enhanced (xgboost-style)", enhanced_errors),
        ("DL (neural network)", dl_errors),
    ]
    for name, errors in models:
        if not errors:
            print(f"  {name}: no data")
            continue
        n = len(errors)
        mae = sum(abs(e) for e in errors) / n
        rmse = math.sqrt(sum(e * e for e in errors) / n)
        bias = sum(errors) / n
        print(f"  {name}:")
        print(f"    MAE : {mae:.4f}")
        print(f"    RMSE: {rmse:.4f}")
        print(f"    Bias: {bias:.4f}")

    await svc.close()


if __name__ == "__main__":
    import asyncio

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    match_id = int(sys.argv[1])
    asyncio.run(validate(match_id))
