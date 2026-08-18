"""Storage service - SQLite (default) or PostgreSQL database.

Privacy-first: all data stays on the coach's machine by default (SQLite).
Set KAWKAB_DB_URL env var for PostgreSQL (club/cloud deployment).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kawkab.core.logging import get_logger
from kawkab.core.paths import get_paths

if TYPE_CHECKING:
    from kawkab.services.benchmark_service import BenchmarkResult
    from kawkab.services.validation_service import ValidationReport

logger = get_logger(__name__)


class StorageService:
    """SQLite-based storage for Kawkab AI data (or PostgreSQL via KAWKAB_DB_URL)."""

    _COLUMN_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    @staticmethod
    def _sanitize_column_name(name: str) -> str | None:
        if StorageService._COLUMN_NAME_RE.match(name):
            return name
        logger.warning(f"Skipping invalid column name: {name}")
        return None

    def __init__(self, dsn: str | None = None) -> None:
        self._use_postgres: bool = False
        self._pg: Any = None
        self._conn: sqlite3.Connection | None = None
        self._db_path: Path | None = None

        actual_dsn = dsn or os.environ.get("KAWKAB_DB_URL")
        if actual_dsn:
            from kawkab.services.postgres_storage import PostgresStorageAdapter
            self._pg = PostgresStorageAdapter(actual_dsn)
            self._use_postgres = True
            logger.info("StorageService: PostgreSQL mode enabled via KAWKAB_DB_URL")
        else:
            self._db_path = get_paths().database
            logger.info(f"StorageService: SQLite mode, database={self._db_path}")

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("_"):
            return super().__getattribute__(name)
        try:
            pg = super().__getattribute__("_pg")
            if pg is not None and hasattr(pg, name):
                return getattr(pg, name)
        except AttributeError:
            pass
        return super().__getattribute__(name)

    async def initialize(self) -> None:
        if self._use_postgres:
            return  # PostgresStorageAdapter handles init via _pg delegation
        from kawkab.core.migration_manager import MigrationManager
        from kawkab.core.paths import get_paths

        if self._conn is not None:
            logger.warning("StorageService.initialize called with existing connection - closing first")
            self._conn.close()
            self._conn = None

        migrations_dir = get_paths().migrations
        migrations_dir.mkdir(parents=True, exist_ok=True)

        self.auto_backup()

        mgr = MigrationManager(self._db_path, migrations_dir)
        mgr.migrate()

        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        logger.info("StorageService initialized with migrations (WAL mode + FK enforced)")

    def _create_tables(self) -> None:
        """DEPRECATED: Migrations now handle schema creation."""
        logger.debug("_create_tables is deprecated; migrations handle schema")

    async def ensure_team(self, name: str) -> int:
        """Get-or-create a team by name, returning its ID."""
        if self._conn is None:
            return 0
        cursor = self._conn.cursor()
        cursor.execute("SELECT id FROM teams WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row["id"]
        cursor.execute("INSERT INTO teams (name, short_name) VALUES (?, ?)", (name, name[:3].upper()))
        self._conn.commit()
        return cursor.lastrowid or 0

    async def save_match(
        self,
        name: str,
        video_path: str,
        home_team: str | None = None,
        away_team: str | None = None,
    ) -> int:
        """Save a new match and return its ID. Creates/looks up teams."""
        if self._conn is None:
            return 0
        home_team_id = await self.ensure_team(home_team) if home_team else None
        away_team_id = await self.ensure_team(away_team) if away_team else None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO matches (name, video_path, home_team, away_team, home_team_id, away_team_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, video_path, home_team, away_team, home_team_id, away_team_id),
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
        if self._conn is None:
            return
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
        if self._conn is None:
            return 0
        if player_data.get("track_id") is None:
            return 0
        try:
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
                    player_data.get("track_id", 0),
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
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"save_player failed: {e}")
            return 0

    async def save_event(self, match_id: int, event: dict) -> int:
        """Save an event and return its ID."""
        if self._conn is None:
            return 0
        if event.get("type") is None or event.get("timestamp") is None:
            return 0
        try:
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
                    event.get("type", "unknown"),
                    event.get("timestamp", 0.0),
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
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"save_event failed: {e}")
            return 0

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
        if self._conn is None:
            return 0
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
        if self._conn is None:
            return 0
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
        if self._conn is None:
            return 0
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

    async def get_reports(self, match_id: int, language: str, limit: int = 20, offset: int = 0) -> list[dict]:
        """Get saved reports for a match."""
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, match_id, report_text, language, llm_provider, created_at FROM reports WHERE match_id = ? AND language = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (match_id, language, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def update_match_teams(
        self, match_id: int, home_team: str, away_team: str
    ) -> None:
        """Update home/away team names for a match."""
        if self._conn is None:
            return
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
        if self._conn is None:
            return
        sets = []
        vals = []
        if api_match_id is not None and StorageService._sanitize_column_name("api_match_id"):
            sets.append("api_match_id = ?")
            vals.append(api_match_id)
        if competition_code is not None and StorageService._sanitize_column_name("competition_code"):
            sets.append("competition_code = ?")
            vals.append(competition_code)
        if football_data_home_team_id is not None and StorageService._sanitize_column_name("football_data_home_team_id"):
            sets.append("football_data_home_team_id = ?")
            vals.append(football_data_home_team_id)
        if football_data_away_team_id is not None and StorageService._sanitize_column_name("football_data_away_team_id"):
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
        if self._conn is None:
            return
        sets = []
        vals = []
        if apifb_home_team_id is not None and StorageService._sanitize_column_name("apifb_home_team_id"):
            sets.append("apifb_home_team_id = ?")
            vals.append(apifb_home_team_id)
        if apifb_away_team_id is not None and StorageService._sanitize_column_name("apifb_away_team_id"):
            sets.append("apifb_away_team_id = ?")
            vals.append(apifb_away_team_id)
        if apifb_fixture_id is not None and StorageService._sanitize_column_name("apifb_fixture_id"):
            sets.append("apifb_fixture_id = ?")
            vals.append(apifb_fixture_id)
        if apifb_league_id is not None and StorageService._sanitize_column_name("apifb_league_id"):
            sets.append("apifb_league_id = ?")
            vals.append(apifb_league_id)
        if apifb_season is not None and StorageService._sanitize_column_name("apifb_season"):
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
        if self._conn is None:
            return
        sets = []
        vals = []
        if bzzoiro_home_team_id is not None and StorageService._sanitize_column_name("bzzoiro_home_team_id"):
            sets.append("bzzoiro_home_team_id = ?")
            vals.append(bzzoiro_home_team_id)
        if bzzoiro_away_team_id is not None and StorageService._sanitize_column_name("bzzoiro_away_team_id"):
            sets.append("bzzoiro_away_team_id = ?")
            vals.append(bzzoiro_away_team_id)
        if bzzoiro_event_id is not None and StorageService._sanitize_column_name("bzzoiro_event_id"):
            sets.append("bzzoiro_event_id = ?")
            vals.append(bzzoiro_event_id)
        if bzzoiro_league_id is not None and StorageService._sanitize_column_name("bzzoiro_league_id"):
            sets.append("bzzoiro_league_id = ?")
            vals.append(bzzoiro_league_id)
        if bzzoiro_competition_code is not None and StorageService._sanitize_column_name("bzzoiro_competition_code"):
            sets.append("bzzoiro_competition_code = ?")
            vals.append(bzzoiro_competition_code)
        if prediction_data is not None and StorageService._sanitize_column_name("prediction_data"):
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
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, name, video_path, home_team, away_team, match_date,
                   duration_seconds, analyzed_at, created_at,
                   api_match_id, competition_code,
                   bzzoiro_home_team_id, bzzoiro_away_team_id, bzzoiro_event_id, bzzoiro_league_id,
                   apifb_home_team_id, apifb_away_team_id, apifb_fixture_id, apifb_league_id
            FROM matches
            WHERE (is_deleted IS NULL OR is_deleted=0)
            ORDER BY created_at DESC
            """
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_match(self, match_id: int) -> dict | None:
        """Get a single match by ID."""
        if self._conn is None:
            return None
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, name, video_path, duration_seconds, fps, total_frames, home_team_id, away_team_id, score_home, score_away, season_id, match_date, match_type, home_team, away_team, api_match_id, competition_code, football_data_home_team_id, football_data_away_team_id, apifb_home_team_id, apifb_away_team_id, apifb_fixture_id, apifb_league_id, apifb_season, bzzoiro_home_team_id, bzzoiro_away_team_id, bzzoiro_event_id, bzzoiro_league_id, bzzoiro_competition_code, prediction_data, created_at FROM matches WHERE id = ? AND (is_deleted IS NULL OR is_deleted=0)",
            (match_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    async def hard_delete_match(self, match_id: int) -> bool:
        """Permanently delete a match by ID. Returns True if deleted."""
        if self._conn is None:
            return False
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM matches WHERE id = ?", (match_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    async def restore_match(self, match_id: int) -> bool:
        """Restore a soft-deleted match by ID. Returns True if updated."""
        if self._conn is None:
            return False
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE matches SET is_deleted=0, deleted_at=NULL WHERE id = ?",
            (match_id,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    async def get_match_events(self, match_id: int, limit: int = 200, offset: int = 0) -> list[dict]:
        """Get events for a match with pagination."""
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT id, match_id, timestamp, event_type, from_track_id, to_track_id, team,
                     completed, confidence, metadata, user_corrected,
                     json_extract(metadata, '$.x') AS x,
                     json_extract(metadata, '$.y') AS y,
                     json_extract(metadata, '$.xg') AS xg,
                     json_extract(metadata, '$.xa') AS xa,
                     json_extract(metadata, '$.xt') AS xt,
                     json_extract(metadata, '$.vaep') AS vaep
              FROM events WHERE match_id = ? AND (is_deleted IS NULL OR is_deleted=0)
              ORDER BY timestamp LIMIT ? OFFSET ?""",
            (match_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def update_event(self, event_id: int, updates: dict) -> bool:
        """Update an event's fields. Returns True if row updated."""
        if self._conn is None:
            return False
        allowed = {"event_type", "team", "from_track_id", "to_track_id",
                    "completed", "confidence", "metadata", "user_corrected"}
        sets = []
        vals = []
        for key, val in updates.items():
            if key in allowed and StorageService._sanitize_column_name(key):
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
        """Soft-delete an event by ID. Returns True if row updated."""
        if self._conn is None:
            return False
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE events SET is_deleted=1, deleted_at=datetime('now') WHERE id = ? AND (is_deleted IS NULL OR is_deleted=0)",
            (event_id,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    async def hard_delete_event(self, event_id: int) -> bool:
        """Permanently delete an event by ID. Returns True if row deleted."""
        if self._conn is None:
            return False
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    async def restore_event(self, event_id: int) -> bool:
        """Restore a soft-deleted event by ID. Returns True if row updated."""
        if self._conn is None:
            return False
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE events SET is_deleted=0, deleted_at=NULL WHERE id = ?",
            (event_id,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    async def save_benchmark(self, result: BenchmarkResult) -> int:
        """Save a benchmark result to the database."""
        if self._conn is None:
            return 0
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

    async def get_recent_benchmarks(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """Get recent benchmark results with pagination."""
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, match_id, video_path, video_duration_seconds, total_frames, total_time_seconds, realtime_ratio, fps_effective, stage_tracking_seconds, peak_memory_mb, gpu_name, cpu_name, model_size, created_at
            FROM benchmark_results
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def save_validation_result(self, report: ValidationReport) -> list[int]:
        """Save a validation report to the database."""
        if self._conn is None:
            return []
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

    async def get_validation_results(self, match_id: int, limit: int = 20, offset: int = 0) -> list[dict]:
        """Get validation results for a match with pagination."""
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, match_id, metric_name, computed_value, created_at FROM validation_results WHERE match_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (match_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def save_feedback(self, feedback: dict) -> int:
        """Save coach feedback to the database."""
        if self._conn is None:
            return 0
        if not feedback:
            return 0
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO coach_feedback (
                    coach_id, match_id, overall_rating, tracking_rating,
                    events_rating, report_rating, ui_rating, comments, issues, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback.get("coach_id", 0),
                    feedback.get("match_id", 0),
                    feedback.get("overall_rating", 0),
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
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"save_feedback failed: {e}")
            return 0

    async def get_all_feedback(self) -> list[dict]:
        """Get all coach feedback entries."""
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute("SELECT id, coach_id, match_id, overall_rating, tracking_rating, events_rating, report_rating, ui_rating, comments, issues, created_at FROM coach_feedback ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    async def save_issue(self, issue: dict) -> int:
        """Save an issue report to the database."""
        if self._conn is None:
            return 0
        if not issue:
            return 0
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO issue_reports (
                    category, severity, description, match_id, screenshot_path, logs, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    issue.get("category", "unknown"),
                    issue.get("severity", "low"),
                    issue.get("description", ""),
                    issue.get("match_id"),
                    issue.get("screenshot_path"),
                    issue.get("logs", ""),
                    issue.get("created_at", ""),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"save_issue failed: {e}")
            return 0

    async def get_all_issues(self) -> list[dict]:
        """Get all issue reports."""
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute("SELECT id, category, severity, description, match_id, screenshot_path, logs, created_at FROM issue_reports ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    async def save_usage_session(self, session: dict) -> int:
        """Save an anonymized usage session."""
        if self._conn is None:
            return 0
        if not session:
            return 0
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO usage_sessions (
                    session_id, features_used, duration_seconds, match_count,
                    gpu_tier, model_size, error_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.get("session_id", ""),
                    json.dumps(session.get("features_used", [])),
                    session.get("duration_seconds", 0),
                    session.get("match_count", 0),
                    session.get("gpu_tier", ""),
                    session.get("model_size", ""),
                    session.get("error_count", 0),
                    session.get("created_at", ""),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"save_usage_session failed: {e}")
            return 0

    async def save_clip(self, clip: dict) -> int:
        """Save a video clip to the database."""
        if self._conn is None:
            return 0
        if not clip:
            return 0
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO video_clips (
                    match_id, event_type, start_seconds, end_seconds, duration_seconds,
                    source_video_path, output_path, thumbnail_path, player_id, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clip.get("match_id", 0),
                    clip.get("event_type", ""),
                    clip.get("start_seconds", 0.0),
                    clip.get("end_seconds", 0.0),
                    clip.get("duration_seconds", 0.0),
                    clip.get("source_video_path", ""),
                    clip.get("output_path", ""),
                    clip.get("thumbnail_path"),
                    clip.get("player_id"),
                    clip.get("description", ""),
                    clip.get("created_at", ""),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"save_clip failed: {e}")
            return 0

    async def get_clips_for_match(self, match_id: int) -> list[dict]:
        """Get all clips for a match."""
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, match_id, event_type, start_seconds, end_seconds, duration_seconds, source_video_path, output_path, thumbnail_path, player_id, description, created_at FROM video_clips WHERE match_id = ? ORDER BY created_at DESC",
            (match_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def save_playlist(self, playlist: dict) -> int:
        """Save a clip playlist to the database."""
        if self._conn is None:
            return 0
        if not playlist.get("name"):
            return 0
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO clip_playlists (
                    name, description, clip_ids, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    playlist.get("name", ""),
                    playlist.get("description", ""),
                    json.dumps(playlist.get("clip_ids", [])),
                    playlist.get("created_at", ""),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"save_playlist failed: {e}")
            return 0

    async def get_playlists(self) -> list[dict]:
        """Get all playlists."""
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute("SELECT id, name, description, clip_ids, created_at FROM clip_playlists ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    async def get_all_player_profiles(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get player profiles from the DB with pagination."""
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, global_id, display_name, preferred_position AS position, team, jersey_number, is_active, face_embedding, face_confidence, updated_at, created_at FROM player_profiles WHERE is_active = 1 ORDER BY id LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def update_player_profile_face(
        self, profile_id: int, face_embedding_json: str, face_confidence: float
    ) -> None:
        """Store face embedding and confidence for a player profile."""
        if self._conn is None:
            return
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

    async def save_events_bulk(self, match_id: int, events: list[dict]) -> int:
        """Save multiple events in a single transaction. Returns count saved."""
        if self._conn is None:
            return 0
        for ev in events:
            if ev.get("type") is None or ev.get("timestamp") is None:
                return 0
        cursor = self._conn.cursor()
        try:
            params = [
                (match_id, ev.get("type", ""), ev.get("timestamp", 0.0),
                 ev.get("from_track_id"), ev.get("to_track_id"), ev.get("team"),
                 ev.get("completed", False), ev.get("confidence", 0.0),
                 json.dumps(ev.get("metadata", {})))
                for ev in events
            ]
            cursor.executemany(
                """
                INSERT INTO events (match_id, event_type, timestamp, from_track_id,
                    to_track_id, team, completed, confidence, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
            self._conn.commit()
            return len(params)
        except Exception as e:
            logger.warning(f"save_events_bulk failed: {e}")
            self._conn.rollback()
            return 0

    async def get_match_players(self, match_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
        """Get players for a match with pagination."""
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, match_id, track_id, team, jersey_number, name, confidence FROM players WHERE match_id = ? AND (is_deleted IS NULL OR is_deleted=0) ORDER BY id LIMIT ? OFFSET ?",
            (match_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def hard_delete_player(self, player_id: int) -> bool:
        """Permanently delete a player by ID. Returns True if deleted."""
        if self._conn is None:
            return False
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM players WHERE id = ?", (player_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    async def restore_player(self, player_id: int) -> bool:
        """Restore a soft-deleted player by ID. Returns True if updated."""
        if self._conn is None:
            return False
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE players SET is_deleted=0, deleted_at=NULL WHERE id = ?",
            (player_id,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    async def save_players_bulk(self, match_id: int, players: list[dict]) -> int:
        """Save multiple players in a single transaction. Returns count saved."""
        if self._conn is None:
            return 0
        cursor = self._conn.cursor()
        try:
            params = [
                (match_id, p.get("track_id", 0), p.get("jersey_number"), p.get("name"),
                 p.get("team"), p.get("position"), p.get("distance_covered_m", 0),
                 p.get("max_speed_kmh", 0), p.get("avg_speed_kmh", 0),
                 p.get("passes_attempted", 0), p.get("passes_completed", 0),
                 p.get("shots", 0), p.get("tackles", 0))
                for p in players
            ]
            cursor.executemany(
                """
                INSERT INTO players (match_id, track_id, jersey_number, name, team,
                    position, distance_covered_m, max_speed_kmh, avg_speed_kmh,
                    passes_attempted, passes_completed, shots, tackles)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
            self._conn.commit()
            return len(params)
        except Exception as e:
            logger.warning(f"save_players_bulk failed: {e}")
            self._conn.rollback()
            return 0

    async def save_advanced_metrics_bulk(self, match_id: int, metrics: list[dict]) -> int:
        """Save multiple advanced metrics in a single transaction. Returns count saved."""
        if self._conn is None:
            return 0
        cursor = self._conn.cursor()
        try:
            params = [
                (match_id, m.get("player_id"), m.get("metric_name", ""),
                 m.get("metric_value", 0.0), m.get("metric_category", ""),
                 m.get("pitch_zone", ""), m.get("timestamp"),
                 json.dumps(m.get("metadata", {})))
                for m in metrics
            ]
            cursor.executemany(
                """
                INSERT INTO advanced_metrics (match_id, player_id, metric_name,
                    metric_value, metric_category, pitch_zone, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
            self._conn.commit()
            return len(params)
        except Exception as e:
            logger.warning(f"save_advanced_metrics_bulk failed: {e}")
            self._conn.rollback()
            return 0

    async def save_player_profile(self, profile: dict) -> int:
        """Create a new player profile."""
        if self._conn is None:
            return 0
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

    # ── Coding Tags CRUD ──────────────────────────────────────────

    async def save_coding_tag(self, match_id: int, tag: dict) -> int:
        """Save a manual coding tag and return its ID."""
        if self._conn is None:
            return 0
        if tag.get("event_type") is None or tag.get("video_time") is None:
            return 0
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO coding_tags (
                    match_id, event_type, sub_type, video_time,
                    player_track_id, player_name, team, period,
                    notes, lead_ms, lag_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    tag.get("event_type", "unknown"),
                    tag.get("sub_type", ""),
                    tag.get("video_time", 0.0),
                    tag.get("player_track_id", 0),
                    tag.get("player_name", ""),
                    tag.get("team", ""),
                    tag.get("period", 1),
                    tag.get("notes", ""),
                    tag.get("lead_ms", 2000),
                    tag.get("lag_ms", 3000),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            logger.warning(f"save_coding_tag failed: {e}")
            return 0

    async def get_coding_tags(self, match_id: int) -> list[dict]:
        """Get all coding tags for a match, ordered by video_time."""
        if self._conn is None:
            return []
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT id, match_id, event_type, sub_type, video_time, player_track_id, player_name, team, period, notes, lead_ms, lag_ms, created_at FROM coding_tags WHERE match_id = ? AND (is_deleted IS NULL OR is_deleted=0) ORDER BY video_time",
                (match_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"get_coding_tags failed: {e}")
            return []

    async def get_coding_tags_by_type(self, match_id: int, event_type: str) -> list[dict]:
        """Get coding tags filtered by event type."""
        if self._conn is None:
            return []
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT id, match_id, event_type, sub_type, video_time, player_track_id, player_name, team, period, notes, lead_ms, lag_ms, created_at FROM coding_tags WHERE match_id = ? AND event_type = ? AND (is_deleted IS NULL OR is_deleted=0) ORDER BY video_time",
                (match_id, event_type),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"get_coding_tags_by_type failed: {e}")
            return []

    async def get_coding_tags_by_player(self, match_id: int, player_track_id: int) -> list[dict]:
        """Get coding tags filtered by player track ID."""
        if self._conn is None:
            return []
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT id, match_id, event_type, sub_type, video_time, player_track_id, player_name, team, period, notes, lead_ms, lag_ms, created_at FROM coding_tags WHERE match_id = ? AND player_track_id = ? AND (is_deleted IS NULL OR is_deleted=0) ORDER BY video_time",
                (match_id, player_track_id),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"get_coding_tags_by_player failed: {e}")
            return []

    async def update_coding_tag(self, tag_id: int, updates: dict) -> bool:
        """Update a coding tag's fields. Returns True if row updated."""
        if self._conn is None:
            return False
        allowed = {"event_type", "sub_type", "video_time", "player_track_id",
                    "player_name", "team", "period", "notes", "lead_ms", "lag_ms"}
        sets = []
        vals = []
        for key, val in updates.items():
            if key in allowed and StorageService._sanitize_column_name(key):
                sets.append(f"{key} = ?")
                vals.append(val)
        if not sets:
            return False
        vals.append(tag_id)
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                f"UPDATE coding_tags SET {', '.join(sets)} WHERE id = ?", vals
            )
            self._conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.warning(f"update_coding_tag failed: {e}")
            return False

    async def delete_coding_tag(self, tag_id: int) -> bool:
        """Soft-delete a coding tag by ID. Returns True if updated."""
        if self._conn is None:
            return False
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "UPDATE coding_tags SET is_deleted=1, deleted_at=datetime('now') WHERE id = ? AND (is_deleted IS NULL OR is_deleted=0)",
                (tag_id,),
            )
            self._conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.warning(f"delete_coding_tag failed: {e}")
            return False

    async def hard_delete_coding_tag(self, tag_id: int) -> bool:
        """Permanently delete a coding tag by ID. Returns True if deleted."""
        if self._conn is None:
            return False
        try:
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM coding_tags WHERE id = ?", (tag_id,))
            self._conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.warning(f"hard_delete_coding_tag failed: {e}")
            return False

    async def restore_coding_tag(self, tag_id: int) -> bool:
        """Restore a soft-deleted coding tag by ID. Returns True if updated."""
        if self._conn is None:
            return False
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "UPDATE coding_tags SET is_deleted=0, deleted_at=NULL WHERE id = ?",
                (tag_id,),
            )
            self._conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.warning(f"restore_coding_tag failed: {e}")
            return False

    async def get_coding_tag_stats(self, match_id: int) -> dict:
        """Get aggregate stats for coding tags in a match."""
        if self._conn is None:
            return {"total": 0, "by_type": {}, "by_player": {}}
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT event_type, COUNT(*) as cnt FROM coding_tags WHERE match_id = ? AND (is_deleted IS NULL OR is_deleted=0) GROUP BY event_type",
                (match_id,),
            )
            by_type = {row["event_type"]: row["cnt"] for row in cursor.fetchall()}

            cursor.execute(
                "SELECT player_name, COUNT(*) as cnt FROM coding_tags WHERE match_id = ? AND player_name != '' AND (is_deleted IS NULL OR is_deleted=0) GROUP BY player_name",
                (match_id,),
            )
            by_player = {row["player_name"]: row["cnt"] for row in cursor.fetchall()}

            cursor.execute(
                "SELECT COUNT(*) as total FROM coding_tags WHERE match_id = ? AND (is_deleted IS NULL OR is_deleted=0)",
                (match_id,),
            )
            total = cursor.fetchone()["total"]

            return {"total": total, "by_type": by_type, "by_player": by_player}
        except Exception as e:
            logger.warning(f"get_coding_tag_stats failed: {e}")
            return {"total": 0, "by_type": {}, "by_player": {}}

    # ── Backup / Restore ─────────────────────────────────────────────────

    def backup(self) -> str:
        if self._conn is None:
            return ""
        try:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as e:
            logger.warning(f"backup: wal_checkpoint failed: {e}")

        from kawkab.core.paths import get_paths
        backup_dir = get_paths().appdata / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = str(backup_dir / f"kawkab_backup_{timestamp}.db")

        try:
            backup_conn = sqlite3.connect(backup_path)
            self._conn.backup(backup_conn)
            backup_conn.close()
            logger.info(f"Database backed up to {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"backup failed: {e}")
            return ""

    def restore(self, backup_path: str) -> bool:
        if self._conn is None:
            return False

        backup_file = Path(backup_path)
        if not backup_file.exists():
            logger.error(f"restore: backup file not found: {backup_path}")
            return False

        try:
            self._conn.close()
            self._conn = None

            shutil.copy2(backup_file, self._db_path)

            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")

            from kawkab.core.migration_manager import MigrationManager
            from kawkab.core.paths import get_paths
            mgr = MigrationManager(self._db_path, get_paths().migrations)
            mgr.migrate()

            logger.info(f"Database restored from {backup_path}")
            return True
        except Exception as e:
            logger.error(f"restore failed: {e}")
            return False

    def auto_backup(self) -> str:
        """Snapshot the raw DB file before migrations run.

        Never actually reachable before this fix: it delegated to
        backup(), which requires self._conn to already be open -- but
        initialize() only opens self._conn *after* migrations succeed
        (migrations run against the file directly via a MigrationManager-
        owned connection). Every call site logged "Auto-backup completed
        before migration" as if it worked; it always hit backup()'s
        `if self._conn is None: return ""` guard and silently no-op'd.

        This does a plain file copy instead (+ -wal/-shm sidecars if
        present from an unclean previous shutdown) rather than the
        sqlite3 `.backup()` API backup() uses, since that needs a live
        connection this method is specifically meant to run before.
        No-ops (not an error) if the DB doesn't exist yet -- nothing to
        back up on a brand-new install.
        """
        if self._use_postgres or self._db_path is None or not self._db_path.exists():
            return ""
        try:
            backup_dir = get_paths().appdata / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = backup_dir / f"kawkab_pre_migration_{timestamp}.db"
            shutil.copy2(self._db_path, dest)
            for suffix in ("-wal", "-shm"):
                sidecar = self._db_path.with_name(self._db_path.name + suffix)
                if sidecar.exists():
                    shutil.copy2(sidecar, Path(str(dest) + suffix))
            logger.info(f"Auto-backup completed before migration: {dest}")
            return str(dest)
        except Exception as e:
            logger.warning(f"Auto-backup skipped or failed before migration: {e}")
            return ""

    # ── Team management ──────────────────────────────────────────────────

    async def save_team(self, name: str, short_name: str = "", home_color: str = "#1e7e34", away_color: str = "#ffffff") -> int:
        if self._conn is None:
            return 0
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO teams (name, short_name, home_color, away_color) VALUES (?, ?, ?, ?)",
                (name, short_name, home_color, away_color),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            logger.warning(f"save_team failed: {e}")
            return 0

    async def get_team_by_name(self, name: str) -> dict | None:
        if self._conn is None:
            return None
        cursor = self._conn.cursor()
        cursor.execute("SELECT id, name, short_name, home_color, away_color, created_at FROM teams WHERE name = ?", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None

    async def get_all_teams(self) -> list[dict]:
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute("SELECT id, name, short_name, home_color, away_color, created_at FROM teams ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    # ── Tracking frames ──────────────────────────────────────────────────

    async def save_tracking_frame(self, match_id: int, frame_number: int, timestamp: float,
                                   player_detections: list[dict], ball_detections: list[dict]) -> bool:
        if self._conn is None:
            return False
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO tracking_frames (match_id, frame_number, timestamp, player_detections, ball_detections) VALUES (?, ?, ?, ?, ?)",
                (match_id, frame_number, timestamp, json.dumps(player_detections), json.dumps(ball_detections)),
            )
            self._conn.commit()
            return True
        except Exception as e:
            logger.warning(f"save_tracking_frame failed: {e}")
            return False

    async def save_tracking_frames_bulk(self, match_id: int, frames: list[dict]) -> int:
        if self._conn is None:
            return 0
        if not frames:
            return 0
        cursor = self._conn.cursor()
        rows = []
        for f in frames:
            try:
                rows.append((
                    match_id,
                    f.get("frame_number", 0),
                    f.get("timestamp", 0.0),
                    json.dumps(f.get("player_detections", [])),
                    json.dumps(f.get("ball_detections", [])),
                ))
            except Exception as e:
                logger.warning(f"save_tracking_frames_bulk frame {f.get('frame_number')} failed: {e}")
        if not rows:
            return 0
        cursor.executemany(
            "INSERT OR REPLACE INTO tracking_frames (match_id, frame_number, timestamp, player_detections, ball_detections) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()
        return len(rows)

    async def get_tracking_frames(self, match_id: int, start_frame: int = 0, end_frame: int | None = None, limit: int = 1000) -> list[dict]:
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        if end_frame is not None:
            cursor.execute(
                "SELECT id, match_id, frame_number, timestamp, player_detections, ball_detections, created_at FROM tracking_frames WHERE match_id = ? AND frame_number >= ? AND frame_number <= ? ORDER BY frame_number LIMIT ?",
                (match_id, start_frame, end_frame, limit),
            )
        else:
            cursor.execute(
                "SELECT id, match_id, frame_number, timestamp, player_detections, ball_detections, created_at FROM tracking_frames WHERE match_id = ? AND frame_number >= ? ORDER BY frame_number LIMIT ?",
                (match_id, start_frame, limit),
            )
        rows = []
        for row in cursor.fetchall():
            d = dict(row)
            d["player_detections"] = json.loads(d.get("player_detections", "[]"))
            d["ball_detections"] = json.loads(d.get("ball_detections", "[]"))
            rows.append(d)
        return rows

    async def get_tracking_frame_count(self, match_id: int) -> int:
        if self._conn is None:
            return 0
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM tracking_frames WHERE match_id = ?", (match_id,))
        row = cursor.fetchone()
        return row["cnt"] if row else 0

    async def delete_tracking_frames(self, match_id: int) -> bool:
        if self._conn is None:
            return False
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM tracking_frames WHERE match_id = ?", (match_id,))
        self._conn.commit()
        return True

    # ── Encryption key management ────────────────────────────────────────

    async def get_encryption_key(self, key_name: str = "medical_v1") -> str | None:
        if self._conn is None:
            return None
        cursor = self._conn.cursor()
        cursor.execute("SELECT key_value FROM encryption_keys WHERE key_name = ?", (key_name,))
        row = cursor.fetchone()
        return row["key_value"] if row else None

    async def rotate_encryption_key(self, key_name: str = "medical_v1") -> str | None:
        if self._conn is None:
            return None
        import os
        new_key = os.urandom(32).hex()
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE encryption_keys SET key_value = ?, rotated_at = datetime('now') WHERE key_name = ?",
            (new_key, key_name),
        )
        self._conn.commit()
        if cursor.rowcount > 0:
            from kawkab.core.encryption import init_fernet
            init_fernet(new_key)
            return new_key
        return None

    # ── User / Auth ───────────────────────────────────────────────────────────

    async def create_user(
        self, username: str, password_hash: str, role: str = "analyst",
        email: str = "", display_name: str = "",
        must_reset_password: bool = False,
    ) -> int:
        if self._conn is None:
            return 0
        cursor = self._conn.cursor()
        cursor.execute(
            """INSERT INTO users (username, email, display_name, password_hash, role, must_reset_password)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, email, display_name, password_hash, role, int(must_reset_password)),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def get_user_by_username(self, username: str) -> dict | None:
        if self._conn is None:
            return None
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, username, email, display_name, role, team, is_active, is_locked, locked_until, password_hash, must_reset_password, last_login FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    async def get_user_by_id(self, user_id: int) -> dict | None:
        if self._conn is None:
            return None
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, username, email, display_name, role, team, is_active, is_locked, locked_until, password_hash, must_reset_password, last_login FROM users WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    async def clear_expired_lock(self, user_id: int) -> None:
        """Reset is_locked/failed_attempts once locked_until has passed.

        record_failed_login() sets is_locked=1 + locked_until='+1 hour', but
        the only other place that clears is_locked was update_user_login()
        -- called only on a SUCCESSFUL login, which is unreachable while
        is_locked=1 blocks login() first. Without this, a lockout was
        permanent: the promised "try again in 1 hour" never actually
        un-blocked the account. Deliberately doesn't touch last_login
        (unlike update_user_login) since no successful auth happened yet.
        """
        if self._conn is None:
            return
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE users SET is_locked=0, failed_attempts=0, locked_until=NULL WHERE id=?",
            (user_id,),
        )
        self._conn.commit()

    async def update_user_login(self, user_id: int) -> None:
        if self._conn is None:
            return
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE users SET last_login=datetime('now'), failed_attempts=0, is_locked=0 WHERE id=?",
            (user_id,),
        )
        self._conn.commit()

    async def record_failed_login(self, username: str) -> int:
        if self._conn is None:
            return 0
        cursor = self._conn.cursor()
        cursor.execute("SELECT id, failed_attempts, is_locked FROM users WHERE username=?", (username,))
        row = cursor.fetchone()
        if not row:
            return 0
        uid = row["id"]
        attempts = (row["failed_attempts"] or 0) + 1
        if attempts >= 5:
            cursor.execute(
                "UPDATE users SET failed_attempts=?, is_locked=1, locked_until=datetime('now','+1 hour') WHERE id=?",
                (attempts, uid),
            )
        else:
            cursor.execute("UPDATE users SET failed_attempts=? WHERE id=?", (attempts, uid))
        self._conn.commit()
        return 5 - attempts

    async def save_session(self, user_id: int, token_hash: str, expires_at: str) -> int:
        if self._conn is None:
            return 0
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO user_sessions (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user_id, token_hash, expires_at),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def validate_session(self, token_hash: str) -> dict | None:
        if self._conn is None:
            return None
        cursor = self._conn.cursor()
        # u.is_locked=0 added: previously a session created before a lockout
        # stayed valid through it -- locking an account did not invalidate
        # its live sessions, only blocked *new* logins.
        cursor.execute(
            """SELECT u.id, u.username, u.role, u.team, u.display_name
               FROM user_sessions s JOIN users u ON s.user_id = u.id
               WHERE s.token_hash=? AND s.expires_at > datetime('now') AND u.is_active=1 AND u.is_locked=0""",
            (token_hash,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    async def delete_session(self, token_hash: str) -> bool:
        if self._conn is None:
            return False
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM user_sessions WHERE token_hash=?", (token_hash,))
        self._conn.commit()
        return cursor.rowcount > 0

    async def audit_log(
        self, user_id: int, username: str, action: str,
        resource_type: str = "", resource_id: str = "", details: dict | None = None,
    ) -> int:
        if self._conn is None:
            return 0
        cursor = self._conn.cursor()
        cursor.execute(
            """INSERT INTO audit_events_local (user_id, username, action, resource_type, resource_id, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, action, resource_type, resource_id, json.dumps(details or {})),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def get_audit_log(self, limit: int = 50, offset: int = 0) -> list[dict]:
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, user_id, username, action, resource_type, resource_id, details, created_at FROM audit_events_local ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def get_all_users(self) -> list[dict]:
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, username, email, display_name, role, team, is_active, is_locked, last_login, created_at FROM users ORDER BY id"
        )
        return [dict(row) for row in cursor.fetchall()]

    async def change_password(self, user_id: int, new_hash: str) -> bool:
        if self._conn is None:
            return False
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash=?, must_reset_password=0, updated_at=datetime('now') WHERE id=?",
            (new_hash, user_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # ── GPS / Physical Data ────────────────────────────────────────────────────

    async def save_gps_session(
        self, match_id: int, player_id: int, session_type: str, vendor: str,
    ) -> int:
        if self._conn is None:
            return 0
        cursor = self._conn.cursor()
        cursor.execute(
            """INSERT INTO gps_sessions (match_id, player_id, session_type, vendor)
               VALUES (?, ?, ?, ?)""",
            (match_id, player_id, session_type, vendor),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def update_gps_session_stats(
        self, session_id: int, summary: dict,
    ) -> None:
        if self._conn is None:
            return
        cursor = self._conn.cursor()
        cursor.execute(
            """UPDATE gps_sessions SET duration_seconds=?, total_distance_m=?,
               max_speed_kmh=?, avg_speed_kmh=?, player_load=?
               WHERE id=?""",
            (
                summary.get("duration_s"),
                summary.get("total_distance_m"),
                summary.get("max_speed_kmh"),
                summary.get("avg_speed_kmh"),
                summary.get("total_player_load"),
                session_id,
            ),
        )
        self._conn.commit()

    async def save_gps_samples_bulk(
        self, session_id: int, samples: list[dict],
    ) -> int:
        if self._conn is None or not samples:
            return 0
        cursor = self._conn.cursor()
        count = 0
        for s in samples:
            cursor.execute(
                """INSERT INTO gps_samples (session_id, timestamp, lat, lon, speed_ms,
                   acceleration, accel_x, accel_y, accel_z, heart_rate, distance,
                   player_load, metabolic_power, speed_zone, x_m, y_m)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    s.get("timestamp", 0.0),
                    s.get("lat"),
                    s.get("lon"),
                    s.get("speed_ms"),
                    s.get("acceleration"),
                    s.get("accel_x"),
                    s.get("accel_y"),
                    s.get("accel_z"),
                    s.get("heart_rate"),
                    s.get("distance"),
                    s.get("player_load"),
                    s.get("metabolic_power"),
                    s.get("speed_zone"),
                    s.get("x_m"),
                    s.get("y_m"),
                ),
            )
            count += 1
        self._conn.commit()
        return count

    async def get_gps_sessions(self, match_id: int) -> list[dict]:
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT id, player_id, session_type, vendor, start_time, end_time,
               duration_seconds, total_distance_m, max_speed_kmh, avg_speed_kmh,
               player_load FROM gps_sessions
               WHERE match_id=? AND (is_deleted IS NULL OR is_deleted=0)
               ORDER BY id""",
            (match_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def get_gps_samples(self, session_id: int) -> list[dict]:
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT timestamp, speed_ms, acceleration, heart_rate, distance,
               player_load, metabolic_power, speed_zone, x_m, y_m
               FROM gps_samples WHERE session_id=?
               ORDER BY timestamp""",
            (session_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def save_acwr(
        self, player_id: int, date: str, acute: float, chronic: float, acwr: float,
    ) -> int:
        if self._conn is None:
            return 0
        cursor = self._conn.cursor()
        cat = "normal"
        if acwr > 1.5:
            cat = "very_high"
        elif acwr > 1.3:
            cat = "high"
        elif acwr < 0.8:
            cat = "low"
        cursor.execute(
            """INSERT OR REPLACE INTO acwr_daily
               (player_id, date, acute_load_7d, chronic_load_28d, acwr, load_category)
               VALUES (?,?,?,?,?,?)""",
            (player_id, date, acute, chronic, acwr, cat),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    async def get_player_acwr(
        self, player_id: int, limit: int = 30,
    ) -> list[dict]:
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT date, acute_load_7d, chronic_load_28d, acwr, load_category
               FROM acwr_daily WHERE player_id=?
               ORDER BY date DESC LIMIT ?""",
            (player_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def get_player_gps_summary(
        self, player_id: int, limit: int = 10,
    ) -> list[dict]:
        if self._conn is None:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT id, session_type, vendor, start_time, duration_seconds,
               total_distance_m, max_speed_kmh, avg_speed_kmh, player_load
               FROM gps_sessions WHERE player_id=?
               ORDER BY id DESC LIMIT ?""",
            (player_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("StorageService closed")
        else:
            logger.warning("StorageService.close called with no active connection")
