from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

CLOUD_DB_PATH = os.environ.get("KAWKAB_CLOUD_DB", str(Path.home() / ".kawkab" / "cloud.db"))


_db: Optional[sqlite3.Connection] = None


def get_cloud_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        Path(CLOUD_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _db = sqlite3.connect(CLOUD_DB_PATH)
        _db.row_factory = sqlite3.Row
        _db.execute("PRAGMA journal_mode=WAL")
        _db.execute("PRAGMA foreign_keys=ON")
        _migrate(_db)
    return _db


def _migrate(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            owner_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            role TEXT DEFAULT 'member',
            UNIQUE(team_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS team_invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id),
            email TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            token TEXT UNIQUE NOT NULL,
            accepted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id INTEGER NOT NULL REFERENCES users(id),
            team_id INTEGER REFERENCES teams(id),
            data TEXT DEFAULT '{}',
            version INTEGER DEFAULT 1,
            is_shared INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            device_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            synced_at TEXT DEFAULT (datetime('now'))
        );

        INSERT OR IGNORE INTO schema_version VALUES (1);
    """)
    db.commit()
