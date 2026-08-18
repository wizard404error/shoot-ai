"""Database migration system for Kawkab AI.

Simple numbered migration system. Migrations are SQL scripts that upgrade
the schema from one version to the next. On startup, StorageService checks
the current schema_version and applies any pending migrations.

Migration files: src/kawkab/migrations/001_initial.sql, 002_add_seasons.sql, etc.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

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
        """Record that a migration has been applied.

        Does NOT commit -- the caller (migrate()) controls the transaction
        boundary so this write lands in the same transaction as the
        migration's own schema changes. Committing here independently
        would defeat that: a failure between this call and the schema
        changes committing would record a version bump for a migration
        that never actually finished applying.
        """
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
            (version,),
        )

    def _get_migration_files(self) -> list[Path]:
        """Get all migration files sorted by version number."""
        if not self.migrations_dir.exists():
            return []
        all_files = list(self.migrations_dir.glob("*.sql"))
        numeric_files = []
        for f in all_files:
            stem = f.stem
            parts = stem.split("_")
            if parts and parts[0].isdigit():
                numeric_files.append((int(parts[0]), f))
        numeric_files.sort(key=lambda x: x[0])
        return [f for _, f in numeric_files]

    def migrate(self) -> None:
        """Apply all pending migrations.

        Each migration file runs inside one explicit transaction, so a
        failure partway through a file rolls back every statement from
        that file instead of leaving the schema partially changed with no
        way forward. Previously this used conn.executescript(sql) with no
        transaction at all: sqlite3.Connection.executescript() issues an
        implicit COMMIT before running and then autocommits each
        statement in the script as it executes, so it can't be made
        atomic just by wrapping it in BEGIN/COMMIT -- the implicit COMMIT
        would silently swallow that. If migration N failed at, say,
        statement 5 of 9: statements 1-4 were permanently applied,
        _set_version() never ran (it came after the failure), so the next
        startup saw version N-1 and re-applied migration N from statement
        1 -- which then failed immediately re-running a CREATE TABLE/ALTER
        TABLE that had already succeeded. The app was permanently bricked
        with no rollback path.

        Statements are now split and executed individually inside a
        manual transaction (conn.isolation_level = None -- see below).
        Splitting on ";" is safe here specifically because none of the
        numbered migration files use CREATE TRIGGER or other constructs
        with semicolons inside a statement body (verified before writing
        this); a migrations directory that gained one would need a real
        SQL-aware splitter instead.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        # Manual transaction control: without this, sqlite3's default
        # "autocommit unless a DML statement started one" mode does its
        # own implicit BEGIN handling that fights with the explicit
        # BEGIN/COMMIT/ROLLBACK below.
        conn.isolation_level = None
        try:
            current = self._get_current_version(conn)
            files = self._get_migration_files()

            applied = 0
            for file in files:
                version = int(file.stem.split("_")[0])
                if version > current:
                    sql = file.read_text(encoding="utf-8")
                    logger.info(f"Applying migration {version}: {file.name}")
                    statements = [s.strip() for s in sql.split(";") if s.strip()]
                    conn.execute("BEGIN")
                    try:
                        for stmt in statements:
                            conn.execute(stmt)
                        self._set_version(conn, version)
                        conn.execute("COMMIT")
                        applied += 1
                    except Exception as e:
                        conn.execute("ROLLBACK")
                        logger.error(f"Migration {version} failed and was rolled back: {e}")
                        raise
        finally:
            conn.close()

        if applied > 0:
            logger.info(f"Applied {applied} migration(s). Schema now at version {current + applied}")
        else:
            logger.debug(f"Schema up to date at version {current}")
