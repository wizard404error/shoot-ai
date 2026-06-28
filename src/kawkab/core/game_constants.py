from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameConstants:
    """Game-specific constants (not user-configurable)."""

    PITCH_LENGTH_M: float = 105.0
    PITCH_WIDTH_M: float = 68.0
    PRESS_THRESHOLD_M: float = 5.0
    POSSESSION_CHANGE_DIST_M: float = 2.0
    FINAL_THIRD_PCT: float = 2.0 / 3.0
    CARRY_PIXEL_TO_METER_RATIO: float = 0.015
    MOMENTUM_WINDOW_MIN: int = 5
    MOMENTUM_WINDOW_MINUTES: int = 5
    PASS_FLOW_GRID_CELLS: int = 5

    # Heatmap defaults
    HEATMAP_GRID_COLS: int = 40
    HEATMAP_GRID_ROWS: int = 60
    HEATMAP_KERNEL_SIZE: int = 3

    # PPDA / pressing
    PPDA_ATTACKING_THRESHOLD_PCT: float = 0.4

    # Progressive actions
    PROGRESSIVE_MIN_PROGRESSION_RATIO: float = 0.25
    PROGRESSIVE_ATTACKING_THIRD_FRACTION: float = 0.6
    PROGRESSIVE_MIN_CARRY_M: float = 5.0

    # Pressing trap zone boundaries (left, right as fraction of pitch width)
    PRESSING_TRAP_ZONE_BOUNDARY_PCT: tuple = (0.25, 0.75)


GAME = GameConstants()
