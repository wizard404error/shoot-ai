"""Database migration system for Kawkab AI.

Simple numbered migration system. Migrations are SQL scripts that upgrade
the schema from one version to the next. On startup, StorageService checks
the current schema_version and applies any pending migrations.

Migration files: src/kawkab/migrations/001_initial.sql, 002_add_seasons.sql, etc.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from kawkab.core.logging import get_logger

logger = get_logger(__name__)


class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self, db_path: Path, migrations_dir: Path) -> None:
        self.db_path = db_path
        self.migrations_dir = migrations_dir

    def _get_current_version(self, conn: sqlite3.Connection) -> int:
        """Get current schema version from the database."""
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else 0

    def _set_version(self, conn: sqlite3.Connection, version: int) -> None:
        """Record that a migration has been applied."""
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
            (version,),
        )
        conn.commit()

    def _get_migration_files(self) -> list[Path]:
        """Get all migration files sorted by version number."""
        if not self.migrations_dir.exists():
            return []
        files = sorted(
            self.migrations_dir.glob("*.sql"),
            key=lambda p: int(p.stem.split("_")[0]),
        )
        return files

    def migrate(self) -> None:
        """Apply all pending migrations."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        current = self._get_current_version(conn)
        files = self._get_migration_files()

        applied = 0
        for file in files:
            version = int(file.stem.split("_")[0])
            if version > current:
                sql = file.read_text(encoding="utf-8")
                logger.info(f"Applying migration {version}: {file.name}")
                try:
                    conn.executescript(sql)
                    self._set_version(conn, version)
                    applied += 1
                except Exception as e:
                    logger.error(f"Migration {version} failed: {e}")
                    raise

        conn.close()
        if applied > 0:
            logger.info(f"Applied {applied} migration(s). Schema now at version {current + applied}")
        else:
            logger.debug(f"Schema up to date at version {current}")
