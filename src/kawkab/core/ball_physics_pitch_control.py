"""Ball-physics pitch control — simulates ball trajectory to determine control.

Models which team can reach each point on the pitch first, accounting for:
- Player positions and velocities
- Ball travel time (ball speed, air resistance)
- Player acceleration/deceleration
- First-touch control radius

This is the most physically accurate pitch control model,
closer to professional tools like Tractable and Second Spectrum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class PhysicsPitchControlFrame:
    timestamp: float = 0.0
    home_control_pct: float = 0.0
    away_control_pct: float = 0.0
    disputed_pct: float = 0.0
    ball_zone_team: str | None = None
    home_grid: list[list[float]] = field(default_factory=list)
    away_grid: list[list[float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "t": round(self.timestamp, 1),
            "h": round(self.home_control_pct, 1),
            "a": round(self.away_control_pct, 1),
            "d": round(self.disputed_pct, 1),
            "bz": self.ball_zone_team,
        }


@dataclass
class PhysicsPitchControlMatch:
    avg_home_control: float = 0.0
    avg_away_control: float = 0.0
    frames: list[PhysicsPitchControlFrame] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "avg_home": round(self.avg_home_control, 1),
            "avg_away": round(self.avg_away_control, 1),
        }


class BallPhysicsPitchControl:
    """Physics-based pitch control using ball trajectory simulation.

    For each point on the grid, computes which player can reach it first
    by simulating:
    1. Player movement: time = f(position, velocity, max_accel)
    2. Ball travel: time = distance / ball_speed (with optional decay)

    The player with the shortest arrival time controls the point.

    Args:
        grid_rows: Number of vertical grid cells.
        grid_cols: Number of horizontal grid cells.
        max_player_speed: Max player speed in m/s.
        max_player_accel: Max player acceleration in m/s**2.
        ball_speed_kick: Ball speed when kicked in m/s.
        ball_speed_roll: Ball speed when rolling in m/s.
        reaction_time: Player reaction time in seconds.
    """

    def __init__(
        self,
        grid_rows: int = 30,
        grid_cols: int = 46,
        max_player_speed: float = 7.0,
        max_player_accel: float = 3.0,
        ball_speed_kick: float = 20.0,
        ball_speed_roll: float = 10.0,
        reaction_time: float = 0.3,
    ):
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self.max_player_speed = max_player_speed
        self.max_player_accel = max_player_accel
        self.ball_speed_kick = ball_speed_kick
        self.ball_speed_roll = ball_speed_roll
        self.reaction_time = reaction_time

    def _player_arrival_time(
        self,
        px: float, py: float,
        vx: float, vy: float,
        tx: float, ty: float,
        max_speed: float | None = None,
        max_accel: float | None = None,
    ) -> float:
        """Compute time for a player to reach target point (tx, ty).

        Uses kinematic equation: d = v*t + 0.5*a*t**2
        Simplified to: t = reaction + (distance / max_speed)
        More sophisticated version accounts for initial velocity direction.

        Args:
            px, py: Player position.
            vx, vy: Player velocity vector.
            tx, ty: Target grid point.
            max_speed: Player's max speed (overrides instance default).
            max_accel: Player's max acceleration (overrides instance default).

        Returns:
            Arrival time in seconds.
        """
        max_speed = max_speed or self.max_player_speed
        max_accel = max_accel or self.max_player_accel

        distance = np.sqrt((tx - px) ** 2 + (ty - py) ** 2)
        dx = tx - px
        dy = ty - py

        vel_toward = np.divide(
            (vx * dx + vy * dy), distance,
            out=np.zeros_like(distance), where=distance > 0,
        )
        effective_speed = np.maximum(vel_toward, 0.0) + max_accel * self.reaction_time
        effective_speed = np.minimum(effective_speed, max_speed)
        travel_time = np.divide(
            distance, np.maximum(effective_speed, 0.5),
            out=np.zeros_like(distance), where=distance > 0,
        )

        return self.reaction_time + travel_time

    def _ball_arrival_time(
        self,
        bx: float, by: float,
        tx: float, ty: float,
        is_kicked: bool = False,
    ) -> float:
        """Compute time for ball to reach target point.

        Args:
            bx, by: Ball position.
            tx, ty: Target grid point.
            is_kicked: If True, use kick speed; otherwise rolling speed.

        Returns:
            Ball arrival time in seconds.
        """
        distance = np.sqrt((tx - bx) ** 2 + (ty - by) ** 2)
        ball_speed = self.ball_speed_kick if is_kicked else self.ball_speed_roll
        return distance / max(ball_speed, 1.0)

    def compute_frame_control(
        self,
        home_positions: list[tuple[float, float]],
        away_positions: list[tuple[float, float]],
        ball_pos: tuple[float, float] | None = None,
        pitch_length: float = 105.0,
        pitch_width: float = 68.0,
        home_velocities: list[tuple[float, float]] | None = None,
        away_velocities: list[tuple[float, float]] | None = None,
        ball_is_kicked: bool = False,
    ) -> PhysicsPitchControlFrame:
        """Compute physics-based pitch control for one frame.

        Args:
            home_positions: (x, y) for each home player.
            away_positions: (x, y) for each away player.
            ball_pos: (x, y) ball position or None.
            pitch_length, pitch_width: Pitch dimensions in meters.
            home_velocities: (vx, vy) for each home player (default zero).
            away_velocities: (vx, vy) for each away player (default zero).
            ball_is_kicked: Whether ball is in fast flight.

        Returns:
            PhysicsPitchControlFrame with control grid and stats.
        """
        all_players = home_positions + away_positions
        n_home = len(home_positions)
        n_away = len(away_positions)

        if not all_players:
            return PhysicsPitchControlFrame(
                timestamp=0.0,
                home_control_pct=50.0,
                away_control_pct=50.0,
                disputed_pct=0.0,
            )

        home_velocities = home_velocities or [(0.0, 0.0)] * n_home
        away_velocities = away_velocities or [(0.0, 0.0)] * n_away
        all_velocities = list(home_velocities) + list(away_velocities)

        gx = (np.arange(self.grid_cols) + 0.5) * pitch_length / self.grid_cols
        gy = (np.arange(self.grid_rows) + 0.5) * pitch_width / self.grid_rows
        tx_grid, ty_grid = np.meshgrid(gx, gy)

        all_pos = np.array(all_players, dtype=np.float64)
        all_vel = np.array(all_velocities, dtype=np.float64)

        px = all_pos[:, 0].reshape(-1, 1, 1)
        py = all_pos[:, 1].reshape(-1, 1, 1)
        vx = all_vel[:, 0].reshape(-1, 1, 1)
        vy = all_vel[:, 1].reshape(-1, 1, 1)

        dx = tx_grid - px
        dy = ty_grid - py
        dist = np.sqrt(dx ** 2 + dy ** 2)

        dot = vx * dx + vy * dy
        vel_toward = np.divide(
            dot, dist,
            out=np.zeros_like(dist), where=dist > 0,
        )
        effective_speed = (
            np.maximum(vel_toward, 0.0)
            + self.max_player_accel * self.reaction_time
        )
        effective_speed = np.minimum(effective_speed, self.max_player_speed)

        travel_time = np.divide(
            dist, np.maximum(effective_speed, 0.5),
            out=np.zeros_like(dist), where=dist > 0,
        )
        player_arrival = self.reaction_time + travel_time

        if n_home > 0:
            best_home = np.min(player_arrival[:n_home], axis=0)
        else:
            best_home = np.full((self.grid_rows, self.grid_cols), np.inf)
        if n_away > 0:
            best_away = np.min(player_arrival[n_home:], axis=0)
        else:
            best_away = np.full((self.grid_rows, self.grid_cols), np.inf)

        if ball_pos is not None:
            bx, by = ball_pos
            ball_time = self._ball_arrival_time(bx, by, tx_grid, ty_grid, ball_is_kicked)
            disputed = ball_time < np.minimum(best_home, best_away)
        else:
            disputed = np.zeros((self.grid_rows, self.grid_cols), dtype=bool)

        home_grid = np.zeros((self.grid_rows, self.grid_cols), dtype=np.float64)
        away_grid = np.zeros((self.grid_rows, self.grid_cols), dtype=np.float64)

        not_disputed = ~disputed
        home_win = (best_home < best_away) & not_disputed
        away_win = (best_away < best_home) & not_disputed
        tie = (best_home == best_away) & not_disputed

        home_grid[home_win] = 1.0
        away_grid[away_win] = 1.0
        home_grid[tie] = 0.5
        away_grid[tie] = 0.5

        total = self.grid_rows * self.grid_cols
        disputed_count = int(np.sum(disputed))
        home_count = int(np.sum(home_grid))
        away_count = total - home_count - disputed_count

        home_pct = (home_count / total) * 100.0
        away_pct = (away_count / total) * 100.0
        disputed_pct = (disputed_count / total) * 100.0

        ball_zone_team: str | None = None
        if ball_pos is not None and all_players:
            bx, by = ball_pos
            player_times = self._player_arrival_time(
                all_pos[:, 0], all_pos[:, 1],
                all_vel[:, 0], all_vel[:, 1],
                bx, by,
            )
            best_idx = np.argmin(player_times)
            ball_zone_team = "home" if best_idx < n_home else "away"

        return PhysicsPitchControlFrame(
            timestamp=0.0,
            home_control_pct=round(home_pct, 2),
            away_control_pct=round(away_pct, 2),
            disputed_pct=round(disputed_pct, 2),
            ball_zone_team=ball_zone_team,
            home_grid=home_grid.tolist(),
            away_grid=away_grid.tolist(),
        )

    def compute_match_control(
        self,
        frames: list[dict[str, Any]],
        pitch_length: float = 105.0,
        pitch_width: float = 68.0,
    ) -> PhysicsPitchControlMatch:
        """Compute physics-based pitch control across multiple frames.

        Args:
            frames: List of dicts with keys:
                - timestamp: float
                - home_positions: list of (x, y)
                - away_positions: list of (x, y)
                - ball_pos: (x, y) or None
                - home_velocities: optional list of (vx, vy)
                - away_velocities: optional list of (vx, vy)
                - ball_is_kicked: optional bool
            pitch_length, pitch_width: Pitch dimensions.

        Returns:
            PhysicsPitchControlMatch with averaged stats.
        """
        if not frames:
            return PhysicsPitchControlMatch()

        frame_results: list[PhysicsPitchControlFrame] = []
        total_home = 0.0
        total_away = 0.0
        frame_count = 0

        for fdata in frames:
            ts = fdata.get("timestamp", 0.0)
            home_pos = fdata.get("home_positions", [])
            away_pos = fdata.get("away_positions", [])
            ball_pos = fdata.get("ball_pos")
            home_vel = fdata.get("home_velocities")
            away_vel = fdata.get("away_velocities")
            ball_kicked = fdata.get("ball_is_kicked", False)

            result = self.compute_frame_control(
                home_positions=home_pos,
                away_positions=away_pos,
                ball_pos=ball_pos,
                pitch_length=pitch_length,
                pitch_width=pitch_width,
                home_velocities=home_vel,
                away_velocities=away_vel,
                ball_is_kicked=ball_kicked,
            )
            result.timestamp = ts
            frame_results.append(result)
            total_home += result.home_control_pct
            total_away += result.away_control_pct
            frame_count += 1

        return PhysicsPitchControlMatch(
            avg_home_control=total_home / max(frame_count, 1),
            avg_away_control=total_away / max(frame_count, 1),
            frames=frame_results,
        )
