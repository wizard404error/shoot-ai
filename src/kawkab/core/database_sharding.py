"""Database sharding by season — partition match/event data across per-season SQLite databases.

Keeps the current season hot (default DB) while archiving older seasons
to separate files. Queries cross-season transparently when needed.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from kawkab.core.logging import get_logger

logger = get_logger(__name__)


def get_season_key(date_str: str | None = None) -> str:
    """Convert a date string to a season key (e.g., '2025-2026')."""
    if date_str:
        try:
            year = int(date_str[:4])
        except (ValueError, IndexError):
            year = datetime.utcnow().year
    else:
        year = datetime.utcnow().year
    if datetime.utcnow().month >= 7:
        return f"{year}-{year + 1}"
    return f"{year - 1}-{year}"


class SeasonShardManager:
    """Manages per-season database shards for match and event data.

    Each season gets its own SQLite database file at data/shard_<season>.db.
    The current season is the default database; cross-season queries merge results.
    """

    def __init__(self, data_dir: str | None = None) -> None:
        self._data_dir = data_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "data"
        )
        self._shards: dict[str, sqlite3.Connection] = {}
        self._current_season = get_season_key()
        os.makedirs(self._data_dir, exist_ok=True)

    def _shard_path(self, season: str) -> str:
        return os.path.join(self._data_dir, f"shard_{season}.db")

    def _get_shard(self, season: str) -> sqlite3.Connection:
        if season not in self._shards:
            path = self._shard_path(season)
            conn = sqlite3.connect(path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._init_shard_schema(conn)
            self._shards[season] = conn
        return self._shards[season]

    def _init_shard_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                home_team TEXT,
                away_team TEXT,
                home_score INTEGER DEFAULT 0,
                away_score INTEGER DEFAULT 0,
                date TEXT,
                season TEXT NOT NULL DEFAULT '',
                data TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'unknown',
                timestamp REAL DEFAULT 0,
                x REAL DEFAULT 0,
                y REAL DEFAULT 0,
                data TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_events_match ON events(match_id);
            CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season);
            CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
        """)
        conn.commit()

    def store_match(self, match: dict, season: str | None = None) -> int:
        season = season or self._current_season
        conn = self._get_shard(season)
        date = match.get("date", datetime.utcnow().isoformat())
        conn.execute(
            """INSERT INTO matches (name, home_team, away_team, home_score, away_score, date, season, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                match.get("name", "Unknown Match"),
                match.get("home_team", "Home"),
                match.get("away_team", "Away"),
                match.get("home_score", 0),
                match.get("away_score", 0),
                date,
                season,
                json.dumps(match),
            ),
        )
        conn.commit()
        match_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        logger.info(f"Stored match {match_id} in shard {season}")
        return match_id

    def get_match(self, match_id: int, season: str | None = None) -> dict | None:
        seasons = [season] if season else self._list_seasons()
        for s in seasons:
            conn = self._get_shard(s)
            row = conn.execute(
                "SELECT * FROM matches WHERE id = ?", (match_id,)
            ).fetchone()
            if row:
                return dict(row)
        return None

    def store_events(self, events: list[dict], match_id: int, season: str | None = None) -> int:
        if not events:
            return 0
        season = season or self._current_season
        conn = self._get_shard(season)
        count = 0
        for ev in events:
            conn.execute(
                """INSERT INTO events (match_id, event_type, timestamp, x, y, data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    match_id,
                    ev.get("event_type", "unknown"),
                    ev.get("timestamp", 0),
                    ev.get("x", 0),
                    ev.get("y", 0),
                    json.dumps(ev),
                ),
            )
            count += 1
        conn.commit()
        logger.info(f"Stored {count} events in shard {season} for match {match_id}")
        return count

    def get_events(self, match_id: int) -> list[dict]:
        results = []
        for season in self._list_seasons():
            conn = self._get_shard(season)
            rows = conn.execute(
                "SELECT * FROM events WHERE match_id = ?", (match_id,)
            ).fetchall()
            for row in rows:
                ev = dict(row)
                try:
                    ev["data"] = json.loads(ev["data"])
                except (json.JSONDecodeError, TypeError):
                    pass
                results.append(ev)
        return results

    def get_all_matches(self, season: str | None = None) -> list[dict]:
        results = []
        seasons = [season] if season else self._list_seasons()
        for s in seasons:
            conn = self._get_shard(s)
            rows = conn.execute(
                "SELECT * FROM matches ORDER BY date DESC"
            ).fetchall()
            for row in rows:
                m = dict(row)
                try:
                    m["data"] = json.loads(m["data"])
                except (json.JSONDecodeError, TypeError):
                    pass
                results.append(m)
        return results

    def get_season_stats(self, season: str) -> dict:
        conn = self._get_shard(season)
        matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return {"season": season, "matches": matches, "events": events}

    def _list_seasons(self) -> list[str]:
        seasons = []
        for f in os.listdir(self._data_dir):
            if f.startswith("shard_") and f.endswith(".db"):
                season = f.replace("shard_", "").replace(".db", "")
                seasons.append(season)
        if self._current_season not in seasons:
            seasons.append(self._current_season)
        return sorted(seasons)

    def migrate_to_shards(self, source_db_path: str) -> dict[str, int]:
        """Migrate data from a monolithic database to sharded structure."""
        if not os.path.exists(source_db_path):
            return {"error": f"Source DB not found: {source_db_path}"}

        source = sqlite3.connect(source_db_path)
        source.row_factory = sqlite3.Row
        migrated = {"matches": 0, "events": 0}

        try:
            rows = source.execute("SELECT * FROM matches").fetchall()
            for row in rows:
                m = dict(row)
                date = m.get("date", datetime.utcnow().isoformat())
                season = get_season_key(date)
                match_id = self.store_match(m, season)
                migrated["matches"] += 1

                ev_rows = source.execute(
                    "SELECT * FROM events WHERE match_id = ?", (row["id"],)
                ).fetchall()
                events = [dict(ev) for ev in ev_rows]
                self.store_events(events, match_id, season)
                migrated["events"] += len(events)

            logger.info(f"Migration complete: {migrated}")
        finally:
            source.close()

        return migrated

    def close(self) -> None:
        for conn in self._shards.values():
            try:
                conn.close()
            except Exception:
                pass
        self._shards.clear()
