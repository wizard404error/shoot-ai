"""Tests for MigrationManager."""

import shutil
import tempfile
from pathlib import Path

import pytest

from tests.conftest import load_service_module

# Load real module, bypassing conftest stub
mm_mod = load_service_module(
    "kawkab.core.migration_manager", "migration_manager.py", subdir="core"
)
MigrationManager = mm_mod.MigrationManager


def _closing_conn(path):
    """Open and return a sqlite3 connection that uses DELETE journal mode."""
    import sqlite3
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=DELETE")
    return conn


class TestMigrationManager:
    def test_initial_version_is_zero(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            db_path = tmpdir / "test.db"
            migrations_dir = tmpdir / "migrations"
            migrations_dir.mkdir()
            mgr = MigrationManager(db_path, migrations_dir)
            mgr.migrate()
            conn = _closing_conn(db_path)
            version = mgr._get_current_version(conn)
            assert version == 0
            conn.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_applies_migration_files(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            db_path = tmpdir / "test.db"
            migrations_dir = tmpdir / "migrations"
            migrations_dir.mkdir()
            mig_file = migrations_dir / "001_create_test_table.sql"
            mig_file.write_text("CREATE TABLE test_table (id INTEGER PRIMARY KEY);")
            mgr = MigrationManager(db_path, migrations_dir)
            mgr.migrate()
            conn = _closing_conn(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
            assert cursor.fetchone() is not None
            version = mgr._get_current_version(conn)
            assert version >= 1
            conn.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_skips_already_applied_migrations(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            db_path = tmpdir / "test.db"
            migrations_dir = tmpdir / "migrations"
            migrations_dir.mkdir()
            mig_file = migrations_dir / "001_create_test_table.sql"
            mig_file.write_text("CREATE TABLE test_table (id INTEGER PRIMARY KEY);")
            mgr = MigrationManager(db_path, migrations_dir)
            mgr.migrate()
            mgr.migrate()
            conn = _closing_conn(db_path)
            version = mgr._get_current_version(conn)
            assert version == 1
            conn.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_handles_empty_migrations_dir(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            db_path = tmpdir / "test.db"
            migrations_dir = tmpdir / "migrations"
            migrations_dir.mkdir()
            mgr = MigrationManager(db_path, migrations_dir)
            mgr.migrate()
            conn = _closing_conn(db_path)
            version = mgr._get_current_version(conn)
            assert version == 0
            conn.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_migration_015_event_dedup_applies_cleanly(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            db_path = tmpdir / "test.db"
            migrations_dir = tmpdir / "migrations"
            migrations_dir.mkdir()
            import sqlite3
            conn = _closing_conn(db_path)
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, match_id INTEGER, timestamp REAL, event_type TEXT, from_track_id INTEGER)")
            cursor.execute("CREATE TABLE user_corrections (id INTEGER PRIMARY KEY, event_id INTEGER)")
            conn.commit()
            conn.close()
            mig_file = migrations_dir / "015_add_event_dedup.sql"
            mig_file.write_text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedup\n"
                "ON events(match_id, timestamp, event_type, from_track_id);\n"
                "CREATE INDEX IF NOT EXISTS idx_user_corrections_event\n"
                "ON user_corrections(event_id);\n"
            )
            mgr = MigrationManager(db_path, migrations_dir)
            mgr.migrate()
            conn = _closing_conn(db_path)
            version = mgr._get_current_version(conn)
            assert version == 15
            cursor = conn.cursor()
            cursor.execute("INSERT INTO events (id, match_id, timestamp, event_type, from_track_id) VALUES (1, 1, 10.0, 'pass', 1)")
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("INSERT INTO events (id, match_id, timestamp, event_type, from_track_id) VALUES (2, 1, 10.0, 'pass', 1)")
            conn.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
