"""Postgres/SQLite storage parity tests (Phase 2c, elite-readiness roadmap).

The Postgres adapter (postgres_storage.py) is a hand-written parallel of
StorageService, not a drop-in twin — CLAUDE.md's "storage backend
divergence" known gap. These tests pin the *contract* both backends must
satisfy: same method surface, same result shapes, same return types,
same fallback behavior when no database is connected. Running the same
assertion helper against both adapters means a divergence introduced on
one side fails here, not in production at a club.

The SQLite side runs against a REAL migrated scratch DB (real migration
chain 001-030, same pattern as test_statsbomb_import_service.py). The
Postgres side runs against the adapter's documented no-pool fallback
behavior (no live Postgres in unit CI — the pool paths need a real
server, exercised by the integration job when one exists).

Method surface equality is the core regression guard: for every public
async storage method the SQLite service exposes (minus documented
SQLite-only methods like backup()), the Postgres adapter must expose the
same name — that is the contract StatsBomb/vendor import services and
the API layer rely on when the backend is swapped.
"""

from __future__ import annotations

import asyncio
import inspect
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def sqlite_storage(tmp_path):
    """Real SQLite storage with the REAL 001-030 migration chain."""
    from kawkab.core.migration_manager import MigrationManager
    from kawkab.services.storage_service import StorageService

    scratch_db = tmp_path / "test_parity.db"
    migrations_dir = PROJECT_ROOT / "src" / "kawkab" / "migrations"
    MigrationManager(scratch_db, migrations_dir).migrate()
    svc = StorageService()
    svc._db_path = scratch_db
    svc._conn = sqlite3.connect(str(scratch_db))
    svc._conn.row_factory = sqlite3.Row
    return svc


@pytest.fixture()
def pg_adapter():
    from kawkab.services.postgres_storage import PostgresStorageAdapter

    return PostgresStorageAdapter()  # no DSN -> not available -> fallback paths


# ── Method-surface parity (the divergence guard) ───────────────────────────

# Documented exceptions: SQLite-specific backup API, connection plumbing,
# and the frame/loop helper StorageService uses for __getattr__ delegation.
_SQLITE_ONLY = {
    "backup",
    "initialize",
    "close",
    "_get_conn",
    "_ensure_initialized",
    "_sanitize_column_name",
    "_log_error",
}


def _public_async_methods(cls) -> set[str]:
    out = set()
    for name, member in inspect.getmembers(cls):
        if name.startswith("_"):
            continue
        if inspect.iscoroutinefunction(member):
            out.add(name)
    return out


class TestMethodSurfaceParity:
    def test_migration_030_tables_exist_in_sqlite(self, sqlite_storage):
        """The vendor-provenance tables must be present after migration."""
        cur = sqlite_storage._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('tracking_imports', 'event_frame_links')"
        )
        names = {row["name"] for row in cur.fetchall()}
        assert names == {"tracking_imports", "event_frame_links"}

    def test_tracking_import_methods_on_both_backends(self, sqlite_storage, pg_adapter):
        for method in (
            "save_tracking_import",
            "get_tracking_imports",
            "get_tracking_import_by_id",
            "delete_tracking_import",
            "save_event_frame_links_bulk",
            "get_event_frame_links",
            "save_tracking_frames_bulk",
            "get_tracking_frames",
        ):
            assert hasattr(sqlite_storage, method), f"SQLite missing {method}"
            assert hasattr(pg_adapter, method), f"Postgres missing {method}"

    def test_import_service_contract_methods_on_both_backends(self, sqlite_storage, pg_adapter):
        """Methods the StatsBomb/vendor import services call — must exist on
        both backends or vendor imports break the moment a club runs Postgres."""
        for method in (
            "save_match",
            "save_player",
            "save_event",
            "save_advanced_metrics",
            "get_match_events",
            "get_tracking_imports",
        ):
            assert hasattr(sqlite_storage, method), f"SQLite missing {method}"
            assert hasattr(pg_adapter, method), f"Postgres missing {method}"

    def test_no_orphaned_sqlite_async_methods(self, sqlite_storage, pg_adapter):
        """Every public async StorageService method (minus documented
        SQLite-only ones) must exist on the Postgres adapter."""
        sqlite_methods = _public_async_methods(type(sqlite_storage)) - _SQLITE_ONLY
        pg_methods = _public_async_methods(type(pg_adapter))
        missing = sqlite_methods - pg_methods
        assert not missing, (
            f"Postgres adapter is missing {len(missing)} methods that exist on "
            f"StorageService: {sorted(missing)[:20]}"
        )


# ── Behavioral parity on shared fallback semantics ─────────────────────────


class TestNoConnectionFallbackParity:
    """Both adapters must fail soft (documented convention) when the DB
    connection is absent — never raise."""

    def test_sqlite_save_match_no_conn_returns_zero(self, tmp_path):
        from kawkab.services.storage_service import StorageService

        svc = StorageService()
        svc._conn = None
        assert asyncio.run(svc.save_match("x", "")) == 0

    def test_pg_save_match_no_pool_returns_zero(self, pg_adapter):
        assert asyncio.run(pg_adapter.save_match("x", "")) == 0

    def test_sqlite_get_tracking_imports_no_conn_returns_empty(self, tmp_path):
        from kawkab.services.storage_service import StorageService

        svc = StorageService()
        svc._conn = None
        assert asyncio.run(svc.get_tracking_imports(1)) == []

    def test_pg_get_tracking_imports_no_pool_returns_empty(self, pg_adapter):
        assert asyncio.run(pg_adapter.get_tracking_imports(1)) == []

    def test_pg_save_tracking_import_no_pool_returns_zero(self, pg_adapter):
        result = asyncio.run(
            pg_adapter.save_tracking_import(1, "skillcorner")
        )
        assert result == 0

    def test_pg_get_tracking_import_by_id_no_pool_returns_none(self, pg_adapter):
        assert asyncio.run(pg_adapter.get_tracking_import_by_id(1)) is None

    def test_pg_delete_tracking_import_no_pool_returns_false(self, pg_adapter):
        assert asyncio.run(pg_adapter.delete_tracking_import(1)) is False

    def test_pg_event_frame_links_no_pool(self, pg_adapter):
        assert asyncio.run(pg_adapter.save_event_frame_links_bulk(1, [{"event_id": 1}])) == 0
        assert asyncio.run(pg_adapter.get_event_frame_links(1)) == []


# ── Round-trip parity: the same operations against the real SQLite DB ──────


class TestTrackingImportRoundTrip:
    def test_tracking_import_full_round_trip(self, sqlite_storage):
        """save_match -> save_tracking_import -> get_tracking_imports ->
        delete, exercising migration 030's real tables."""
        match_id = asyncio.run(sqlite_storage.save_match(
            "SkillCorner Fixture", "", home_team="Alpha", away_team="Beta"
        ))
        assert match_id > 0

        import_row = asyncio.run(sqlite_storage.save_tracking_import(
            match_id, "skillcorner",
            source_path="/tmp/fake.json",
            checksum="deadbeef",
            fps=25.0,
            frame_count=100,
            pitch_length_m=105.0,
            pitch_width_m=68.0,
            metadata={"periods": [1, 2]},
        ))
        assert import_row > 0

        rows = asyncio.run(sqlite_storage.get_tracking_imports(match_id))
        assert len(rows) == 1
        row = rows[0]
        assert row["vendor"] == "skillcorner"
        assert row["checksum"] == "deadbeef"
        assert row["fps"] == pytest.approx(25.0)
        assert row["frame_count"] == 100
        assert row["metadata"] == {"periods": [1, 2]}

        by_id = asyncio.run(sqlite_storage.get_tracking_import_by_id(import_row))
        assert by_id is not None and by_id["id"] == import_row

        assert asyncio.run(sqlite_storage.delete_tracking_import(import_row)) is True
        assert asyncio.run(sqlite_storage.get_tracking_imports(match_id)) == []

    def test_event_frame_links_round_trip_with_dedup(self, sqlite_storage):
        match_id = asyncio.run(sqlite_storage.save_match("L", ""))
        # events table needs a real event row (FK)
        event_id = asyncio.run(sqlite_storage.save_event(match_id, {
            "type": "pass", "timestamp": 1.0, "team": "home",
        }))
        assert event_id > 0

        links = [{"event_id": event_id, "frame_number": 5, "frame_offset": 0},
                 {"event_id": event_id, "frame_number": 6, "frame_offset": 1},
                 {"event_id": event_id, "frame_number": 5, "frame_offset": 0}]  # dup
        written = asyncio.run(
            sqlite_storage.save_event_frame_links_bulk(match_id, links)
        )
        assert written == 3  # executemany row count; the UNIQUE dup is ignored

        rows = asyncio.run(sqlite_storage.get_event_frame_links(match_id))
        assert len(rows) == 2
        assert {r["frame_number"] for r in rows} == {5, 6}

        single = asyncio.run(sqlite_storage.get_event_frame_links(match_id, event_id=event_id))
        assert len(single) == 2

    def test_vendor_tracking_frames_round_trip(self, sqlite_storage):
        """Vendor frames persist through the SAME plumbing the video
        pipeline uses, and read back with parsed detection lists."""
        match_id = asyncio.run(sqlite_storage.save_match("T", ""))
        frames = [
            {
                "frame_number": i,
                "timestamp": i / 25.0,
                "player_detections": [
                    {"track_id": 1, "x": 10.0 + i, "y": 20.0, "speed": 1.5},
                    {"track_id": 2, "x": 30.0, "y": 40.0 + i, "speed": 2.0},
                ],
                "ball_detections": [{"track_id": 999, "x": 50.0, "y": 34.0, "z": 0.1}],
            }
            for i in range(5)
        ]
        saved = asyncio.run(sqlite_storage.save_tracking_frames_bulk(match_id, frames))
        assert saved == 5

        got = asyncio.run(sqlite_storage.get_tracking_frames(match_id, limit=100))
        assert len(got) == 5
        assert got[0]["player_detections"][0]["x"] == pytest.approx(10.0)
        assert got[4]["ball_detections"][0]["y"] == pytest.approx(34.0)
        assert asyncio.run(sqlite_storage.get_tracking_frame_count(match_id)) == 5
