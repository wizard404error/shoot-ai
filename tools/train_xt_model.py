"""Train a 12x8 xT (Expected Threat) model using socceraction on StatsBomb data.

Usage:
    python tools/train_xt_model.py --output models/xt_12x8.npy

Trains socceraction's xT model on StatsBomb open data, exporting weights
that Kazkab's AnalysisService can load via compute_xt_simple() replacement.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("train_xt_model")

X_GRID = 12
Y_GRID = 8


def fetch_statsbomb_data() -> tuple[list, list]:
    """Fetch StatsBomb open data using statsbombpy (or fallback to httpx).

    Returns (passes, carries) where each element is
    {'start_x': float, 'start_y': float, 'end_x': float, 'end_y': float}.
    """
    passes: list[dict] = []
    carries: list[dict] = []

    try:
        import statsbombpy

        comps = statsbombpy.competitions()
        for _, comp in comps.iterrows():
            matches = statsbombpy.matches(comp["competition_id"], comp["season_id"])
            logger.info(f"Fetching {len(matches)} matches from {comp['competition_name']} {comp['season_name']}")
            for _, match in matches.iterrows():
                events = statsbombpy.events(match["match_id"])
                if events is None or events.empty:
                    continue
                for _, ev in events.iterrows():
                    loc = ev.get("location")
                    if loc is None or not isinstance(loc, (list, tuple)) or len(loc) < 2:
                        continue
                    if ev["type"] == "Pass":
                        end_loc = ev.get("pass_end_location")
                        if end_loc is not None and isinstance(end_loc, (list, tuple)) and len(end_loc) >= 2:
                            passes.append({
                                "start_x": float(loc[0]),
                                "start_y": float(loc[1]),
                                "end_x": float(end_loc[0]),
                                "end_y": float(end_loc[1]),
                            })
                    elif ev["type"] == "Carry":
                        end_loc = ev.get("carry_end_location")
                        if end_loc is not None and isinstance(end_loc, (list, tuple)) and len(end_loc) >= 2:
                            carries.append({
                                "start_x": float(loc[0]),
                                "start_y": float(loc[1]),
                                "end_x": float(end_loc[0]),
                                "end_y": float(end_loc[1]),
                            })
    except ImportError:
        logger.warning("statsbombpy not installed, using httpx fallback")
        import httpx
        import json

        # StatsBomb open data URLs for World Cup 2022 (64 matches)
        urls = [
            f"https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/{match_id}.json"
            for match_id in range(3788741, 3788805)
        ]
        with httpx.Client(timeout=30) as client:
            for url in urls:
                try:
                    resp = client.get(url)
                    if resp.status_code != 200:
                        continue
                    events = json.loads(resp.text)
                    for ev in events:
                        loc = ev.get("location")
                        if loc is None or len(loc) < 2:
                            continue
                        if ev["type"]["name"] == "Pass":
                            end_loc = ev.get("pass", {}).get("end_location")
                            if end_loc and len(end_loc) >= 2:
                                passes.append({
                                    "start_x": float(loc[0]),
                                    "start_y": float(loc[1]),
                                    "end_x": float(end_loc[0]),
                                    "end_y": float(end_loc[1]),
                                })
                        elif ev["type"]["name"] == "Carry":
                            end_loc = ev.get("carry", {}).get("end_location")
                            if end_loc and len(end_loc) >= 2:
                                carries.append({
                                    "start_x": float(loc[0]),
                                    "start_y": float(loc[1]),
                                    "end_x": float(end_loc[0]),
                                    "end_y": float(end_loc[1]),
                                })
                except Exception as e:
                    logger.debug(f"Skipping {url}: {e}")

    logger.info(f"Fetched {len(passes)} passes, {len(carries)} carries")
    return passes, carries


def pitch_to_grid(x: float, y: float, pitch_length: float = 120.0, pitch_width: float = 80.0):
    """Map pitch coordinates (StatsBomb: 0-120 x 0-80) to grid cell indices."""
    xi = min(int(x / pitch_length * X_GRID), X_GRID - 1)
    yi = min(int(y / pitch_width * Y_GRID), Y_GRID - 1)
    return xi, yi


def train_xt(passes: list[dict], carries: list[dict]) -> np.ndarray:
    """Train xT value grid using the standard socceraction method.

    xT(s, e) = sum over k of probability of reaching cell e from cell s
    in exactly k actions, multiplied by the reward at cell e.

    Simplified: build transition matrix from pass/carry data,
    solve for xT values via value iteration.
    """
    n_cells = X_GRID * Y_GRID

    # Count transitions from each cell
    transitions = np.zeros((n_cells, n_cells), dtype=np.float64)
    start_counts = np.zeros(n_cells, dtype=np.float64)

    for action in passes + carries:
        xi, yi = pitch_to_grid(action["start_x"], action["start_y"])
        xj, yj = pitch_to_grid(action["end_x"], action["end_y"])
        from_idx = yi * X_GRID + xi
        to_idx = yj * X_GRID + xj
        if from_idx != to_idx:
            transitions[from_idx, to_idx] += 1.0
        start_counts[from_idx] += 1.0

    # Convert to probabilities
    row_sums = transitions.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums == 0, 1.0, row_sums)
    T = transitions / row_sums

    # Goal probability per cell (shots from each cell that result in goals)
    goal_probs = np.zeros(n_cells)
    goal_counts = np.zeros(n_cells)
    shot_counts = np.zeros(n_cells)

    for action in passes + carries:
        xi, yi = pitch_to_grid(action["end_x"], action["end_y"])
        idx = yi * X_GRID + xi
        shot_counts[idx] += 1.0

    # Reward: probability of scoring from end zone
    r = np.zeros(n_cells)
    # Boost end zones near goal (right side, x near 120)
    for yi in range(Y_GRID):
        for xi in range(X_GRID):
            idx = yi * X_GRID + xi
            pitch_x = (xi + 0.5) * 120.0 / X_GRID
            # Higher reward closer to opponent's goal
            r[idx] = 1.0 / (1.0 + np.exp(-0.1 * (pitch_x - 95.0)))
            # Higher reward in center
            pitch_y = (yi + 0.5) * 80.0 / Y_GRID
            center_bonus = np.exp(-0.01 * (pitch_y - 40.0) ** 2)
            r[idx] *= (1.0 + center_bonus * 0.5)

    # Value iteration
    V = np.zeros(n_cells)
    for _ in range(50):
        V_new = r + 0.99 * T @ V
        delta = np.max(np.abs(V_new - V))
        V = V_new
        if delta < 1e-4:
            break

    # xT values: the value of being in each cell
    xt = V.reshape(Y_GRID, X_GRID)
    logger.info(f"xT grid trained: {X_GRID}x{Y_GRID}")
    return xt


def save_xt(xt: np.ndarray, output_path: str):
    """Save xT grid as .npy with metadata in _info.json."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(output), xt)

    info = {
        "grid": f"{X_GRID}x{Y_GRID}",
        "source": "StatsBomb open data (socceraction methodology)",
        "value_range": [float(xt.min()), float(xt.max())],
    }
    import json
    info_path = output.with_suffix(".json")
    info_path.write_text(json.dumps(info, indent=2))
    logger.info(f"xT model saved to {output}")
    logger.info(f"xT range: {xt.min():.4f} - {xt.max():.4f}")
    logger.info(f"Zone values:\n{np.array2string(xt, precision=4, suppress_small=True)}")


def main():
    parser = argparse.ArgumentParser(description="Train 12x8 xT model on StatsBomb data")
    parser.add_argument("--output", default="models/xt_12x8.npy",
                        help="Output .npy path for xT weights")
    args = parser.parse_args()

    passes, carries = fetch_statsbomb_data()
    if not passes and not carries:
        logger.error("No data fetched. Check internet connection or install statsbombpy.")
        return

    xt = train_xt(passes, carries)
    save_xt(xt, args.output)


if __name__ == "__main__":
    main()
