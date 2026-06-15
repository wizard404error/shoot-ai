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
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("StorageService initialized")

    def _create_tables(self) -> None:
        """Create all required database tables."""
        assert self._conn is not None

        cursor = self._conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                video_path TEXT NOT NULL,
                home_team TEXT,
                away_team TEXT,
                match_date TIMESTAMP,
                duration_seconds REAL,
                fps REAL,
                total_frames INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                analyzed_at TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                track_id INTEGER NOT NULL,
                jersey_number INTEGER,
                name TEXT,
                team TEXT,
                position TEXT,
                distance_covered_m REAL,
                max_speed_kmh REAL,
                avg_speed_kmh REAL,
                passes_attempted INTEGER DEFAULT 0,
                passes_completed INTEGER DEFAULT 0,
                shots INTEGER DEFAULT 0,
                tackles INTEGER DEFAULT 0,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                timestamp REAL NOT NULL,
                from_track_id INTEGER,
                to_track_id INTEGER,
                team TEXT,
                completed BOOLEAN,
                confidence REAL,
                metadata TEXT,
                user_corrected BOOLEAN DEFAULT 0,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                possession_home REAL,
                possession_away REAL,
                passes_home INTEGER,
                passes_away INTEGER,
                shots_home INTEGER,
                shots_away INTEGER,
                confidence_overall REAL,
                full_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                language TEXT NOT NULL,
                report_text TEXT NOT NULL,
                llm_provider TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                correction_type TEXT NOT NULL,
                original_value TEXT,
                corrected_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self._conn.commit()

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

    async def get_all_matches(self) -> list[dict]:
        """Get all matches from the database."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, name, video_path, home_team, away_team, match_date,
                   duration_seconds, analyzed_at, created_at
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

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("StorageService closed")
