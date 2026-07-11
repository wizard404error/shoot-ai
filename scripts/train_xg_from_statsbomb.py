"""Train xG model coefficients on StatsBomb open data.

Loads StatsBomb match files from tests/data/ground_truth/statsbomb/events/,
extracts shot events, trains logistic regression coefficients via batch gradient
descent, and saves to src/kawkab/core/trained_xg_coefficients.json.
The xG model loader auto-discovers this file at import time.
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from kawkab.core.xg_trainer import (
    FEATURE_NAMES,
    FitShot,
    batch_gradient_descent,
    fit_from_shots,
)

EVENT_DIR = (
    Path(__file__).resolve().parent.parent
    / "tests" / "data" / "ground_truth" / "statsbomb" / "events"
)
OUTPUT_PATH = SRC_DIR / "kawkab" / "core" / "trained_xg_coefficients.json"
STATSBOMB_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/events"
SB_MATCH_IDS = [15946, 18245, 18252, 19975, 20378, 3753, 69301, 7189, 20388, 20464]
_MAX_RETRIES = 5

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
GOAL_CENTER_X = PITCH_LENGTH
GOAL_CENTER_Y = PITCH_WIDTH / 2.0
GOAL_WIDTH = 7.32

MODEL_NAMES = {
    'heuristic': 'Heuristic (legacy, hand-set)',
    'enhanced': 'Enhanced (hand-set, StatsBomb-calibrated)',
    'trained': 'Trained on StatsBomb data (this script)',
}


def _get_distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def _get_angle(x, y):
    dx = GOAL_CENTER_X - x
    dy = GOAL_CENTER_Y - y
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 1.0:
        return 90.0
    half_goal = math.degrees(math.atan2(GOAL_WIDTH / 2, dist))
    angle_to_center = abs(math.degrees(math.atan2(dy, dx)))
    return min(angle_to_center + half_goal, 90.0)


def _map_body_part(sb_part):
    m = {"Head": "head", "Left Foot": "left_foot", "Right Foot": "right_foot", "Other": "right_foot"}
    return m.get(sb_part, "right_foot")


def _map_shot_type(sb_type):
    m = {"Open Play": "open_play", "Volley": "volley", "Half Volley": "half_volley",
         "Free Kick": "free_kick", "Penalty": "penalty", "Corner": "open_play",
         "Set Piece": "free_kick", "Direct Free Kick": "free_kick"}
    return m.get(sb_type, "open_play")


def _fetch_missing_data() -> None:
    """Auto-download StatsBomb match files not present locally with retry on 429."""
    EVENT_DIR.mkdir(parents=True, exist_ok=True)
    missing = [mid for mid in SB_MATCH_IDS if not (EVENT_DIR / f"{mid}.json").exists()]
    if not missing:
        return
    try:
        import httpx
    except ImportError:
        print("  httpx not available, skipping auto-fetch")
        return
    client = httpx.Client(timeout=30.0, follow_redirects=True)
    for mid in missing:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = client.get(f"{STATSBOMB_BASE}/{mid}.json")
                if resp.status_code == 429:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    print(f"  429 on match {mid}, retrying in {wait:.1f}s (attempt {attempt}/{_MAX_RETRIES})")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                (EVENT_DIR / f"{mid}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
                print(f"  Fetched match {mid} ({len(data)} events)")
                break
            except Exception as exc:
                if attempt == _MAX_RETRIES:
                    print(f"  Failed to fetch match {mid} after {_MAX_RETRIES} attempts: {exc}")
                else:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    print(f"  Error on match {mid}, retrying in {wait:.1f}s: {exc}")
                    time.sleep(wait)
    client.close()


def load_all_shots():
    shots = []
    for fpath in sorted(EVENT_DIR.glob("*.json")):
        match_id = int(fpath.stem)
        if match_id not in SB_MATCH_IDS:
            continue
        try:
            events = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  Skip {fpath.name}: {e}")
            continue
        for ev in events:
            type_info = ev.get("type", {}) or {}
            if type_info.get("name") != "Shot":
                continue
            shot_info = ev.get("shot", {}) or {}
            sb_xg = shot_info.get("statsbomb_xg")
            if sb_xg is None:
                continue
            loc = ev.get("location") or []
            if len(loc) < 2:
                continue
            x, y = float(loc[0]), float(loc[1])
            body_part = _map_body_part((shot_info.get("body_part") or {}).get("name", ""))
            shot_type = _map_shot_type((shot_info.get("type") or {}).get("name", ""))
            is_goal = (shot_info.get("outcome") or {}).get("name") == "Goal"
            under_pressure = ev.get("under_pressure", False)
            freeze_frame = shot_info.get("freeze_frame", [])
            n_opponents = sum(1 for p in freeze_frame if not p.get("teammate", True)) if freeze_frame else 0
            gk_dist = 0.0
            if freeze_frame:
                for p in freeze_frame:
                    if not p.get("teammate", True) and p.get("position", {}).get("name") == "Goalkeeper":
                        ploc = p.get("location", [])
                        if len(ploc) >= 2:
                            gk_dist = _get_distance(x, y, float(ploc[0]), float(ploc[1]))
            is_rebound = False
            is_big_chance = False
            assist_type = "standard"
            if ev.get("pass"):
                pass_type = (ev.get("pass", {}).get("height", {}) or {}).get("name", "")
                if pass_type == "Through Ball":
                    assist_type = "through_ball"
                elif pass_type in ("Cross", "Corner"):
                    assist_type = "cross"

            shots.append(FitShot(
                distance_m=_get_distance(x, y, GOAL_CENTER_X, GOAL_CENTER_Y),
                angle_deg=_get_angle(x, y),
                is_header=(body_part == "head"),
                is_through_ball_assist=(assist_type == "through_ball"),
                is_cross_assist=(assist_type == "cross"),
                is_one_on_one=(n_opponents <= 1 and _get_distance(x, y, GOAL_CENTER_X, GOAL_CENTER_Y) < 20),
                is_pressed=under_pressure,
                is_volley=(shot_type in ("volley", "half_volley")),
                is_free_kick=(shot_type == "free_kick"),
                gk_distance_m=gk_dist,
                is_rebound=is_rebound,
                is_big_chance=is_big_chance,
                is_goal=is_goal,
            ))
    return shots


def main():
    print("=== xG Coefficient Trainer ===")
    print()

    _fetch_missing_data()

    if not EVENT_DIR.is_dir() or not list(EVENT_DIR.glob("*.json")):
        print(f"No StatsBomb data found in {EVENT_DIR}")
        sys.exit(1)

    shots = load_all_shots()
    print(f"Loaded {len(shots)} shots from StatsBomb data")

    goals = sum(1 for s in shots if s.is_goal)
    print(f"Goals: {goals} ({goals/max(len(shots),1)*100:.1f}%)")
    print()

    if len(shots) < 50:
        print(f"Too few shots ({len(shots)}), need >= 50. Training with fallback.")
        sys.exit(1)

    train_coeffs = fit_from_shots(shots, model_name="trained")
    # Only save non-zero coefficients so the default enhanced fallback
    # is preserved for features with insufficient training data.
    nonzero = {k: v for k, v in train_coeffs.items() if v != 0.0 or k.startswith("_")}
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(nonzero, f, indent=2)
    print(f"Trained coefficients saved to {OUTPUT_PATH}")
    print()

    print("Trained coefficients:")
    for name, val in train_coeffs.items():
        if name.startswith("_"):
            continue
        print(f"  {name:25s} = {val:+.6f}")
    print()
    print("Metadata:")
    print(f"  n_shots  = {train_coeffs.get('_n_shots', '?')}")
    print(f"  goal_rate = {train_coeffs.get('_goal_rate', '?'):.4f}")
    print(f"  model     = {train_coeffs.get('_model_name', '?')}")


if __name__ == "__main__":
    main()
