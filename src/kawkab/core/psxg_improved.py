"""Improved Post-Shot xG (PSxG) model.

Estimates the probability of a shot on target becoming a goal
based on shot placement (9-zone goal mouth grid), shot speed
proxy (distance + shot type), and body part.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from kawkab.core.game_constants import GAME

PITCH_LENGTH = GAME.PITCH_LENGTH_M
PITCH_WIDTH = GAME.PITCH_WIDTH_M
GOAL_WIDTH_M = 7.32
GOAL_HEIGHT_M = 2.44


@dataclass
class PsXgResult:
    psxg: float = 0.0
    placement_zone: str = ""
    placement_x: float = 0.0
    placement_y: float = 0.0
    speed_proxy: float = 0.0
    body_part: str = ""
    shot_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "psxg": round(self.psxg, 4),
            "placement_zone": self.placement_zone,
            "placement_x": round(self.placement_x, 2),
            "placement_y": round(self.placement_y, 2),
            "speed_proxy": round(self.speed_proxy, 2),
            "body_part": self.body_part,
            "shot_type": self.shot_type,
        }


# 9-zone goal mouth: x = horizontal (left/center/right), y = vertical (top/center/bottom)
# Values represent save difficulty: 1.0 = unsavable, 0.0 = easy save
PLACEMENT_DIFFICULTY: dict[str, float] = {
    "top_left": 0.85,
    "top_center": 0.65,
    "top_right": 0.85,
    "mid_left": 0.70,
    "mid_center": 0.30,
    "mid_right": 0.70,
    "bottom_left": 0.75,
    "bottom_center": 0.25,
    "bottom_right": 0.75,
}

# Body part multipliers for shot power/speed
BODY_PART_SPEED: dict[str, float] = {
    "right_foot": 1.0,
    "left_foot": 0.95,
    "head": 0.5,
    "other": 0.6,
}

# Shot type speed modifiers
SHOT_TYPE_SPEED: dict[str, float] = {
    "open_play": 1.0,
    "volley": 1.15,
    "half_volley": 1.1,
    "header": 0.5,
    "free_kick": 1.2,
    "penalty": 1.0,
}

# Distance penalty (further = lower PSxG due to lower placement precision)
DISTANCE_PENALTY_FACTOR = 0.005


def _classify_placement(
    placement_x: float,
    placement_y: float,
) -> str:
    """Classify shot placement into 9-zone grid.

    Args:
        placement_x: Horizontal position relative to goal center (-3.66 to +3.66).
        placement_y: Vertical position from ground (0 to 2.44).

    Returns:
        Zone key like 'top_left', 'mid_center', etc.
    """
    if placement_y > GOAL_HEIGHT_M * 0.6:
        vert = "top"
    elif placement_y > GOAL_HEIGHT_M * 0.3:
        vert = "mid"
    else:
        vert = "bottom"

    if placement_x < -GOAL_WIDTH_M * 0.2:
        horiz = "left"
    elif placement_x > GOAL_WIDTH_M * 0.2:
        horiz = "right"
    else:
        horiz = "center"

    return f"{vert}_{horiz}"


def compute_psxg(shot_event: dict[str, Any]) -> PsXgResult:
    """Compute Post-Shot xG for a shot on target.

    Uses a 9-zone goal mouth placement grid, shot speed proxy
    (derived from distance, body part, shot type), and placement
    accuracy inferred from distance.

    Args:
        shot_event: Dict with optional placement_x, placement_y (goal-relative),
            end_x, end_y, start_x, start_y, body_part, shot_type.

    Returns:
        PsXgResult with psxg and factor breakdown.
    """
    start_x = shot_event.get("start_x", PITCH_LENGTH / 2)
    start_y = shot_event.get("start_y", PITCH_WIDTH / 2)
    end_x = shot_event.get("end_x", start_x)
    end_y = shot_event.get("end_y", start_y)

    distance_m = math.hypot(end_x - start_x, end_y - start_y)

    placement_x = shot_event.get("placement_x", 0.0)
    placement_y = shot_event.get("placement_y", GOAL_HEIGHT_M * 0.5)

    body_part = shot_event.get("body_part", "right_foot")
    shot_type = shot_event.get("shot_type", "open_play")

    placement_key = _classify_placement(placement_x, placement_y)
    difficulty = PLACEMENT_DIFFICULTY.get(placement_key, 0.5)

    body_speed = BODY_PART_SPEED.get(body_part, 1.0)
    shot_speed = SHOT_TYPE_SPEED.get(shot_type, 1.0)
    speed_proxy = body_speed * shot_speed * max(1.0, 30.0 / max(distance_m, 1.0))

    distance_decay = max(0.0, 1.0 - distance_m * DISTANCE_PENALTY_FACTOR)

    psxg = difficulty * speed_proxy * 0.5 * distance_decay
    psxg = min(max(psxg, 0.01), 0.98)

    return PsXgResult(
        psxg=round(psxg, 4),
        placement_zone=placement_key,
        placement_x=round(placement_x, 2),
        placement_y=round(placement_y, 2),
        speed_proxy=round(speed_proxy, 2),
        body_part=body_part,
        shot_type=shot_type,
    )
