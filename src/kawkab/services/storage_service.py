"""Storage service - SQLite database for matches, players, events, corrections.

Privacy-first: all data stays on the coach's machine.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from kawkab.core.logging import get_logger
from kawkab.core.paths import get_paths

logger = get_logger(__name__)


class StorageService:
    """SQLite-based storage for Kawkab AI data."""

    def __init__(self) -> None:
        self._db_path = get_paths().database
        self._conn: sqlite3.Connection | None = None
        logger.info(f"StorageService: database={self._db_path}")

    async def initialize(self) -> None:
        """Create database and tables if they don't exist."""
        from kawkab.core.migration_manager import MigrationManager
        from kawkab.core.paths import get_paths

        migrations_dir = get_paths().migrations
        migrations_dir.mkdir(parents=True, exist_ok=True)

        # Run migrations before opening connection
        mgr = MigrationManager(self._db_path, migrations_dir)
        mgr.migrate()

        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        logger.info("StorageService initialized with migrations")

    def _create_tables(self) -> None:
        """DEPRECATED: Migrations now handle schema creation."""
        logger.debug("_create_tables is deprecated; migrations handle schema")

    async def save_match(
        self,
        name: str,
        video_path: str,
        home_team: str | None = None,
        away_team: str | None = None,
    ) -> int:
        """Save a new match and return its ID."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO matches (name, video_path, home_team, away_team)
            VALUES (?, ?, ?, ?)
            """,
            (name, video_path, home_team, away_team),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def update_match_analysis(
        self,
        match_id: int,
        duration: float,
        fps: float,
        total_frames: int,
    ) -> None:
        """Update match with analysis metadata."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE matches
            SET duration_seconds = ?, fps = ?, total_frames = ?,
                analyzed_at = ?
            WHERE id = ?
            """,
            (duration, fps, total_frames, datetime.now(), match_id),
        )
        self._conn.commit()

    async def save_player(self, match_id: int, player_data: dict) -> int:
        """Save a player and return its ID."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO players (
                match_id, track_id, jersey_number, name, team, position,
                distance_covered_m, max_speed_kmh, avg_speed_kmh,
                passes_attempted, passes_completed, shots, tackles
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                player_data["track_id"],
                player_data.get("jersey_number"),
                player_data.get("name"),
                player_data.get("team"),
                player_data.get("position"),
                player_data.get("distance_covered_m", 0),
                player_data.get("max_speed_kmh", 0),
                player_data.get("avg_speed_kmh", 0),
                player_data.get("passes_attempted", 0),
                player_data.get("passes_completed", 0),
                player_data.get("shots", 0),
                player_data.get("tackles", 0),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def save_event(self, match_id: int, event: dict) -> int:
        """Save an event and return its ID."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO events (
                match_id, event_type, timestamp, from_track_id, to_track_id,
                team, completed, confidence, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                event["type"],
                event["timestamp"],
                event.get("from_track_id"),
                event.get("to_track_id"),
                event.get("team"),
                event.get("completed", False),
                event.get("confidence", 0.0),
                json.dumps(event.get("metadata", {})),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def save_advanced_metrics(
        self,
        match_id: int,
        metric_name: str,
        metric_value: float,
        metric_category: str = "",
        player_id: int | None = None,
        pitch_zone: str = "",
        timestamp: float | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Save an advanced metric and return its ID."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO advanced_metrics (
                match_id, player_id, metric_name, metric_value,
                metric_category, pitch_zone, timestamp, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                player_id,
                metric_name,
                metric_value,
                metric_category,
                pitch_zone,
                timestamp,
                json.dumps(metadata or {}),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def save_correction(
        self,
        event_id: int,
        correction_type: str,
        original_value: Any,
        corrected_value: Any,
    ) -> int:
        """Save a user correction for an event."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_corrections (
                event_id, correction_type, original_value, corrected_value
            ) VALUES (?, ?, ?, ?)
            """,
            (
                event_id,
                correction_type,
                json.dumps(original_value),
                json.dumps(corrected_value),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def save_report(
        self, match_id: int, language: str, report_text: str, llm_provider: str
    ) -> int:
        """Save a generated report."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO reports (match_id, language, report_text, llm_provider)
            VALUES (?, ?, ?, ?)
            """,
            (match_id, language, report_text, llm_provider),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def get_reports(self, match_id: int, language: str) -> list[dict]:
        """Get saved reports for a match."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM reports WHERE match_id = ? AND language = ? ORDER BY created_at DESC",
            (match_id, language),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def update_match_teams(
        self, match_id: int, home_team: str, away_team: str
    ) -> None:
        """Update home/away team names for a match."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE matches SET home_team = ?, away_team = ? WHERE id = ?",
            (home_team, away_team, match_id),
        )
        self._conn.commit()

    async def update_match_football_data(
        self,
        match_id: int,
        api_match_id: int | None = None,
        competition_code: str | None = None,
        football_data_home_team_id: int | None = None,
        football_data_away_team_id: int | None = None,
    ) -> None:
        """Update football-data.org reference fields for a match."""
        assert self._conn is not None
        sets = []
        vals = []
        if api_match_id is not None:
            sets.append("api_match_id = ?")
            vals.append(api_match_id)
        if competition_code is not None:
            sets.append("competition_code = ?")
            vals.append(competition_code)
        if football_data_home_team_id is not None:
            sets.append("football_data_home_team_id = ?")
            vals.append(football_data_home_team_id)
        if football_data_away_team_id is not None:
            sets.append("football_data_away_team_id = ?")
            vals.append(football_data_away_team_id)
        if not sets:
            return
        vals.append(match_id)
        cursor = self._conn.cursor()
        cursor.execute(
            f"UPDATE matches SET {', '.join(sets)} WHERE id = ?", vals
        )
        self._conn.commit()

    async def update_match_apifootball(
        self,
        match_id: int,
        apifb_home_team_id: int | None = None,
        apifb_away_team_id: int | None = None,
        apifb_fixture_id: int | None = None,
        apifb_league_id: int | None = None,
        apifb_season: int | None = None,
    ) -> None:
        """Update API-Football reference fields for a match."""
        assert self._conn is not None
        sets = []
        vals = []
        if apifb_home_team_id is not None:
            sets.append("apifb_home_team_id = ?")
            vals.append(apifb_home_team_id)
        if apifb_away_team_id is not None:
            sets.append("apifb_away_team_id = ?")
            vals.append(apifb_away_team_id)
        if apifb_fixture_id is not None:
            sets.append("apifb_fixture_id = ?")
            vals.append(apifb_fixture_id)
        if apifb_league_id is not None:
            sets.append("apifb_league_id = ?")
            vals.append(apifb_league_id)
        if apifb_season is not None:
            sets.append("apifb_season = ?")
            vals.append(apifb_season)
        if not sets:
            return
        vals.append(match_id)
        cursor = self._conn.cursor()
        cursor.execute(
            f"UPDATE matches SET {', '.join(sets)} WHERE id = ?", vals
        )
        self._conn.commit()

    async def update_match_bzzoiro(
        self,
        match_id: int,
        bzzoiro_home_team_id: int | None = None,
        bzzoiro_away_team_id: int | None = None,
        bzzoiro_event_id: int | None = None,
        bzzoiro_league_id: int | None = None,
        bzzoiro_competition_code: str | None = None,
        prediction_data: str | None = None,
    ) -> None:
        """Update Bzzoiro reference fields for a match."""
        assert self._conn is not None
        sets = []
        vals = []
        if bzzoiro_home_team_id is not None:
            sets.append("bzzoiro_home_team_id = ?")
            vals.append(bzzoiro_home_team_id)
        if bzzoiro_away_team_id is not None:
            sets.append("bzzoiro_away_team_id = ?")
            vals.append(bzzoiro_away_team_id)
        if bzzoiro_event_id is not None:
            sets.append("bzzoiro_event_id = ?")
            vals.append(bzzoiro_event_id)
        if bzzoiro_league_id is not None:
            sets.append("bzzoiro_league_id = ?")
            vals.append(bzzoiro_league_id)
        if bzzoiro_competition_code is not None:
            sets.append("bzzoiro_competition_code = ?")
            vals.append(bzzoiro_competition_code)
        if prediction_data is not None:
            sets.append("prediction_data = ?")
            vals.append(prediction_data)
        if not sets:
            return
        vals.append(match_id)
        cursor = self._conn.cursor()
        cursor.execute(
            f"UPDATE matches SET {', '.join(sets)} WHERE id = ?", vals
        )
        self._conn.commit()

    async def get_all_matches(self) -> list[dict]:
        """Get all matches from the database."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, name, video_path, home_team, away_team, match_date,
                   duration_seconds, analyzed_at, created_at,
                   api_match_id, competition_code,
                   bzzoiro_home_team_id, bzzoiro_away_team_id, bzzoiro_event_id, bzzoiro_league_id,
                   apifb_home_team_id, apifb_away_team_id, apifb_fixture_id, apifb_league_id
            FROM matches
            ORDER BY created_at DESC
            """
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_match(self, match_id: int) -> dict | None:
        """Get a single match by ID."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    async def get_match_events(self, match_id: int) -> list[dict]:
        """Get all events for a match."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM events WHERE match_id = ? ORDER BY timestamp",
            (match_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def update_event(self, event_id: int, updates: dict) -> bool:
        """Update an event's fields. Returns True if row updated."""
        assert self._conn is not None
        allowed = {"event_type", "team", "from_track_id", "to_track_id",
                    "completed", "confidence", "metadata"}
        sets = []
        vals = []
        for key, val in updates.items():
            if key in allowed:
                col = key
                if key == "metadata" and isinstance(val, dict):
                    val = json.dumps(val)
                sets.append(f"{col} = ?")
                vals.append(val)
        if not sets:
            return False
        sets.append("user_corrected = 1")
        vals.append(event_id)
        cursor = self._conn.cursor()
        cursor.execute(
            f"UPDATE events SET {', '.join(sets)} WHERE id = ?", vals
        )
        self._conn.commit()
        return cursor.rowcount > 0

    async def delete_event(self, event_id: int) -> bool:
        """Delete an event by ID. Returns True if row deleted."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    async def save_benchmark(self, result: "BenchmarkResult") -> int:
        """Save a benchmark result to the database."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO benchmark_results (
                match_id, video_path, video_duration_seconds, total_frames,
                total_time_seconds, realtime_ratio, fps_effective,
                stage_enhancement_seconds, stage_detection_seconds,
                stage_tracking_seconds, stage_analysis_seconds,
                stage_advanced_metrics_seconds, stage_save_seconds,
                peak_memory_mb, peak_gpu_memory_mb, gpu_utilization_pct,
                gpu_name, cpu_name, ram_gb, model_size, frame_skip
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.match_id,
                result.video_path,
                result.video_duration_seconds,
                result.total_frames,
                result.total_time_seconds,
                result.realtime_ratio,
                result.fps_effective,
                result.stage_enhancement_seconds,
                result.stage_detection_seconds,
                result.stage_tracking_seconds,
                result.stage_analysis_seconds,
                result.stage_advanced_metrics_seconds,
                result.stage_save_seconds,
                result.peak_memory_mb,
                result.peak_gpu_memory_mb,
                result.gpu_utilization_pct,
                result.gpu_name,
                result.cpu_name,
                result.ram_gb,
                result.model_size,
                result.frame_skip,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def get_recent_benchmarks(self, limit: int = 10) -> list[dict]:
        """Get recent benchmark results."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT * FROM benchmark_results
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def save_validation_result(self, report: "ValidationReport") -> list[int]:
        """Save a validation report to the database."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        ids = []
        for result in report.results:
            cursor.execute(
                """
                INSERT INTO validation_results (
                    match_id, ground_truth_source, overall_accuracy,
                    category, metric_name, computed_value, ground_truth_value,
                    absolute_error, relative_error_pct, accuracy_score, sample_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.match_id,
                    report.ground_truth_source,
                    report.overall_accuracy,
                    result.category,
                    result.metric_name,
                    result.computed_value,
                    result.ground_truth_value,
                    result.absolute_error,
                    result.relative_error_pct,
                    result.accuracy_score,
                    result.sample_count,
                ),
            )
            ids.append(cursor.lastrowid or 0)
        self._conn.commit()
        return ids

    async def get_validation_results(self, match_id: int) -> list[dict]:
        """Get validation results for a match."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM validation_results WHERE match_id = ? ORDER BY created_at DESC",
            (match_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def save_feedback(self, feedback: dict) -> int:
        """Save coach feedback to the database."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO coach_feedback (
                coach_id, match_id, overall_rating, tracking_rating,
                events_rating, report_rating, ui_rating, comments, issues, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback["coach_id"],
                feedback["match_id"],
                feedback["overall_rating"],
                feedback.get("tracking_rating"),
                feedback.get("events_rating"),
                feedback.get("report_rating"),
                feedback.get("ui_rating"),
                feedback.get("comments", ""),
                json.dumps(feedback.get("issues", [])),
                feedback.get("created_at", ""),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def get_all_feedback(self) -> list[dict]:
        """Get all coach feedback entries."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM coach_feedback ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    async def save_issue(self, issue: dict) -> int:
        """Save an issue report to the database."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO issue_reports (
                category, severity, description, match_id, screenshot_path, logs, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                issue["category"],
                issue["severity"],
                issue["description"],
                issue.get("match_id"),
                issue.get("screenshot_path"),
                issue.get("logs", ""),
                issue.get("created_at", ""),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def get_all_issues(self) -> list[dict]:
        """Get all issue reports."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM issue_reports ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    async def save_usage_session(self, session: dict) -> int:
        """Save an anonymized usage session."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO usage_sessions (
                session_id, features_used, duration_seconds, match_count,
                gpu_tier, model_size, error_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["session_id"],
                json.dumps(session["features_used"]),
                session["duration_seconds"],
                session["match_count"],
                session["gpu_tier"],
                session["model_size"],
                session.get("error_count", 0),
                session.get("created_at", ""),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def save_clip(self, clip: dict) -> int:
        """Save a video clip to the database."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO video_clips (
                match_id, event_type, start_seconds, end_seconds, duration_seconds,
                source_video_path, output_path, thumbnail_path, player_id, description, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clip["match_id"],
                clip["event_type"],
                clip["start_seconds"],
                clip["end_seconds"],
                clip["duration_seconds"],
                clip["source_video_path"],
                clip["output_path"],
                clip.get("thumbnail_path"),
                clip.get("player_id"),
                clip.get("description", ""),
                clip.get("created_at", ""),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def get_clips_for_match(self, match_id: int) -> list[dict]:
        """Get all clips for a match."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM video_clips WHERE match_id = ? ORDER BY created_at DESC",
            (match_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def save_playlist(self, playlist: dict) -> int:
        """Save a clip playlist to the database."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO clip_playlists (
                name, description, clip_ids, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                playlist["name"],
                playlist.get("description", ""),
                json.dumps(playlist["clip_ids"]),
                playlist.get("created_at", ""),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def get_playlists(self) -> list[dict]:
        """Get all playlists."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM clip_playlists ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    async def get_all_player_profiles(self) -> list[dict]:
        """Get all player profiles from the DB."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM player_profiles WHERE is_active = 1")
        return [dict(row) for row in cursor.fetchall()]

    async def update_player_profile_face(
        self, profile_id: int, face_embedding_json: str, face_confidence: float
    ) -> None:
        """Store face embedding and confidence for a player profile."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE player_profiles
            SET face_embedding = ?, face_confidence = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (face_embedding_json, face_confidence, profile_id),
        )
        self._conn.commit()

    async def save_player_profile(self, profile: dict) -> int:
        """Create a new player profile."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO player_profiles (
                global_id, display_name, jersey_number, preferred_position,
                team, is_active, face_embedding, face_confidence
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                profile.get("global_id", ""),
                profile.get("display_name", ""),
                profile.get("jersey_number"),
                profile.get("preferred_position"),
                profile.get("team", "home"),
                profile.get("face_embedding"),
                profile.get("face_confidence", 0.0),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("StorageService closed")
