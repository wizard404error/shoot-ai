"""Improved post-shot xG model using shot placement zones."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class GoalZone(IntEnum):
    TOP_LEFT = 1
    TOP_CENTER = 2
    TOP_RIGHT = 3
    MID_LEFT = 4
    MID_CENTER = 5
    MID_RIGHT = 6
    BOT_LEFT = 7
    BOT_CENTER = 8
    BOT_RIGHT = 9


@dataclass
class PsXgResult:
    probability: float
    goal_zone: GoalZone
    placement_quality: float
    speed_factor: float
    distance_factor: float


GOAL_ZONE_BASE_PSXG: dict[GoalZone, float] = {
    GoalZone.TOP_LEFT: 0.85,
    GoalZone.TOP_CENTER: 0.55,
    GoalZone.TOP_RIGHT: 0.85,
    GoalZone.MID_LEFT: 0.70,
    GoalZone.MID_CENTER: 0.40,
    GoalZone.MID_RIGHT: 0.70,
    GoalZone.BOT_LEFT: 0.70,
    GoalZone.BOT_CENTER: 0.40,
    GoalZone.BOT_RIGHT: 0.70,
}


def compute_goal_zone(
    shot_x: float,
    shot_y: float,
    goal_left: float = 0.0,
    goal_right: float = 7.32,
    goal_top: float = 0.0,
    goal_bottom: float = 2.44,
) -> GoalZone:
    zone_w = (goal_right - goal_left) / 3.0
    zone_h = (goal_bottom - goal_top) / 3.0

    col = int((shot_x - goal_left) / zone_w)
    col = max(0, min(2, col))
    row = int((shot_y - goal_top) / zone_h)
    row = max(0, min(2, row))

    mapping: dict[tuple[int, int], GoalZone] = {
        (0, 0): GoalZone.TOP_LEFT,
        (1, 0): GoalZone.TOP_CENTER,
        (2, 0): GoalZone.TOP_RIGHT,
        (0, 1): GoalZone.MID_LEFT,
        (1, 1): GoalZone.MID_CENTER,
        (2, 1): GoalZone.MID_RIGHT,
        (0, 2): GoalZone.BOT_LEFT,
        (1, 2): GoalZone.BOT_CENTER,
        (2, 2): GoalZone.BOT_RIGHT,
    }
    return mapping.get((col, row), GoalZone.MID_CENTER)


def compute_placement_quality(
    goal_zone: GoalZone, shot_x: float, shot_y: float
) -> float:
    cx_map: dict[GoalZone, float] = {
        GoalZone.TOP_LEFT: 0.0,
        GoalZone.TOP_CENTER: 3.66,
        GoalZone.TOP_RIGHT: 7.32,
        GoalZone.MID_LEFT: 0.0,
        GoalZone.MID_CENTER: 3.66,
        GoalZone.MID_RIGHT: 7.32,
        GoalZone.BOT_LEFT: 0.0,
        GoalZone.BOT_CENTER: 3.66,
        GoalZone.BOT_RIGHT: 7.32,
    }
    cy_map: dict[GoalZone, float] = {
        GoalZone.TOP_LEFT: 0.0,
        GoalZone.TOP_CENTER: 0.0,
        GoalZone.TOP_RIGHT: 0.0,
        GoalZone.MID_LEFT: 1.22,
        GoalZone.MID_CENTER: 1.22,
        GoalZone.MID_RIGHT: 1.22,
        GoalZone.BOT_LEFT: 2.44,
        GoalZone.BOT_CENTER: 2.44,
        GoalZone.BOT_RIGHT: 2.44,
    }
    cx = cx_map.get(goal_zone, 3.66)
    cy = cy_map.get(goal_zone, 1.22)
    dist = math.sqrt((shot_x - cx) ** 2 + (shot_y - cy) ** 2)
    max_dist = math.sqrt((3.66) ** 2 + (1.22) ** 2)
    quality = 1.0 - min(dist / max_dist, 1.0)
    return max(0.0, min(1.0, quality))


def compute_psxg(
    shot_x: float,
    shot_y: float,
    shot_type: str,
    distance: float,
    placement_quality: float | None = None,
) -> float:
    goal_zone = compute_goal_zone(shot_x, shot_y)
    base = GOAL_ZONE_BASE_PSXG.get(goal_zone, 0.55)

    if placement_quality is None:
        placement_quality = compute_placement_quality(goal_zone, shot_x, shot_y)

    distance_factor = math.exp(-distance / 25.0)
    distance_factor = max(0.3, min(1.0, distance_factor))

    speed_factor = 1.0
    if shot_type == "header":
        speed_factor = 0.85
    elif shot_type == "volley":
        speed_factor = 1.1
    elif shot_type == "free_kick":
        speed_factor = 1.05

    psxg = base * (0.6 + 0.4 * placement_quality) * distance_factor * speed_factor
    return max(0.01, min(0.99, psxg))
