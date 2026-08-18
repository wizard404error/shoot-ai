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

    def test_full_real_migration_chain_applies_cleanly_to_fresh_db(self):
        """Every existing test above uses a synthetic migrations_dir with
        hand-written SQL -- none of them ever run the REAL, FULL
        001-through-latest chain from src/kawkab/migrations/ against a
        genuinely empty database. That's exactly the scenario a brand new
        install (or CI) hits, and it's the one place schema drift between
        a migration file and the code that queries its tables would
        surface as a hard failure instead of silently working by
        coincidence on someone's already-migrated dev database.
        """
        real_migrations_dir = Path(__file__).resolve().parent.parent.parent / "src" / "kawkab" / "migrations"
        assert real_migrations_dir.exists(), f"expected migrations dir at {real_migrations_dir}"
        migration_files = sorted(real_migrations_dir.glob("*.sql"))
        numbered = [f for f in migration_files if f.stem.split("_")[0].isdigit()]
        assert len(numbered) >= 20, "sanity check: expected the real migration set, not an empty/wrong dir"

        tmpdir = Path(tempfile.mkdtemp())
        try:
            db_path = tmpdir / "fresh.db"
            mgr = MigrationManager(db_path, real_migrations_dir)
            mgr.migrate()  # must not raise

            conn = _closing_conn(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = {row[0] for row in cursor.fetchall()}

            highest_version = max(int(f.stem.split("_")[0]) for f in numbered)
            version = mgr._get_current_version(conn)
            assert version == highest_version

            # Spot-check tables from across the whole chain (earliest,
            # middle, and the two newest/untracked-until-now migrations)
            # actually exist -- catches a migration that silently no-ops
            # (e.g. a typo'd CREATE TABLE IF NOT EXISTS) as well as one
            # that raises.
            for expected_table in [
                "matches", "players", "events",              # 001
                "coding_tags",                                # 018
                "player_shortlist", "player_contracts",       # 016, 017
                "gps_sessions", "gps_samples", "acwr_daily",  # 026
                "users", "user_sessions", "audit_events_local",  # 027
            ]:
                assert expected_table in tables, f"migration chain never created '{expected_table}'"

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
