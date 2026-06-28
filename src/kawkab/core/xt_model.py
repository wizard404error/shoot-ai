"""Expected Threat (xT) model for football analytics.

Computes the threat value of each pitch zone by solving
a transition matrix built from actual match events (passes, carries).

xT values represent the probability of scoring from each zone,
accounting for the probability of moving the ball to higher-threat zones.

References:
    - Singh (2019) "Expected Threat (xT)"
    - Fernandez et al. (2018) "Decomposing the Immeasurable"
"""

from __future__ import annotations

import functools
import math
from collections import defaultdict
from typing import Any

import numpy as np


class ExpectedThreatModel:
    """Data-driven expected threat model.

    Builds a transition matrix from match events and solves
    for zone threat values using the xT algorithm.

    Args:
        rows: Number of vertical zones (default 16).
        cols: Number of horizontal zones (default 12).
        pitch_length: Pitch length in meters.
        pitch_width: Pitch width in meters.
        gamma: Discount factor for future actions (default 0.9).
    """

    def __init__(
        self,
        rows: int = 20,
        cols: int = 32,
        pitch_length: float = 105.0,
        pitch_width: float = 68.0,
        gamma: float = 0.9,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.pitch_length = pitch_length
        self.pitch_width = pitch_width
        self.gamma = gamma
        self._transition = None
        self._ze_values: np.ndarray | None = None

    @functools.lru_cache(maxsize=256)
    def _zone_from_position(
        self, x: float, y: float
    ) -> tuple[int, int]:
        col = min(self.cols - 1, max(0, int(x / self.pitch_length * self.cols)))
        row = min(self.rows - 1, max(0, int(y / self.pitch_width * self.rows)))
        return (row, col)

    def build_transition_matrix(
        self,
        events: list[dict[str, Any]],
    ) -> None:
        transitions = defaultdict(lambda: defaultdict(int))
        possession_from_zone = defaultdict(int)
        shots_from_zone = defaultdict(int)
        goals_from_zone = defaultdict(int)

        for ev in events:
            if ev.get("type") not in ("pass", "carry"):
                continue
            sx = ev.get("start_x", 0.0)
            sy = ev.get("start_y", 34.0)
            ex = ev.get("end_x", 0.0)
            ey = ev.get("end_y", 34.0)
            start_zone = self._zone_from_position(sx, sy)
            end_zone = self._zone_from_position(ex, ey)
            possession_from_zone[start_zone] += 1

            if ev.get("completed", True):
                # Successful actions: transition to destination zone
                if start_zone != end_zone:
                    transitions[start_zone][end_zone] += 1
            else:
                # Failed actions: transition to opponent's equivalent zone
                # (mirror across pitch: col = cols - 1 - col)
                opp_row = end_zone[0]
                opp_col = self.cols - 1 - end_zone[1]
                opp_zone = (opp_row, opp_col)
                if start_zone != opp_zone:
                    transitions[start_zone][opp_zone] += 1

        for ev in events:
            if ev.get("type") != "shot":
                continue
            sx = ev.get("start_x", 0.0)
            sy = ev.get("start_y", 34.0)
            zone = self._zone_from_position(sx, sy)
            shots_from_zone[zone] += 1
            possession_from_zone[zone] += 1
            if ev.get("is_goal", False):
                goals_from_zone[zone] += 1

        self._transition = dict(transitions)
        self._ze_values = self._solve_xT(possession_from_zone, goals_from_zone)

    def _solve_xT(
        self,
        possession_from_zone: dict[tuple[int, int], int] | None = None,
        goals_from_zone: dict[tuple[int, int], int] | None = None,
    ) -> np.ndarray:
        possession_from_zone = possession_from_zone or {}
        goals_from_zone = goals_from_zone or {}

        # ze = goals / total_possessions (NOT goals / shots)
        # This captures P(score|possession in zone) not P(score|shot in zone)
        ze = np.zeros((self.rows, self.cols), dtype=np.float64)
        for (r, c), count in possession_from_zone.items():
            goals = goals_from_zone.get((r, c), 0)
            ze[r, c] = goals / max(count, 1)

        if self._transition is None or not self._transition:
            return ze

        n_zones = self.rows * self.cols
        xT = ze.flatten().copy()

        # Power iteration: xT_new[src] = ze[src] + gamma * sum(prob * xT[dst])
        for _iteration in range(100):
            prev = xT.copy()
            for (src_r, src_c), targets in self._transition.items():
                src_idx = src_r * self.cols + src_c
                total = sum(targets.values())
                if total == 0:
                    continue
                weighted_sum = 0.0
                for (dst_r, dst_c), count in targets.items():
                    dst_idx = dst_r * self.cols + dst_c
                    weighted_sum += (count / total) * prev[dst_idx]
                xT[src_idx] = ze[src_r, src_c] + self.gamma * weighted_sum

            delta = float(np.max(np.abs(xT - prev)))
            if delta < 1e-6:
                break

        return xT.reshape(self.rows, self.cols)

    def compute_action_xt(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
    ) -> float:
        if self._ze_values is None:
            return 0.0
        start_zone = self._zone_from_position(start_x, start_y)
        end_zone = self._zone_from_position(end_x, end_y)
        start_val = self._ze_values[start_zone[0], start_zone[1]]
        end_val = self._ze_values[end_zone[0], end_zone[1]]
        return max(0.0, end_val - start_val)

    @functools.lru_cache(maxsize=128)
    def _get_zone_value(self, row: int, col: int) -> float:
        if self._ze_values is None:
            return 0.0
        return float(self._ze_values[row, col])

    def get_zone_values(self) -> np.ndarray:
        if self._ze_values is None:
            return np.zeros((self.rows, self.cols), dtype=np.float64)
        return self._ze_values.copy()

    def get_zone_grid(self) -> list[list[float]]:
        vals = self.get_zone_values()
        return [[round(float(vals[r, c]), 4) for c in range(self.cols)] for r in range(self.rows)]

    def compute_match_xt(
        self,
        events: list[dict[str, Any]],
    ) -> dict[str, float]:
        self.build_transition_matrix(events)
        home_xt = 0.0
        away_xt = 0.0

        for ev in events:
            if ev.get("type") not in ("pass", "carry"):
                continue
            if not ev.get("completed", True):
                continue
            xt_gained = self.compute_action_xt(
                ev.get("start_x", 0.0),
                ev.get("start_y", 34.0),
                ev.get("end_x", 0.0),
                ev.get("end_y", 34.0),
            )
            if ev.get("team") == "home":
                home_xt += xt_gained
            else:
                away_xt += xt_gained

        return {
            "home": round(home_xt, 4),
            "away": round(away_xt, 4),
        }
