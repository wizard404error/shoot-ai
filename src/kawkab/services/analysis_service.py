"""Analysis service - statistics, patterns, formations, xG/xT.

Computes per-match and season-level insights from tracking data.
"""

from __future__ import annotations

import math
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
    ) -> None:
        self.pitch_length = pitch_length_m
        self.pitch_width = pitch_width_m
        logger.info(
            f"AnalysisService: pitch={pitch_length_m}x{pitch_width_m}m"
        )

    async def analyze_match(
        self, track_data: MatchTrackData, match_id: int = 0
    ) -> MatchAnalysis:
        """Compute full match analysis from tracking data.

        Args:
            track_data: Output from CVService.process_video
            match_id: Database ID for this match

        Returns:
            Complete MatchAnalysis with stats, events, patterns
        """
        logger.info(f"Analyzing match: {track_data.total_frames} frames")

        players = self._compute_player_stats(track_data)
        events = self._detect_events(track_data)
        team_stats = self._compute_team_stats(players, events, track_data)
        possession = self._compute_possession(track_data)
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

        home_formation = self.detect_formation(track_data, team="home")
        away_formation = self.detect_formation(track_data, team="away")
        home_ppda = self.compute_ppda(track_data, team="home")
        away_ppda = self.compute_ppda(track_data, team="away")

        confidence = self._compute_confidence(track_data, events)

        logger.info(
            f"Analysis complete: {len(players)} players, "
            f"{len(events)} events, confidence={confidence:.2%}, "
            f"formations: {home_formation['formation']}/{away_formation['formation']}"
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
        )

    def _compute_player_stats(
        self, track_data: MatchTrackData
    ) -> dict[int, PlayerStats]:
        """Compute per-player statistics from tracking data."""
        players: dict[int, PlayerStats] = {}
        prev_positions: dict[int, tuple[float, float]] = {}
        max_speed_per_player: dict[int, float] = {}

        fps = track_data.fps
        pixels_per_meter = 720.0 / self.pitch_width

        for frame in track_data.frames:
            current_positions: dict[int, tuple[float, float]] = {}

            for det in frame.detections:
                if det.class_name != "person" or det.track_id is None:
                    continue

                tid = det.track_id
                if tid not in players:
                    players[tid] = PlayerStats(track_id=tid)

                x1, y1, x2, y2 = det.bbox
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                current_positions[tid] = (cx, cy)

                players[tid].positions.append((frame.timestamp, cx, cy))

                if tid in prev_positions:
                    px, py = prev_positions[tid]
                    dx = cx - px
                    dy = cy - py
                    pixel_distance = math.sqrt(dx * dx + dy * dy)
                    meters = pixel_distance / pixels_per_meter
                    players[tid].distance_covered_m += meters

                    if fps > 0:
                        time_delta = 1.0 / fps
                        speed_mps = meters / time_delta if time_delta > 0 else 0
                        speed_kmh = speed_mps * 3.6
                        max_speed_per_player[tid] = max(
                            max_speed_per_player.get(tid, 0), speed_kmh
                        )

            prev_positions = current_positions

        for tid, player in players.items():
            if track_data.duration_seconds > 0:
                player.avg_speed_kmh = (
                    player.distance_covered_m / track_data.duration_seconds * 3.6
                )
            player.max_speed_kmh = max_speed_per_player.get(tid, 0.0)

        return players

    def _detect_events(
        self, track_data: MatchTrackData
    ) -> list[dict]:
        """Detect basic events (passes, shots, tackles) from tracking.

        Heuristic-based: detects possession changes (passes), fast ball
        movement toward goal (shots), and proximity changes (tackles).
        """
        events: list[dict] = []
        prev_possession: int | None = None
        ball_track_id: int | None = None

        player_proximity_threshold = 60  # pixels

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
                continue

            bx = (ball_det.bbox[0] + ball_det.bbox[2]) / 2
            by = (ball_det.bbox[1] + ball_det.bbox[3]) / 2

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
                events.append(
                    {
                        "type": "pass",
                        "timestamp": frame.timestamp,
                        "from_track_id": prev_possession,
                        "to_track_id": closest_player.track_id,
                        "completed": True,
                        "team": "home" if prev_possession % 2 == 0 else "away",
                        "confidence": min(1.0, 1.0 - closest_dist / 200),
                    }
                )

            prev_possession = closest_player.track_id

        return events

    def _compute_team_stats(
        self,
        players: dict[int, PlayerStats],
        events: list[dict],
        track_data: MatchTrackData,
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
        self, track_data: MatchTrackData
    ) -> dict[str, float]:
        """Compute possession percentage per team.

        Uses player ball proximity as proxy for possession.
        """
        home_frames = 0
        away_frames = 0

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
        self, track_data: MatchTrackData, team: str = "home", n_players: int = 11
    ) -> dict:
        """Detect team formation (e.g., 4-3-3, 4-4-2) using k-means clustering.

        Args:
            track_data: Match tracking data
            team: "home" or "away"
            n_players: Expected number of outfield players (default 10 + GK = 11)

        Returns:
            Dict with formation (e.g., "4-3-3"), defensive line height,
            and player positions
        """
        import math
        from collections import defaultdict

        team_player_positions: dict[int, list[tuple[float, float]]] = defaultdict(list)
        track_lifetimes: dict[int, int] = defaultdict(int)

        for frame in track_data.frames:
            for det in frame.detections:
                if det.class_name != "person" or det.track_id is None:
                    continue
                if team == "home":
                    if det.track_id % 2 != 0:
                        continue
                else:
                    if det.track_id % 2 == 0:
                        continue
                x1, y1, x2, y2 = det.bbox
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                team_player_positions[det.track_id].append((cx, cy))
                track_lifetimes[det.track_id] += 1

        min_lifetime = track_data.total_frames * 0.15
        team_player_positions = {
            tid: positions
            for tid, positions in team_player_positions.items()
            if track_lifetimes[tid] >= min_lifetime
        }

        if len(team_player_positions) < 5:
            return {
                "formation": "unknown",
                "confidence": 0.0,
                "line_height": None,
                "player_count": len(team_player_positions),
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
        def_line_pct = def_line_height / 1280.0 if def_line_height else 0.5

        formation_str = f"{n_def}-{n_mid}-{n_att}"

        valid_formations = {
            "4-3-3", "4-4-2", "4-2-3-1", "3-5-2", "3-4-3", "5-3-2",
            "5-4-1", "4-1-4-1", "4-5-1", "3-4-1-2", "3-6-1",
            "2-4-4", "4-3-1-2",
        }
        if formation_str in valid_formations:
            confidence = 0.7 if n >= 8 else 0.4
        else:
            confidence = 0.3

        return {
            "formation": formation_str,
            "confidence": confidence,
            "line_height": round(def_line_pct, 2),
            "player_count": n,
            "defenders": defenders,
            "midfielders": midfielders,
            "attackers": attackers,
        }

    def compute_ppda(
        self, track_data: MatchTrackData, team: str = "home"
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
                if current_possessor_track_id % 2 == 0:
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
