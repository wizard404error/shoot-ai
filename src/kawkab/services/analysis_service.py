"""Analysis service - statistics, patterns, formations, xG/xT.

Computes per-match and season-level insights from tracking data.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from kawkab.core.logging import get_logger
from kawkab.services.cv_service import FrameDetections, MatchTrackData

logger = get_logger(__name__)


@dataclass
class PlayerStats:
    """Statistics for a single player (tracked ID)."""

    track_id: int
    jersey_number: int | None = None
    name: str | None = None
    team: str | None = None  # "home" or "away"
    position: str | None = None

    distance_covered_m: float = 0.0
    max_speed_kmh: float = 0.0
    avg_speed_kmh: float = 0.0
    passes_attempted: int = 0
    passes_completed: int = 0
    shots: int = 0
    tackles: int = 0
    interceptions: int = 0
    possession_time_s: float = 0.0

    positions: list[tuple[float, float, float]] = field(default_factory=list)
    # list of (timestamp, x, y) for trajectory

    @property
    def pass_accuracy(self) -> float:
        if self.passes_attempted == 0:
            return 0.0
        return self.passes_completed / self.passes_attempted


@dataclass
class TeamStats:
    """Statistics for a team."""

    team_name: str
    possession_pct: float = 0.0
    passes_completed: int = 0
    passes_attempted: int = 0
    shots: int = 0
    shots_on_target: int = 0
    tackles: int = 0
    corners: int = 0
    fouls: int = 0
    distance_covered_km: float = 0.0

    @property
    def pass_accuracy(self) -> float:
        if self.passes_attempted == 0:
            return 0.0
        return self.passes_completed / self.passes_attempted


@dataclass
class MatchAnalysis:
    """Complete analysis for a single match."""

    match_id: int
    duration_seconds: float
    home_team: TeamStats
    away_team: TeamStats
    players: dict[int, PlayerStats]  # track_id -> stats

    events: list[dict] = field(default_factory=list)
    pass_network: dict = field(default_factory=dict)
    formations: dict = field(default_factory=dict)
    pressing_intensity: float = 0.0  # PPDA (lower = more pressing)

    ppda_breakdown: dict = field(default_factory=dict)
    xg_total: dict = field(default_factory=dict)
    xt_total: dict = field(default_factory=dict)

    confidence_overall: float = 0.0
    confidence_breakdown: dict = field(default_factory=dict)


class AnalysisService:
    """Computes match analysis from tracking data."""

    def __init__(
        self,
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
        use_kalman: bool = True,
    ) -> None:
        self.pitch_length = pitch_length_m
        self.pitch_width = pitch_width_m
        self.use_kalman = use_kalman
        logger.info(
            f"AnalysisService: pitch={pitch_length_m}x{pitch_width_m}m, kalman={use_kalman}"
        )

    async def analyze_match(
        self, track_data: MatchTrackData, match_id: int = 0, homography_matrix=None
    ) -> MatchAnalysis:
        """Compute full match analysis from tracking data.

        Args:
            track_data: Output from CVService.process_video
            match_id: Database ID for this match
            homography_matrix: Optional HomographyMatrix for meter-based stats

        Returns:
            Complete MatchAnalysis with stats, events, patterns
        """
        logger.info(f"Analyzing match: {track_data.total_frames} frames")

        if homography_matrix is not None and track_data.player_teams:
            self._assign_teams_by_pitch_side(track_data, homography_matrix)

        players = self._compute_player_stats(track_data, homography_matrix)
        events = self._detect_events(track_data, homography_matrix)
        team_stats = self._compute_team_stats(players, events, track_data, homography_matrix)
        possession = self._compute_possession(track_data, homography_matrix)
        pass_network = self._compute_pass_network(events)

        home = TeamStats(team_name="Home")
        away = TeamStats(team_name="Away")
        home.possession_pct = possession["home"]
        away.possession_pct = possession["away"]

        for event in events:
            team = event.get("team", "home")
            target = home if team == "home" else away
            if event["type"] == "pass":
                target.passes_attempted += 1
                if event.get("completed"):
                    target.passes_completed += 1
            elif event["type"] == "shot":
                target.shots += 1
                if event.get("on_target"):
                    target.shots_on_target += 1

        home_formation = self.detect_formation(track_data, team="home", homography_matrix=homography_matrix)
        away_formation = self.detect_formation(track_data, team="away", homography_matrix=homography_matrix)
        home_ppda = self.compute_ppda(track_data, team="home", homography_matrix=homography_matrix)
        away_ppda = self.compute_ppda(track_data, team="away", homography_matrix=homography_matrix)

        confidence = self._compute_confidence(track_data, events)

        xg_data = self.compute_xg_simple(events)
        xt_data = self.compute_xt_simple(events)
        logger.info(
            f"xG: home={xg_data['home']} away={xg_data['away']} "
            f"({len(xg_data.get('shot_details', []))} shots)"
        )
        logger.info(
            f"xT: home={xt_data['home']} away={xt_data['away']}"
        )

        coords = "meters" if homography_matrix else "pixels"
        logger.info(
            f"Analysis complete: {len(players)} players, "
            f"{len(events)} events, confidence={confidence:.2%}, "
            f"formations: {home_formation['formation']}/{away_formation['formation']}, "
            f"coords={coords}"
        )

        return MatchAnalysis(
            match_id=match_id,
            duration_seconds=track_data.duration_seconds,
            home_team=home,
            away_team=away,
            players=players,
            events=events,
            pass_network=pass_network,
            confidence_overall=confidence,
            formations={
                "home": home_formation,
                "away": away_formation,
            },
            pressing_intensity=home_ppda.get("ppda") or 0.0,
            xg_total=xg_data,
            xt_total=xt_data,
        )

    def _assign_teams_by_pitch_side(
        self, track_data: MatchTrackData, homography_matrix
    ) -> None:
        x_per_team: dict[str, list[float]] = {"home": [], "away": []}
        for tid, entry in track_data.track_registry.items():
            team = track_data.player_teams.get(tid)
            px = entry.get("first_pixel_x")
            if team not in ("home", "away") or px is None:
                continue
            try:
                pitch_x, _ = homography_matrix.pixel_to_pitch(px, 0)
                x_per_team[team].append(pitch_x)
            except Exception:
                continue

        if len(x_per_team["home"]) < 3 or len(x_per_team["away"]) < 3:
            return

        home_med = statistics.median(x_per_team["home"])
        away_med = statistics.median(x_per_team["away"])

        if home_med > away_med:
            track_data.swap_teams()
            logger.info(
                f"Pitch-side heuristic: home players at x={home_med:.0f}m (right), "
                f"away at x={away_med:.0f}m (left) → swapped teams"
            )
        else:
            logger.info(
                f"Pitch-side heuristic: home at x={home_med:.0f}m (left), "
                f"away at x={away_med:.0f}m (right) → already correct"
            )

    def _compute_player_stats(
        self, track_data: MatchTrackData, homography_matrix=None
    ) -> dict[int, PlayerStats]:
        """Compute per-player statistics from tracking data.

        If homography_matrix is provided, distances are in meters.
        Otherwise, pixel-based estimates using pitch width assumption.

        Per-frame delta is capped at MAX_FRAME_DELTA_M to filter
        broadcast-cut teleport artifacts (where same track ID
        briefly jumps across the pitch during camera switches).
        """
        players: dict[int, PlayerStats] = {}
        prev_positions: dict[int, tuple[float, float]] = {}
        max_speed_per_player: dict[int, float] = {}

        fps = track_data.fps
        pixels_per_meter = 720.0 / self.pitch_width

        frame_skip = max(1, track_data.tracking_metrics.get("frame_skip", 1))

        if homography_matrix is not None:
            max_frame_delta_m = 0.5
        else:
            max_frame_delta_m = 25.0

        use_kalman = (
            self.use_kalman
            and getattr(track_data, "match_type", None) == "full_match"
            and homography_matrix is not None
        )
        if use_kalman:
            logger.info("Using Kalman smoother for full-match distance/speed")
            return self._compute_player_stats_kalman(
                track_data, homography_matrix, max_frame_delta_m
            )

        prev_timestamps: dict[int, float] = {}
        is_skip_frame = lambda fno: fno % frame_skip != 0

        for frame in track_data.frames:
            current_positions: dict[int, tuple[float, float]] = {}
            ts = frame.timestamp
            frame_is_skipped = is_skip_frame(frame.frame_number)

            for det in frame.detections:
                if det.class_name != "person" or det.track_id is None:
                    continue

                tid = det.track_id
                if tid not in players:
                    players[tid] = PlayerStats(track_id=tid)
                    if track_data.player_teams:
                        players[tid].team = track_data.player_teams.get(tid, "unknown")

                x1, y1, x2, y2 = det.bbox
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                if homography_matrix is not None:
                    cx, cy = homography_matrix.pixel_to_pitch(cx, cy)

                current_positions[tid] = (cx, cy)
                players[tid].positions.append((ts, cx, cy))

                if frame_is_skipped:
                    continue

                if tid in prev_positions:
                    px, py = prev_positions[tid]
                    dx = cx - px
                    dy = cy - py

                    if homography_matrix is not None:
                        meters = math.sqrt(dx * dx + dy * dy)
                    else:
                        pixel_distance = math.sqrt(dx * dx + dy * dy)
                        meters = pixel_distance / pixels_per_meter

                    if meters > max_frame_delta_m:
                        meters = 0.0

                    players[tid].distance_covered_m += meters

                    if meters > 0 and tid in prev_timestamps:
                        dt = ts - prev_timestamps[tid]
                        if dt > 0:
                            speed_mps = meters / dt
                            speed_kmh = speed_mps * 3.6
                            if speed_kmh <= 36.0:
                                max_speed_per_player[tid] = max(
                                    max_speed_per_player.get(tid, 0), speed_kmh
                                )

                prev_timestamps[tid] = ts

            if not frame_is_skipped:
                prev_positions = current_positions

        for tid, player in players.items():
            if track_data.duration_seconds > 0:
                player.avg_speed_kmh = (
                    player.distance_covered_m / track_data.duration_seconds * 3.6
                )
            player.max_speed_kmh = max_speed_per_player.get(tid, 0.0)

        return players

    def _compute_player_stats_kalman(
        self, track_data: MatchTrackData, homography_matrix, max_frame_delta_m: float
    ) -> dict[int, PlayerStats]:
        """Compute player stats using Kalman smoothing for full-match videos."""
        from kawkab.services.kalman_smoother import PlayerPositionSmoother

        players: dict[int, PlayerStats] = {}
        track_positions: dict[int, list[tuple[float, float, float]]] = defaultdict(list)

        for frame in track_data.frames:
            ts = frame.timestamp
            for det in frame.detections:
                if det.class_name != "person" or det.track_id is None:
                    continue
                tid = det.track_id
                if tid not in players:
                    players[tid] = PlayerStats(track_id=tid)
                    if track_data.player_teams:
                        players[tid].team = track_data.player_teams.get(tid, "unknown")

                x1, y1, x2, y2 = det.bbox
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                if homography_matrix is not None:
                    cx, cy = homography_matrix.pixel_to_pitch(cx, cy)

                track_positions[tid].append((ts, cx, cy))

        for tid, positions in track_positions.items():
            if len(positions) < 2:
                continue

            smoother = PlayerPositionSmoother(
                process_noise_std=0.3,
                measurement_noise_std=0.8,
            )

            smoothed: list[tuple[float, float, float]] = []
            for i, (ts, x, y) in enumerate(positions):
                if i == 0:
                    smoother.update(x, y, 0.0)
                else:
                    dt = positions[i][0] - positions[i - 1][0]
                    smoother.update(x, y, dt)
                sx, sy = smoother.get_position()
                smoothed.append((ts, sx, sy))

            total_distance = 0.0
            max_speed = 0.0
            for i in range(1, len(smoothed)):
                dt = smoothed[i][0] - smoothed[i - 1][0]
                if dt <= 0:
                    continue
                dx = smoothed[i][1] - smoothed[i - 1][1]
                dy = smoothed[i][2] - smoothed[i - 1][2]
                meters = math.sqrt(dx * dx + dy * dy)
                if meters > max_frame_delta_m:
                    meters = 0.0
                total_distance += meters
                speed_mps = meters / dt
                speed_kmh = speed_mps * 3.6
                if speed_kmh <= 36.0:
                    max_speed = max(max_speed, speed_kmh)

            players[tid].distance_covered_m = total_distance
            players[tid].max_speed_kmh = max_speed
            players[tid].positions = [
                (ts, x, y) for ts, x, y in smoothed
            ]

        for tid, player in players.items():
            if track_data.duration_seconds > 0:
                player.avg_speed_kmh = (
                    player.distance_covered_m / track_data.duration_seconds * 3.6
                )

        return players

    def _detect_events(
        self, track_data: MatchTrackData, homography_matrix=None
    ) -> list[dict]:
        events: list[dict] = []
        prev_possession: int | None = None
        ball_track_id: int | None = None
        frames_since_shot: int = 999

        player_proximity_threshold = 60  # pixels
        shot_speed_threshold_pps = 600  # pixels/s fallback
        shot_speed_threshold_mps = 8.0  # m/s with homography
        goal_proximity_m = 20.0
        shot_cooldown_frames = 15

        ball_history: list[tuple[float, float, float, float | None, float | None]] = []
        possession_ball_positions: dict[int, tuple[float, float]] = {}

        for frame in track_data.frames:
            ball_det = None
            player_dets = []

            for det in frame.detections:
                if det.class_name == "sports ball":
                    ball_det = det
                    if det.track_id is not None:
                        ball_track_id = det.track_id
                elif det.class_name == "person":
                    player_dets.append(det)

            if ball_det is None or not player_dets:
                frames_since_shot += 1
                continue

            bx = (ball_det.bbox[0] + ball_det.bbox[2]) / 2
            by = (ball_det.bbox[1] + ball_det.bbox[3]) / 2

            pitch_x: float | None = None
            pitch_y: float | None = None
            if homography_matrix is not None:
                try:
                    pitch_x, pitch_y = homography_matrix.pixel_to_pitch(bx, by)
                except Exception:
                    pass

            closest_player = None
            closest_dist = float("inf")
            for p in player_dets:
                px = (p.bbox[0] + p.bbox[2]) / 2
                py = (p.bbox[1] + p.bbox[3]) / 2
                d = math.sqrt((bx - px) ** 2 + (by - py) ** 2)
                if d < closest_dist:
                    closest_dist = d
                    closest_player = p

            if closest_player is None or closest_player.track_id is None:
                frames_since_shot += 1
                continue

            possession_ball_positions[closest_player.track_id] = (bx, by)

            ball_history.append((frame.timestamp, bx, by, pitch_x, pitch_y))
            if len(ball_history) > 5:
                ball_history.pop(0)

            tid = closest_player.track_id
            frames_since_shot += 1

            if ball_track_id is not None and len(ball_history) >= 3:
                p0 = ball_history[-3]
                p1 = ball_history[-1]
                dt = p1[0] - p0[0]

                if dt > 0.01 and frames_since_shot >= shot_cooldown_frames:
                    dx = p1[1] - p0[1]
                    dy = p1[2] - p0[2]
                    speed_px = math.sqrt(dx * dx + dy * dy) / dt

                    is_shot = False
                    shot_conf = 0.0

                    if homography_matrix is not None and p0[3] is not None and p1[3] is not None:
                        dx_p = p1[3] - p0[3]
                        dy_p = p1[4] - p0[4]
                        speed_pitch = math.sqrt(dx_p * dx_p + dy_p * dy_p) / dt
                        if speed_pitch >= shot_speed_threshold_mps:
                            cx = p1[3]
                            near_left = cx <= goal_proximity_m
                            near_right = cx >= (self.pitch_length - goal_proximity_m)
                            moving_left = dx_p < 0
                            moving_right = dx_p > 0
                            if (near_left and moving_left) or (near_right and moving_right):
                                is_shot = True
                                shot_conf = min(1.0, speed_pitch / 25.0)
                    elif speed_px >= shot_speed_threshold_pps:
                        img_h = frame.image_height
                        near_bottom = by > img_h * 0.7
                        near_top = by < img_h * 0.3
                        moving_down = dy > 0
                        moving_up = dy < 0
                        if (near_bottom and moving_down) or (near_top and moving_up):
                            is_shot = True
                            shot_conf = min(1.0, speed_px / 1200.0)

                    if is_shot:
                        frames_since_shot = 0
                        shot_team = "unknown"
                        if track_data.player_teams:
                            shot_team = track_data.player_teams.get(tid, "unknown")
                            if shot_team == "unknown" and prev_possession is not None:
                                shot_team = track_data.player_teams.get(prev_possession, "unknown")
                            if shot_team == "unknown":
                                shot_team = "home" if tid % 2 == 0 else "away"
                        else:
                            shot_team = "home" if tid % 2 == 0 else "away"

                        shot_metadata = {}
                        on_target = False
                        goal_width_m = 7.32
                        if homography_matrix is not None and p1[3] is not None:
                            bx_pitch = p1[3]
                            by_pitch = p1[4]
                            pitch_len = self.pitch_length
                            pitch_wid = self.pitch_width
                            near_goal_x = 0 if bx_pitch <= pitch_len / 2 else pitch_len
                            goal_cx = near_goal_x
                            goal_cy = pitch_wid / 2
                            d_to_goal = math.sqrt((bx_pitch - goal_cx) ** 2 + (by_pitch - goal_cy) ** 2)
                            angle_to_goal = math.degrees(
                                math.atan2(abs(by_pitch - goal_cy), abs(bx_pitch - goal_cx))
                            )
                            shot_metadata["distance_to_goal_m"] = round(d_to_goal, 1)
                            shot_metadata["angle_to_goal_deg"] = round(angle_to_goal, 1)
                            shot_metadata["pitch_x"] = round(bx_pitch, 1)
                            shot_metadata["pitch_y"] = round(by_pitch, 1)
                            cross_line = abs(bx_pitch - near_goal_x) < 1.0
                            in_frame = abs(by_pitch - goal_cy) < goal_width_m / 2 + 1.0
                            on_target = cross_line and in_frame
                        else:
                            d_pix = math.sqrt(dx * dx + dy * dy)
                            shot_metadata["pixel_speed"] = round(d_pix / max(dt, 0.01), 1)

                        logger.debug(
                            f"Shot by {shot_team}: d={shot_metadata.get('distance_to_goal_m', '?')}m, "
                            f"on_target={on_target}, conf={shot_conf:.2f}"
                        )
                        events.append({
                            "type": "shot",
                            "timestamp": frame.timestamp,
                            "team": shot_team,
                            "on_target": on_target,
                            "confidence": shot_conf,
                            "metadata": shot_metadata,
                        })

            closest_player = None
            closest_dist = float("inf")
            for p in player_dets:
                px = (p.bbox[0] + p.bbox[2]) / 2
                py = (p.bbox[1] + p.bbox[3]) / 2
                d = math.sqrt((bx - px) ** 2 + (by - py) ** 2)
                if d < closest_dist:
                    closest_dist = d
                    closest_player = p

            if closest_player is None or closest_player.track_id is None:
                continue

            if (
                prev_possession is not None
                and closest_player.track_id != prev_possession
                and closest_dist < player_proximity_threshold
            ):
                if track_data.player_teams:
                    team = track_data.player_teams.get(
                        closest_player.track_id, "unknown"
                    )
                else:
                    team = "home" if prev_possession % 2 == 0 else "away"

                start_ball = possession_ball_positions.get(prev_possession, (bx, by))
                fw = frame.image_width or 1
                fh = frame.image_height or 1
                pass_metadata = {
                    "start_x_pct": round(start_ball[0] / fw, 4),
                    "start_y_pct": round(start_ball[1] / fh, 4),
                    "end_x_pct": round(bx / fw, 4),
                    "end_y_pct": round(by / fh, 4),
                }

                events.append(
                    {
                        "type": "pass",
                        "timestamp": frame.timestamp,
                        "from_track_id": prev_possession,
                        "to_track_id": closest_player.track_id,
                        "completed": True,
                        "team": team,
                        "confidence": min(1.0, 1.0 - closest_dist / 200),
                        "metadata": pass_metadata,
                    }
                )

            prev_possession = closest_player.track_id

        return events

    def _compute_team_stats(
        self,
        players: dict[int, PlayerStats],
        events: list[dict],
        track_data: MatchTrackData,
        homography_matrix=None,
    ) -> dict[str, TeamStats]:
        """Aggregate per-team statistics."""
        home = TeamStats(team_name="Home")
        away = TeamStats(team_name="Away")

        for player in players.values():
            target = home if player.team == "home" else away
            target.distance_covered_km += player.distance_covered_m / 1000.0
            target.passes_completed += player.passes_completed
            target.passes_attempted += player.passes_attempted
            target.shots += player.shots
            target.tackles += player.tackles

        return {"home": home, "away": away}

    def _compute_possession(
        self, track_data: MatchTrackData, homography_matrix=None
    ) -> dict[str, float]:
        """Compute possession percentage per team.

        Uses player ball proximity as proxy for possession.
        Team assignment comes from CVService team color detection
        (track_data.player_teams). Falls back to track_id % 2 only
        if team detection was disabled or failed.
        """
        home_frames = 0
        away_frames = 0
        unknown_frames = 0
        use_player_teams = bool(track_data.player_teams)

        for frame in track_data.frames:
            ball_det = None
            player_dets = []

            for det in frame.detections:
                if det.class_name == "sports ball":
                    ball_det = det
                elif det.class_name == "person":
                    player_dets.append(det)

            if ball_det is None or not player_dets:
                continue

            bx = (ball_det.bbox[0] + ball_det.bbox[2]) / 2
            by = (ball_det.bbox[1] + ball_det.bbox[3]) / 2

            closest = None
            closest_dist = float("inf")
            for p in player_dets:
                px = (p.bbox[0] + p.bbox[2]) / 2
                py = (p.bbox[1] + p.bbox[3]) / 2
                d = math.sqrt((bx - px) ** 2 + (by - py) ** 2)
                if d < closest_dist:
                    closest_dist = d
                    closest = p

            if closest and closest.track_id is not None:
                if use_player_teams:
                    team = track_data.player_teams.get(closest.track_id)
                    if team == "home":
                        home_frames += 1
                    elif team == "away":
                        away_frames += 1
                    else:
                        unknown_frames += 1
                else:
                    if closest.track_id % 2 == 0:
                        home_frames += 1
                    else:
                        away_frames += 1

        total = home_frames + away_frames
        if total == 0:
            return {"home": 50.0, "away": 50.0}

        return {
            "home": (home_frames / total) * 100,
            "away": (away_frames / total) * 100,
        }

    def _compute_pass_network(self, events: list[dict]) -> dict:
        """Build pass network graph from pass events."""
        edges: dict[tuple[int, int], int] = defaultdict(int)

        for event in events:
            if event["type"] != "pass" or not event.get("completed"):
                continue
            edge = (event["from_track_id"], event["to_track_id"])
            edges[edge] += 1

        nodes = set()
        for (src, dst) in edges:
            nodes.add(src)
            nodes.add(dst)

        return {
            "nodes": [{"id": n} for n in nodes],
            "edges": [
                {"source": s, "target": t, "weight": w}
                for (s, t), w in edges.items()
            ],
        }

    def _compute_confidence(
        self, track_data: MatchTrackData, events: list[dict]
    ) -> float:
        """Compute overall confidence score based on detection quality."""
        if track_data.total_frames == 0:
            return 0.0

        frames_with_ball = sum(
            1
            for f in track_data.frames
            if any(d.class_name == "sports ball" for d in f.detections)
        )
        frames_with_players = sum(
            1
            for f in track_data.frames
            if any(d.class_name == "person" for d in f.detections)
        )

        ball_pct = frames_with_ball / track_data.total_frames
        player_pct = frames_with_players / track_data.total_frames

        return min(1.0, (ball_pct * 0.4 + player_pct * 0.6))

    def detect_formation(
        self, track_data: MatchTrackData, team: str = "home", n_players: int = 11,
        homography_matrix=None,
    ) -> dict:
        """Detect team formation (e.g., 4-3-3, 4-4-2) using k-means clustering.

        Args:
            track_data: Match tracking data
            team: "home" or "away"
            n_players: Expected number of outfield players (default 10 + GK = 11)
            homography_matrix: Optional HomographyMatrix to convert to meters

        Returns:
            Dict with formation (e.g., "4-3-3"), defensive line height,
            and player positions (in meters if homography provided)
        """
        import math
        from collections import defaultdict

        team_player_positions: dict[int, list[tuple[float, float]]] = defaultdict(list)
        track_first_seen: dict[int, float] = {}
        track_last_seen: dict[int, float] = {}
        use_player_teams = bool(track_data.player_teams)

        for frame in track_data.frames:
            ts = frame.timestamp
            for det in frame.detections:
                if det.class_name != "person" or det.track_id is None:
                    continue
                if use_player_teams:
                    assigned = track_data.player_teams.get(det.track_id)
                    if assigned is None:
                        continue
                    if team == "home" and assigned != "home":
                        continue
                    if team == "away" and assigned != "away":
                        continue
                else:
                    if team == "home":
                        if det.track_id % 2 != 0:
                            continue
                    else:
                        if det.track_id % 2 == 0:
                            continue
                x1, y1, x2, y2 = det.bbox
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                if homography_matrix is not None:
                    cx, cy = homography_matrix.pixel_to_pitch(cx, cy)

                tid = det.track_id
                team_player_positions[tid].append((cx, cy))
                if tid not in track_first_seen:
                    track_first_seen[tid] = ts
                track_last_seen[tid] = ts

        min_span_seconds = max(3.0, track_data.duration_seconds * 0.05)
        team_player_positions = {
            tid: positions
            for tid, positions in team_player_positions.items()
            if (track_last_seen.get(tid, 0) - track_first_seen.get(tid, 0)) >= min_span_seconds
        }
        track_lifetimes = {
            tid: track_last_seen[tid] - track_first_seen[tid]
            for tid in team_player_positions
        }
        logger.debug(
            f"Formation team={team}: {len(team_player_positions)} tracks pass "
            f"span>={min_span_seconds:.1f}s filter"
        )

        if len(team_player_positions) < 5:
            return {
                "formation": "unknown",
                "confidence": 0.0,
                "line_height": None,
                "line_height_m": None,
                "player_count": len(team_player_positions),
                "coordinates": "meters" if homography_matrix else "pixels",
            }

        avg_positions = {
            tid: (sum(p[0] for p in positions) / len(positions),
                  sum(p[1] for p in positions) / len(positions))
            for tid, positions in team_player_positions.items()
        }

        outfield_n = n_players - 1
        max_keep = outfield_n + 3

        if len(avg_positions) > max_keep:
            sorted_by_lifetime = sorted(
                avg_positions.items(),
                key=lambda x: track_lifetimes[x[0]],
                reverse=True,
            )
            avg_positions = dict(sorted_by_lifetime[:max_keep])

        sorted_by_x = sorted(avg_positions.items(), key=lambda x: x[1][0])
        n = len(sorted_by_x)

        n_def = max(2, min(5, round(n * 0.4)))
        n_att = max(1, min(4, round(n * 0.3)))
        n_mid = n - n_def - n_att
        if n_mid < 2:
            n_mid = 2
            n_def = max(2, n - n_att - n_mid)
        if n_mid > 6:
            n_mid = 6
            n_def = max(2, n - n_att - n_mid)

        defenders = [sorted_by_x[i][0] for i in range(n_def)]
        attackers = [sorted_by_x[i][0] for i in range(n - n_att, n)]
        midfielders = [
            sorted_by_x[i][0]
            for i in range(n_def, n - n_att)
        ]

        def_line_height = (
            sum(avg_positions[t][0] for t in defenders) / len(defenders)
            if defenders else 0
        )

        if homography_matrix is not None:
            def_line_height_m = round(def_line_height, 2)
            def_line_pct = def_line_height / homography_matrix.pitch_length_m
        else:
            def_line_height_m = None
            def_line_pct = def_line_height / 1280.0 if def_line_height else 0.5

        formation_str = f"{n_def}-{n_mid}-{n_att}"

        valid_formations = {
            "4-3-3", "4-4-2", "4-2-3-1", "3-5-2", "3-4-3", "5-3-2",
            "5-4-1", "4-1-4-1", "4-5-1", "3-4-1-2", "3-6-1",
            "2-4-4", "4-3-1-2", "4-1-3-2", "4-4-1-1", "5-2-3",
            "3-5-1-1", "4-2-2-2", "4-3-2-1", "4-1-2-3",
        }
        if formation_str in valid_formations:
            confidence = 0.7 if n >= 8 else 0.4
        else:
            confidence = 0.3

        return {
            "formation": formation_str,
            "confidence": confidence,
            "line_height": round(def_line_pct, 3),
            "line_height_m": def_line_height_m,
            "player_count": n,
            "defenders": defenders,
            "midfielders": midfielders,
            "attackers": attackers,
            "coordinates": "meters" if homography_matrix else "pixels",
        }

    def compute_ppda(
        self, track_data: MatchTrackData, team: str = "home", homography_matrix=None
    ) -> dict:
        """Compute PPDA (Passes Per Defensive Action) - measure of pressing.

        Lower PPDA = more intense pressing.
        Typical values:
        - High press: 5-8 PPDA
        - Medium press: 9-12 PPDA
        - Low press: 13+ PPDA

        Args:
            track_data: Match tracking data
            team: "home" or "away"

        Returns:
            Dict with PPDA value, intensity label, and per-period breakdown
        """
        if not track_data.frames:
            return {
                "ppda": None,
                "intensity": "unknown",
                "passes": 0,
                "defensive_actions": 0,
            }

        press_threshold_px = 100
        possession_change_threshold_px = 40
        sample_every = 2

        n_passes = 0
        n_defensive_actions = 0
        prev_possessor_track_id = None
        prev_ball_pos = None
        team_possession_frames = 0
        opp_possession_frames = 0

        for i, frame in enumerate(track_data.frames):
            if i % sample_every != 0:
                continue

            ball_det = None
            team_players = []
            opp_players = []
            for det in frame.detections:
                if det.class_name == "sports ball" and ball_det is None:
                    ball_det = det
                elif det.class_name == "person" and det.track_id is not None:
                    if track_data.player_teams:
                        assigned = track_data.player_teams.get(det.track_id)
                        if assigned == "home":
                            (team_players if team == "home" else opp_players).append(det)
                        elif assigned == "away":
                            (team_players if team == "away" else opp_players).append(det)
                    else:
                        if team == "home":
                            if det.track_id % 2 == 0:
                                team_players.append(det)
                            else:
                                opp_players.append(det)
                        else:
                            if det.track_id % 2 != 0:
                                team_players.append(det)
                            else:
                                opp_players.append(det)

            if ball_det is None or not team_players or not opp_players:
                continue

            bx = (ball_det.bbox[0] + ball_det.bbox[2]) / 2
            by = (ball_det.bbox[1] + ball_det.bbox[3]) / 2

            closest_team_dist = min(
                math.sqrt(((p.bbox[0] + p.bbox[2]) / 2 - bx) ** 2 +
                         ((p.bbox[1] + p.bbox[3]) / 2 - by) ** 2)
                for p in team_players
            )
            closest_opp_dist = min(
                math.sqrt(((p.bbox[0] + p.bbox[2]) / 2 - bx) ** 2 +
                         ((p.bbox[1] + p.bbox[3]) / 2 - by) ** 2)
                for p in opp_players
            )

            closest_team_player = min(
                team_players,
                key=lambda p: math.sqrt(((p.bbox[0] + p.bbox[2]) / 2 - bx) ** 2 +
                                       ((p.bbox[1] + p.bbox[3]) / 2 - by) ** 2)
            )
            current_possessor_track_id = closest_team_player.track_id

            if team == "home":
                if track_data.player_teams:
                    if track_data.player_teams.get(current_possessor_track_id) == "home":
                        team_possession_frames += 1
                    else:
                        opp_possession_frames += 1
                elif current_possessor_track_id % 2 == 0:
                    team_possession_frames += 1
                else:
                    opp_possession_frames += 1
            else:
                if current_possessor_track_id % 2 != 0:
                    team_possession_frames += 1
                else:
                    opp_possession_frames += 1

            if (prev_possessor_track_id is not None
                and current_possessor_track_id != prev_possessor_track_id):
                if closest_opp_dist < press_threshold_px:
                    n_defensive_actions += 1
                    if prev_ball_pos is not None:
                        dx = bx - prev_ball_pos[0]
                        dy = by - prev_ball_pos[1]
                        ball_moved = math.sqrt(dx * dx + dy * dy) > possession_change_threshold_px
                        if ball_moved:
                            n_passes += 1

            prev_possessor_track_id = current_possessor_track_id
            prev_ball_pos = (bx, by)

        if n_defensive_actions == 0:
            return {
                "ppda": None,
                "intensity": "unknown",
                "passes": n_passes,
                "defensive_actions": n_defensive_actions,
                "possession_pct": (
                    team_possession_frames / (team_possession_frames + opp_possession_frames) * 100
                    if (team_possession_frames + opp_possession_frames) > 0 else 50.0
                ),
            }

        ppda = n_passes / n_defensive_actions

        if ppda < 8:
            intensity = "high_press"
        elif ppda < 13:
            intensity = "medium_press"
        else:
            intensity = "low_press"

        return {
            "ppda": round(ppda, 2),
            "intensity": intensity,
            "passes": n_passes,
            "defensive_actions": n_defensive_actions,
            "possession_pct": round(
                team_possession_frames / (team_possession_frames + opp_possession_frames) * 100, 1
            ) if (team_possession_frames + opp_possession_frames) > 0 else 50.0,
        }

    def compute_xg_simple(
        self,
        events: list[dict],
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
    ) -> dict:
        """Compute simple xG (expected goals) from shot events.

        Uses a basic distance + angle model. For production, use socceraction
        with VAEP/xT models trained on professional data.

        Args:
            events: List of detected events (must include 'type' == 'shot')
            pitch_length_m: Real pitch length
            pitch_width_m: Real pitch width

        Returns:
            Dict with total xG per team and per-shot breakdown
        """
        import math

        home_xg = 0.0
        away_xg = 0.0
        shot_details = []

        for event in events:
            if event.get("type") != "shot":
                continue

            timestamp = event.get("timestamp", 0)
            team = event.get("team", "home")
            metadata = event.get("metadata", {})

            distance_m = metadata.get("distance_to_goal_m", 18.0)
            angle_deg = metadata.get("angle_to_goal_deg", 30.0)

            angle_rad = math.radians(angle_deg)
            distance_factor = math.exp(-distance_m / 30.0)
            angle_factor = math.cos(angle_rad) ** 2
            xg = distance_factor * angle_factor * 0.6
            xg = max(0.0, min(1.0, xg))

            if team == "home":
                home_xg += xg
            else:
                away_xg += xg

            shot_details.append({
                "timestamp": timestamp,
                "team": team,
                "distance_m": distance_m,
                "angle_deg": angle_deg,
                "xg": round(xg, 3),
            })

        return {
            "home": round(home_xg, 3),
            "away": round(away_xg, 3),
            "shot_details": shot_details,
        }

    def compute_xt_simple(
        self,
        events: list[dict],
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
    ) -> dict:
        """Compute simple xT (expected threat) for passes and carries.

        Divides pitch into 16 zones (4x4) and assigns threat value based
        on zone location. Closer to goal = higher threat.

        Args:
            events: List of detected events
            pitch_length_m: Real pitch length
            pitch_width_m: Real pitch width

        Returns:
            Dict with total xT per team
        """
        xt_zones = [
            [0.01, 0.02, 0.03, 0.04],
            [0.02, 0.05, 0.08, 0.12],
            [0.03, 0.08, 0.15, 0.25],
            [0.04, 0.12, 0.25, 0.50],
        ]

        def get_xt_value(x_pct: float, y_pct: float) -> float:
            col = min(3, int(x_pct * 4))
            row = min(3, int(y_pct * 4))
            return xt_zones[row][col]

        home_xt = 0.0
        away_xt = 0.0

        for event in events:
            if event.get("type") != "pass":
                continue
            if not event.get("completed"):
                continue

            team = event.get("team", "home")
            metadata = event.get("metadata", {})
            start_x = metadata.get("start_x_pct", 0.5)
            end_x = metadata.get("end_x_pct", 0.6)
            start_xt = get_xt_value(start_x, 0.5)
            end_xt = get_xt_value(end_x, 0.5)
            xt_delta = max(0.0, end_xt - start_xt)

            if team == "home":
                home_xt += xt_delta
            else:
                away_xt += xt_delta

        return {
            "home": round(home_xt, 3),
            "away": round(away_xt, 3),
        }

    def track_formations(
        self,
        track_data: Any,
        window_minutes: int = 5,
    ) -> dict[str, Any]:
        """Track formation changes minute-by-minute using a sliding window.

        For each window, classify the team's formation by counting
        outfield players per third (defensive/midfield/attacking).
        Returns a timeline of formation changes.

        Args:
            track_data: MatchTrackData with .frames
            window_minutes: Length of sliding window in minutes.
        """
        if not hasattr(track_data, "frames") or not track_data.frames:
            return {"home_timeline": [], "away_timeline": [], "changes": 0}
        fps = max(1, getattr(track_data, "fps", 30))
        window_frames = int(window_minutes * 60 * fps)
        home_timeline: list[dict[str, Any]] = []
        away_timeline: list[dict[str, Any]] = []
        for start in range(0, len(track_data.frames), window_frames):
            end = min(start + window_frames, len(track_data.frames))
            window = track_data.frames[start:end]
            home_formation = self._classify_formation_in_window(window, "home")
            away_formation = self._classify_formation_in_window(window, "away")
            ts = getattr(window[0], "timestamp", 0.0) if window else 0.0
            home_timeline.append({"minute": round(ts / 60.0, 1), "formation": home_formation})
            away_timeline.append({"minute": round(ts / 60.0, 1), "formation": away_formation})
        changes = 0
        if home_timeline:
            prev = home_timeline[0]["formation"]
            for entry in home_timeline[1:]:
                if entry["formation"] != prev:
                    changes += 1
                    prev = entry["formation"]
        return {
            "home_timeline": home_timeline,
            "away_timeline": away_timeline,
            "changes": changes,
        }

    def _classify_formation_in_window(self, frames: list[Any], team: str) -> str:
        if not frames:
            return "unknown"
        for frame in frames:
            detections = getattr(frame, "detections", []) or []
            team_dets = [d for d in detections if getattr(d, "team", None) == team and not getattr(d, "is_ball", False)]
            if len(team_dets) >= 10:
                return self._detect_formation(team_dets)
        return "unknown"

    def _detect_formation(self, detections: list[Any]) -> str:
        from collections import Counter
        thirds = Counter()
        for d in detections:
            x = getattr(d, "x", None) or 0
            if hasattr(d, "bbox") and d.bbox is not None:
                try:
                    x = d.bbox.cx
                except AttributeError:
                    x = 0
            third = "D" if x < 35 else ("M" if x < 70 else "A")
            thirds[third] += 1
        d_count = thirds["D"]
        m_count = thirds["M"]
        a_count = thirds["A"]
        if d_count == 0 and m_count == 0 and a_count == 0:
            return "unknown"
        return f"{d_count}-{m_count}-{a_count}"

    def detect_line_breaking_passes(
        self,
        events: list[dict[str, Any]],
        n_lines: int = 3,
    ) -> list[dict[str, Any]]:
        """Detect passes that cross defensive lines.

        A line-breaking pass crosses N+1 vertical lines simultaneously
        (e.g., a pass from defensive third to attacking third crosses
        2 lines, hence "line-breaking").

        Args:
            events: List of pass events with start/end x position.
            n_lines: Minimum number of lines crossed.
        """
        PITCH_LENGTH = 100.0
        line_breaks: list[dict[str, Any]] = []
        line_positions = [PITCH_LENGTH * i / (n_lines + 1) for i in range(1, n_lines + 1)]
        for event in events:
            if event.get("type") != "pass":
                continue
            if not event.get("completed", False):
                continue
            metadata = event.get("metadata", {})
            start_x = metadata.get("start_x_pct", 0.5) * PITCH_LENGTH
            end_x = metadata.get("end_x_pct", 0.6) * PITCH_LENGTH
            if end_x <= start_x:
                continue
            lines_crossed = 0
            for line_x in line_positions:
                if start_x < line_x <= end_x:
                    lines_crossed += 1
            if lines_crossed >= 2:
                line_breaks.append({
                    "team": event.get("team", "home"),
                    "player_track_id": event.get("player_track_id"),
                    "start_x_pct": round(metadata.get("start_x_pct", 0.5), 3),
                    "end_x_pct": round(metadata.get("end_x_pct", 0.6), 3),
                    "lines_crossed": lines_crossed,
                    "vertical_gain_pct": round(end_x / PITCH_LENGTH - start_x / PITCH_LENGTH, 3),
                })
        return line_breaks

    def attribute_possession_robust(
        self,
        events: list[dict[str, Any]],
        frames: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Attribute possession events robustly when track_id is missing.

        For pass/tackle/shot events without a player_track_id, infer
        the most likely player from neighboring events on the same
        team. Falls back to "unknown_player" if no match is found.

        Args:
            events: Pass/tackle/shot events.
            frames: Optional tracking frames for spatial proximity.
        """
        last_known: dict[str, int | None] = {"home": None, "away": None}
        attributed: list[dict[str, Any]] = []
        for event in events:
            team = event.get("team", "home")
            track_id = event.get("player_track_id")
            if track_id is not None:
                last_known[team] = track_id
                attributed.append({**event, "attribution_source": "explicit"})
                continue
            inferred = last_known.get(team)
            if inferred is not None:
                attributed.append({
                    **event,
                    "player_track_id": inferred,
                    "attribution_source": "last_known",
                })
            else:
                attributed.append({
                    **event,
                    "player_track_id": -1,
                    "attribution_source": "unknown",
                })
        return attributed
