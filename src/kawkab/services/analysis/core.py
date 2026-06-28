"""Core analysis service — shared dataclasses, constants, and orchestrator."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from kawkab.core.game_constants import GAME
from kawkab.core.logging import get_logger
from kawkab.core.events import (
    AssistType,
    BaseEvent,
    BodyPart,
    CarryEvent,
    EventType,
    PassEvent,
    PassType,
    PressureContext,
    ShotEvent,
    ShotType,
    TackleType,
)
from kawkab.core.xg_model import compute_xg, compute_xg_from_shot_event
from kawkab.core.pitch_control import VoronoiPitchControl, MatchPitchControl
from kawkab.core.player_rating import (
    PlayerPosition,
    PlayerRating,
    compute_rating,
    _infer_position_from_x,
)
from kawkab.services.cv_service import FrameDetections, MatchTrackData

logger = get_logger(__name__)

PITCH_LENGTH = GAME.PITCH_LENGTH_M
PITCH_WIDTH = GAME.PITCH_WIDTH_M


@dataclass
class PlayerStats:
    track_id: int
    jersey_number: int | None = None
    name: str | None = None
    team: str | None = None
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

    @property
    def pass_accuracy(self) -> float:
        if self.passes_attempted == 0:
            return 0.0
        return self.passes_completed / self.passes_attempted


@dataclass
class TeamStats:
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
    match_id: int
    duration_seconds: float
    home_team: TeamStats
    away_team: TeamStats
    players: dict[int, PlayerStats]
    events: list[dict] = field(default_factory=list)
    pass_network: dict = field(default_factory=dict)
    formations: dict = field(default_factory=dict)
    pressing_intensity: float = 0.0
    ppda_breakdown: dict = field(default_factory=dict)
    xg_total: dict = field(default_factory=dict)
    xt_total: dict = field(default_factory=dict)
    confidence_overall: float = 0.0
    confidence_breakdown: dict = field(default_factory=dict)
    typed_events: list[BaseEvent] = field(default_factory=list)
    pass_type_breakdown: dict = field(default_factory=dict)
    carry_events: list[dict] = field(default_factory=list)
    progressive_passes: list[dict] = field(default_factory=list)
    progressive_carries: list[dict] = field(default_factory=list)
    pitch_control: MatchPitchControl | None = None
    player_ratings: dict[int, PlayerRating] = field(default_factory=dict)


class AnalysisServiceCore:
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

    @staticmethod
    def _ensure_package_loaded(package_name: str) -> None:
        parts = package_name.split(".")
        for i in range(1, len(parts) + 1):
            prefix = ".".join(parts[:i])
            if prefix not in __import__("sys").modules:
                try:
                    __import__("importlib").import_module(prefix)
                except ImportError:
                    pass

    async def analyze_match(
        self, track_data: MatchTrackData, match_id: int = 0, homography_matrix=None
    ) -> MatchAnalysis:
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

        typed_events: list[BaseEvent] = []
        for event in events:
            team = event.get("team", "home")
            target = home if team == "home" else away
            if event["type"] == "pass":
                target.passes_attempted += 1
                if event.get("completed"):
                    target.passes_completed += 1
                pe = self._build_typed_pass(event, homography_matrix)
                typed_events.append(pe)
            elif event["type"] == "shot":
                target.shots += 1
                if event.get("on_target"):
                    target.shots_on_target += 1
                se = self._build_typed_shot(event, homography_matrix)
                typed_events.append(se)

        for ev in typed_events:
            if isinstance(ev, PassEvent) and ev.track_id is not None:
                player = players.get(ev.track_id)
                if player:
                    player.passes_attempted += 1
                    if ev.completed:
                        player.passes_completed += 1

        carry_dicts = self._detect_carries(track_data, typed_events, homography_matrix)
        for cd in carry_dicts:
            typed_events.append(cd)

        self._infer_pressure_on_events(track_data, typed_events)
        self._classify_pass_types(typed_events, homography_matrix)
        progressive_passes_list = self._find_progressive_passes(typed_events, homography_matrix)
        pass_breakdown = self._compute_pass_type_breakdown(typed_events)

        carry_events_list = [c.to_dict() for c in typed_events if isinstance(c, CarryEvent)]
        progressive_carries_list = [
            c.to_dict() for c in typed_events
            if isinstance(c, CarryEvent) and c.is_progressive
        ]

        home_formation = self.detect_formation(track_data, team="home", homography_matrix=homography_matrix)
        away_formation = self.detect_formation(track_data, team="away", homography_matrix=homography_matrix)
        home_ppda = self.compute_ppda(track_data, team="home", homography_matrix=homography_matrix)
        away_ppda = self.compute_ppda(track_data, team="away", homography_matrix=homography_matrix)
        confidence = self._compute_confidence(track_data, events)

        shot_events = [e for e in typed_events if isinstance(e, ShotEvent)]
        for se in shot_events:
            se.xg = compute_xg_from_shot_event(se)
            se.xg = max(0.0, min(1.0, se.xg))
        home_xg = sum(e.xg for e in shot_events if e.team == "home")
        away_xg = sum(e.xg for e in shot_events if e.team == "away")
        xg_data = {
            "home": round(home_xg, 3),
            "away": round(away_xg, 3),
            "shot_details": [
                {
                    "timestamp": e.timestamp,
                    "team": e.team,
                    "distance_m": e.distance_m or 0,
                    "angle_deg": e.angle_deg or 0,
                    "xg": round(e.xg, 4),
                    "on_target": e.on_target,
                    "body_part": e.body_part.value if e.body_part else "unknown",
                }
                for e in shot_events
            ],
        }

        xt_data = self.compute_xt_simple(events)
        logger.info(
            f"xG: home={xg_data['home']} away={xg_data['away']} "
            f"({len(shot_events)} shots)"
        )
        logger.info(f"xT: home={xt_data['home']} away={xt_data['away']}")

        pitch_control = self._compute_pitch_control(track_data, homography_matrix)
        player_ratings = self._compute_player_ratings(
            players, typed_events, pitch_control, track_data, homography_matrix
        )

        coords = "meters" if homography_matrix else "pixels"
        logger.info(
            f"Analysis complete: {len(players)} players, "
            f"{len(typed_events)} typed events, confidence={confidence:.2%}, "
            f"formations: {home_formation['formation']}/{away_formation['formation']}, "
            f"coords={coords}"
        )

        backward_compat_events = [e.to_dict() if hasattr(e, "to_dict") else e for e in typed_events]

        return MatchAnalysis(
            match_id=match_id,
            duration_seconds=track_data.duration_seconds,
            home_team=home,
            away_team=away,
            players=players,
            events=backward_compat_events,
            pass_network=pass_network,
            confidence_overall=confidence,
            formations={
                "home": home_formation,
                "away": away_formation,
            },
            pressing_intensity=home_ppda.get("ppda") or 0.0,
            xg_total=xg_data,
            xt_total=xt_data,
            typed_events=typed_events,
            pass_type_breakdown=pass_breakdown,
            carry_events=carry_events_list,
            progressive_passes=progressive_passes_list,
            progressive_carries=progressive_carries_list,
            pitch_control=pitch_control,
            player_ratings=player_ratings,
        )

    def _build_typed_pass(self, event: dict, homography_matrix=None) -> PassEvent:
        meta = event.get("metadata", {})
        sx = meta.get("start_x_pct", 0.5)
        sy = meta.get("start_y_pct", 0.5)
        ex = meta.get("end_x_pct", 0.6)
        ey = meta.get("end_y_pct", 0.5)
        dx = (ex - sx) * self.pitch_length
        dy = (ey - sy) * self.pitch_width
        length_m = math.sqrt(dx * dx + dy * dy)
        return PassEvent(
            timestamp=event.get("timestamp", 0),
            team=event.get("team", "unknown"),
            track_id=event.get("from_track_id"),
            to_track_id=event.get("to_track_id"),
            start_x=sx,
            start_y=sy,
            end_x=ex,
            end_y=ey,
            completed=event.get("completed", True),
            length_m=length_m,
            confidence=event.get("confidence", 0.5),
            period=1,
        )

    def _build_typed_shot(self, event: dict, homography_matrix=None) -> ShotEvent:
        meta = event.get("metadata", {})
        return ShotEvent(
            timestamp=event.get("timestamp", 0),
            team=event.get("team", "unknown"),
            track_id=event.get("track_id"),
            on_target=event.get("on_target", False),
            distance_m=meta.get("distance_to_goal_m", 18.0),
            angle_deg=meta.get("angle_to_goal_deg", 30.0),
            xg=meta.get("xg", 0.0),
            confidence=event.get("confidence", 0.5),
            period=1,
        )

    def _detect_carries(self, track_data, typed_events, homography_matrix=None) -> list[CarryEvent]:
        carries: list[CarryEvent] = []
        if not track_data.frames:
            return carries
        fps = max(1, track_data.fps)
        min_carry_frames = int(fps * 0.5)
        min_carry_distance = 2.0

        pass_frames: set[int] = set()
        for ev in typed_events:
            if isinstance(ev, PassEvent):
                idx = int(ev.timestamp * fps)
                for offset in range(-2, 3):
                    pass_frames.add(idx + offset)

        ball_tracker: dict[int, list[tuple[float, float, float, int]]] = {}
        carry_start: dict[int, tuple[int, float, float, float]] = {}

        for frame in track_data.frames:
            fno = frame.frame_number
            if fno in pass_frames:
                continue
            ts = frame.timestamp
            ball_det = None
            for det in frame.detections:
                if det.class_name == "sports ball":
                    ball_det = det
                    break
            if ball_det is None:
                continue
            bx = (ball_det.bbox[0] + ball_det.bbox[2]) / 2.0
            by = (ball_det.bbox[1] + ball_det.bbox[3]) / 2.0
            closest = None
            closest_dist = float("inf")
            for det in frame.detections:
                if det.class_name != "person" or det.track_id is None:
                    continue
                px = (det.bbox[0] + det.bbox[2]) / 2.0
                py = (det.bbox[1] + det.bbox[3]) / 2.0
                d = math.sqrt((bx - px) ** 2 + (by - py) ** 2)
                if d < closest_dist:
                    closest_dist = d
                    closest = det
            if closest is None or closest.track_id is None:
                continue
            tid = closest.track_id
            if tid not in ball_tracker:
                ball_tracker[tid] = [(ts, bx, by, fno)]
            else:
                ball_tracker[tid].append((ts, bx, by, fno))
            if tid not in carry_start:
                carry_start[tid] = (fno, ts, bx, by)
            else:
                cfno, cts, cbx, cby = carry_start[tid]
                elapsed_frames = fno - cfno
                if elapsed_frames >= min_carry_frames:
                    dx = bx - cbx
                    dy = by - cby
                    cd = math.sqrt(dx * dx + dy * dy)
                    if cd >= min_carry_distance:
                        cx, cy = bx, by
                        if homography_matrix is not None:
                            try:
                                cx, cy = homography_matrix.pixel_to_pitch(bx, by)
                            except Exception as e:
                                logger.warning("Failed to convert ball pixel-to-pitch in carry detection: %s", e)
                        scx, scy = cbx, cby
                        if homography_matrix is not None:
                            try:
                                scx, scy = homography_matrix.pixel_to_pitch(cbx, cby)
                            except Exception as e:
                                logger.warning("Failed to convert carry-start pixel-to-pitch: %s", e)
                        team = "unknown"
                        if track_data.player_teams:
                            team = track_data.player_teams.get(tid, "unknown")
                        carries.append(CarryEvent(
                            timestamp=cts,
                            team=team,
                            track_id=tid,
                            start_x=scx,
                            start_y=scy,
                            end_x=cx,
                            end_y=cy,
                            distance_m=cd if homography_matrix else cd * 0.015,
                            is_progressive=False,
                            confidence=0.5,
                        ))
                    carry_start.pop(tid, None)
                    ball_tracker.pop(tid, None)
        return carries

    @staticmethod
    def _pixel_dist_to_meters(sx, sy, ox, oy, homography_matrix) -> float:
        if homography_matrix is not None:
            try:
                sx_m, sy_m = homography_matrix.pixel_to_pitch(sx, sy)
                ox_m, oy_m = homography_matrix.pixel_to_pitch(ox, oy)
                return math.sqrt((ox_m - sx_m) ** 2 + (oy_m - sy_m) ** 2)
            except Exception:
                pass
        return math.sqrt((ox - sx) ** 2 + (oy - sy) ** 2)

    def _infer_pressure_on_events(self, track_data, typed_events, homography_matrix=None) -> None:
        if not track_data.frames or not track_data.player_teams:
            return

        team_to_side = {"home": "left", "away": "right"}

        for event in typed_events:
            ts = event.timestamp
            frame_idx = min(int(ts * track_data.fps), len(track_data.frames) - 1)
            if frame_idx < 0:
                continue
            frame = track_data.frames[frame_idx]

            home_players = []
            away_players = []
            ball_x, ball_y = 0, 0
            has_ball = False
            shooter_pos = None

            for det in frame.detections:
                if det.class_name == "sports ball":
                    bx = (det.bbox[0] + det.bbox[2]) / 2.0
                    by = (det.bbox[1] + det.bbox[3]) / 2.0
                    ball_x, ball_y = bx, by
                    has_ball = True
                elif det.class_name == "person" and det.track_id is not None:
                    px = (det.bbox[0] + det.bbox[2]) / 2.0
                    py = (det.bbox[1] + det.bbox[3]) / 2.0
                    team = track_data.player_teams.get(det.track_id)
                    if team == "home":
                        home_players.append((det.track_id, px, py))
                        if det.track_id == event.track_id:
                            shooter_pos = (px, py)
                    elif team == "away":
                        away_players.append((det.track_id, px, py))
                        if det.track_id == event.track_id:
                            shooter_pos = (px, py)

            if shooter_pos is None and has_ball:
                shooter_pos = (ball_x, ball_y)
            if shooter_pos is None:
                continue

            event_team = event.team
            opponents = away_players if event_team == "home" else home_players
            if not opponents:
                continue

            sx, sy = shooter_pos
            min_dist = float("inf")
            min_angle = 0.0
            count_within_5m = 0

            for tid, ox, oy in opponents:
                dx = ox - sx
                dy = oy - sy
                dist_pitch = self._pixel_dist_to_meters(sx, sy, ox, oy, homography_matrix)
                if dx * dx + dy * dy < min_dist * min_dist:
                    min_dist = math.sqrt(dx * dx + dy * dy)
                    min_angle = math.degrees(math.atan2(abs(dy), abs(dx)))
                if dist_pitch < 5.0:
                    count_within_5m += 1

            min_dist_pitch = min(
                (
                    self._pixel_dist_to_meters(sx, sy, ox, oy, homography_matrix)
                    for _, ox, oy in opponents
                ),
                default=float("inf"),
            )

            event.pressure = PressureContext(
                nearest_defender_distance=min_dist_pitch,
                nearest_defender_angle=min_angle,
                defenders_within_5m=count_within_5m,
                is_pressed=min_dist_pitch < 2.0,
            )

            if isinstance(event, ShotEvent):
                event.was_pressed = min_dist_pitch < 2.0

    def _classify_pass_types(self, typed_events, homography_matrix=None) -> None:
        for event in typed_events:
            if not isinstance(event, PassEvent):
                continue
            sx, sy = (event.start_x or 0.5), (event.start_y or 0.5)
            ex, ey = (event.end_x or 0.6), (event.end_y or 0.5)

            x_gain = ex - sx
            y_gain = abs(ey - sy)

            if event.length_m > 30.0:
                event.pass_type = PassType.LONG_BALL
            if x_gain < 0:
                event.pass_type = PassType.BACK_PASS
                continue
            if y_gain > 0.5:
                event.pass_type = PassType.SWITCH
                continue
            if ey < 0.2 or ey > 0.8:
                if ex > 0.7:
                    event.pass_type = PassType.CROSS
                    event.is_cross = True
                    continue
            if x_gain > 0.15 and event.length_m > 15.0:
                event.pass_type = PassType.THROUGH_BALL
                event.is_through_ball = True
                continue
            if event.length_m < 5.0:
                event.pass_type = PassType.ONE_TOUCH
                continue
            event.pass_type = PassType.STANDARD

    def _find_progressive_passes(self, typed_events, homography_matrix=None) -> list[dict]:
        progressive = []
        for event in typed_events:
            if not isinstance(event, PassEvent):
                continue
            if not event.completed:
                continue
            sx, ex = (event.start_x or 0.5), (event.end_x or 0.6)
            x_gain = (ex - sx) * self.pitch_length
            is_progressive = x_gain > 5.0 and event.length_m > 10.0
            event.is_progressive = is_progressive
            if is_progressive:
                progressive.append(event.to_dict())
        return progressive

    def _compute_pass_type_breakdown(self, typed_events) -> dict:
        from collections import Counter

        counts: Counter[str] = Counter()
        progressive_count = 0
        key_pass_count = 0
        assist_count = 0
        total = 0

        for event in typed_events:
            if not isinstance(event, PassEvent) or not event.completed:
                continue
            total += 1
            counts[event.pass_type.value] += 1
            if event.is_progressive:
                progressive_count += 1
            if event.is_key_pass:
                key_pass_count += 1
            if event.is_assist:
                assist_count += 1

        return {
            "total": total,
            "by_type": dict(counts),
            "progressive": progressive_count,
            "key_passes": key_pass_count,
            "assists": assist_count,
        }

    def _compute_pitch_control(self, track_data, homography_matrix=None) -> MatchPitchControl | None:
        if not track_data.frames:
            return None

        frame_data = []
        has_homography = homography_matrix is not None
        use_player_teams = bool(track_data.player_teams)

        for frame in track_data.frames:
            home_pos = []
            away_pos = []
            ball_pos = None

            for det in frame.detections:
                cx = (det.bbox[0] + det.bbox[2]) / 2.0
                cy = (det.bbox[1] + det.bbox[3]) / 2.0

                if det.class_name == "sports ball":
                    ball_pos = (cx, cy)
                    if has_homography:
                        try:
                            ball_pos = homography_matrix.pixel_to_pitch(cx, cy)
                        except Exception as e:
                            logger.warning("Failed to convert ball pixel-to-pitch in frame data: %s", e)
                elif det.class_name == "person" and det.track_id is not None:
                    if has_homography:
                        try:
                            cx, cy = homography_matrix.pixel_to_pitch(cx, cy)
                        except Exception as e:
                            logger.warning("Failed to convert player pixel-to-pitch (track_id=%s): %s", det.track_id, e)
                    if use_player_teams:
                        team = track_data.player_teams.get(det.track_id)
                        if team == "home":
                            home_pos.append((cx, cy))
                        elif team == "away":
                            away_pos.append((cx, cy))
                    else:
                        if det.track_id % 2 == 0:
                            home_pos.append((cx, cy))
                        else:
                            away_pos.append((cx, cy))

            frame_data.append({
                "timestamp": frame.timestamp,
                "home_positions": home_pos,
                "away_positions": away_pos,
                "ball_pos": ball_pos,
            })

        pc = VoronoiPitchControl()
        return pc.compute_match_control(frame_data)

    def _assign_teams_by_pitch_side(self, track_data, homography_matrix) -> None:
        x_per_team: dict[str, list[float]] = {"home": [], "away": []}
        for tid, entry in track_data.track_registry.items():
            team = track_data.player_teams.get(tid)
            px = entry.get("first_pixel_x")
            if team not in ("home", "away") or px is None:
                continue
            try:
                pitch_x, _ = homography_matrix.pixel_to_pitch(px, 0)
                x_per_team[team].append(pitch_x)
            except Exception as e:
                logger.warning("Failed to convert pixel x for team assignment (track_id=%s): %s", tid, e)
                continue

        if len(x_per_team["home"]) < 3 or len(x_per_team["away"]) < 3:
            return

        home_med = statistics.median(x_per_team["home"])
        away_med = statistics.median(x_per_team["away"])

        if home_med > away_med:
            track_data.swap_teams()
            logger.info(
                f"Pitch-side heuristic: home players at x={home_med:.0f}m (right), "
                f"away at x={away_med:.0f}m (left) -> swapped teams"
            )
        else:
            logger.info(
                f"Pitch-side heuristic: home at x={home_med:.0f}m (left), "
                f"away at x={away_med:.0f}m (right) -> already correct"
            )

    def _compute_player_stats_kalman(self, track_data, homography_matrix, max_frame_delta_m: float) -> dict[int, PlayerStats]:
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
            players[tid].positions = [(ts, x, y) for ts, x, y in smoothed]

        for tid, player in players.items():
            if track_data.duration_seconds > 0:
                player.avg_speed_kmh = (
                    player.distance_covered_m / track_data.duration_seconds * 3.6
                )

        return players

    def _detect_events(self, track_data, homography_matrix=None) -> list[dict]:
        events: list[dict] = []
        prev_possession: int | None = None
        ball_track_id: int | None = None
        frames_since_shot: int = 999

        player_proximity_threshold = 60
        shot_speed_threshold_pps = 600
        shot_speed_threshold_mps = 8.0
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
                except Exception as e:
                    logger.warning("Failed to convert ball pixel-to-pitch in shot detection: %s", e)

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

                events.append({
                    "type": "pass",
                    "timestamp": frame.timestamp,
                    "from_track_id": prev_possession,
                    "to_track_id": closest_player.track_id,
                    "completed": True,
                    "team": team,
                    "confidence": min(1.0, 1.0 - closest_dist / 200),
                    "metadata": pass_metadata,
                })

            prev_possession = closest_player.track_id

        return events

    def _compute_team_stats(self, players, events, track_data, homography_matrix=None) -> dict[str, TeamStats]:
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

    def _compute_possession(self, track_data, homography_matrix=None) -> dict[str, float]:
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

    def _compute_confidence(self, track_data, events) -> float:
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
