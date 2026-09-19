"""Fault-injection tests for the storage honesty contract (A1 of the elite plan).

These tests FORCE database failures and assert the failure surfaces as a
typed exception — never a silent 0/[]/False. They exist because storage
swallowed errors for months; the proven damage:

- save_coding_tag's FK violation surfaced to the UI as "Tag rejected:
  event_type/tag_type required" (CI, 2026-09-19) — the user was blamed
  for a database problem.
- The Postgres adapter's no-pool fallback fed [] to every read, so a
  cloud deployment once returned empty data for all calls.

Contract under test (coding-tags cluster is the first convert):
- Not-initialized  -> StorageNotInitialized
- DB failure       -> StorageWriteError / StorageReadError
- Rejected input   -> legacy falsy return (distinguishable from failure)
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import install_kawkab_stubs

install_kawkab_stubs()

from kawkab.core.migration_manager import MigrationManager  # noqa: E402
from kawkab.core.paths import get_paths  # noqa: E402
from kawkab.services.postgres_storage import PostgresStorageAdapter  # noqa: E402
from kawkab.services.storage_errors import (  # noqa: E402
    StorageDuplicateError,
    StorageNotInitializedError,
    StorageReadError,
    StorageWriteError,
    is_duplicate_violation,
)
from kawkab.services.storage_service import StorageService  # noqa: E402

# ── helpers ──────────────────────────────────────────────────────────────


def _migrated_sqlite_storage() -> StorageService:
    """A real sqlite StorageService with the full schema applied."""
    svc = StorageService()
    svc._use_postgres = False
    svc._pg = None
    svc._db_path = Path(tempfile.mkdtemp(prefix="kawkab_honesty_")) / "honesty.db"
    svc._conn = sqlite3.connect(str(svc._db_path))
    svc._conn.row_factory = sqlite3.Row
    # Mirror production initialize(): FK enforcement is what makes the
    # coding_tags->matches constraint fire instead of silently passing.
    svc._conn.execute("PRAGMA foreign_keys=ON")
    MigrationManager(svc._db_path, get_paths().migrations).migrate()
    return svc


# ── sqlite: closed connection (a real user flow) ─────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "op,args",
    [
        ("save_coding_tag", (1, {"event_type": "shot"})),
        ("get_coding_tags", (1,)),
        ("get_coding_tags_by_type", (1, "shot")),
        ("get_coding_tags_by_player", (1, 5)),
        ("update_coding_tag", (1, {"notes": "x"})),
        ("delete_coding_tag", (1,)),
        ("hard_delete_coding_tag", (1,)),
        ("restore_coding_tag", (1,)),
        ("get_coding_tag_stats", (1,)),
    ],
)
async def test_closed_connection_raises_not_initialized(op, args):
    svc = _migrated_sqlite_storage()
    svc._conn.close()
    svc._conn = None
    with pytest.raises(StorageNotInitializedError):
        await getattr(svc, op)(*args)


# ── sqlite: live connection, forced DB failure ───────────────────────────


@pytest.mark.asyncio
async def test_fk_violation_raises_write_error_not_rejection():
    """THE regression pin: a missing match row (FK violation) must raise
    StorageWriteError, not return 0 that the UI renders as 'Tag rejected:
    event_type/tag_type required'."""
    svc = _migrated_sqlite_storage()
    try:
        with pytest.raises(StorageWriteError) as excinfo:
            await svc.save_coding_tag(424242, {"event_type": "shot", "video_time": 1.0})
        assert "save_coding_tag" in str(excinfo.value)
        # The typed error chain keeps the real cause for logs.
        assert excinfo.value.__cause__ is not None
    finally:
        svc._conn.close()


@pytest.mark.asyncio
async def test_read_failure_raises_read_error():
    svc = _migrated_sqlite_storage()
    try:
        svc._conn.execute("DROP TABLE coding_tags")
        svc._conn.commit()
        with pytest.raises(StorageReadError):
            await svc.get_coding_tags(1)
    finally:
        svc._conn.close()


@pytest.mark.asyncio
async def test_write_failure_raises_write_error_on_update():
    svc = _migrated_sqlite_storage()
    try:
        svc._conn.execute("DROP TABLE coding_tags")
        svc._conn.commit()
        with pytest.raises(StorageWriteError):
            await svc.update_coding_tag(1, {"notes": "x"})
    finally:
        svc._conn.close()


# ── rejected input stays a falsy return, distinguishable from failure ────


@pytest.mark.asyncio
async def test_rejected_input_still_returns_falsy():
    svc = _migrated_sqlite_storage()
    try:
        assert await svc.save_coding_tag(1, {"notes": "no type key"}) == 0
        assert await svc.update_coding_tag(1, {"not_a_field": 1}) is False
    finally:
        svc._conn.close()


# ── Postgres adapter: pool down ──────────────────────────────────────────


def _pg_without_pool() -> PostgresStorageAdapter:
    a = PostgresStorageAdapter(dsn="postgresql://user:pass@localhost:5432/kawkab_test")
    a._pool = None
    a._available = False
    return a


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "op,args",
    [
        ("save_coding_tag", (1, {"event_type": "shot"})),
        ("get_coding_tags", (1,)),
        ("get_coding_tags_by_type", (1, "shot")),
        ("get_coding_tags_by_player", (1, 5)),
        ("update_coding_tag", (1, {"notes": "x"})),
        ("delete_coding_tag", (1,)),
        ("hard_delete_coding_tag", (1,)),
        ("restore_coding_tag", (1,)),
        ("get_coding_tag_stats", (1,)),
    ],
)
async def test_pg_pool_down_raises_not_initialized(op, args):
    """Pin: pool-down must RAISE for the converted cluster. The old silent
    [] fallback is the exact mechanism that made a Postgres deployment
    return empty data for every call."""
    adapter = _pg_without_pool()
    with pytest.raises(StorageNotInitializedError):
        await getattr(adapter, op)(*args)


# ── handler surface: failure vs rejection vs success ─────────────────────


@pytest.mark.asyncio
async def test_handler_distinguishes_failure_from_rejection():
    """Through the real handler: DB failure -> sanitized error payload;
    rejected input -> the same 'Tag rejected' payload as before (input
    feedback, not error masking)."""
    from kawkab.ui.bridge_handlers.bridge_coding import CodingHandler

    failing = MagicMock(
        save_coding_tag=AsyncMock(side_effect=StorageWriteError("save_coding_tag", "boom"))
    )
    h = CodingHandler(None, {"storage_service": failing})
    out = json.loads(await h.save_tag("1", json.dumps({"event_type": "shot"})))
    assert "error" in out and "save_coding_tag" in out["error"]

    rejecting = MagicMock(save_coding_tag=AsyncMock(return_value=0))
    h2 = CodingHandler(None, {"storage_service": rejecting})
    out2 = json.loads(await h2.save_tag("1", json.dumps({"notes": "no type"})))
    assert "error" in out2 and "Tag rejected" in out2["error"]


@pytest.mark.asyncio
async def test_handler_reports_read_failure_honestly():
    from kawkab.ui.bridge_handlers.bridge_coding import CodingHandler

    failing = MagicMock(
        get_coding_tags=AsyncMock(side_effect=StorageReadError("get_coding_tags", "disk full"))
    )
    h = CodingHandler(None, {"storage_service": failing})
    out = json.loads(await h.get_tags("1"))
    assert "error" in out


# ── duplicates: a contract outcome, not a failure ───────────────────────


@pytest.mark.asyncio
async def test_duplicate_event_raises_typed_duplicate_not_write_error():
    """The events dedup index (migration 015) makes same-second-same-type
    events a real, EXPECTED outcome (consecutive ball receipts). It must
    raise StorageDuplicateError — catchable as failure by generic callers,
    catchable as skip by importers — never a swallowed 0 like before, and
    never an opaque failure that breaks importer dedup (the v0.13.2-batch
    regression)."""
    from kawkab.services.storage_errors import StorageDuplicateError

    svc = _migrated_sqlite_storage()
    try:
        match_id = await svc.save_match("dup-test", "")
        ev = {"type": "pass", "timestamp": 12.5, "team": "home", "from_track_id": 77}
        assert await svc.save_event(match_id, ev) > 0
        with pytest.raises(StorageDuplicateError) as excinfo:
            await svc.save_event(match_id, ev)
        # Subclass contract: generic failure handlers still catch it.
        assert isinstance(excinfo.value, StorageWriteError)
    finally:
        svc._conn.close()


@pytest.mark.asyncio
async def test_fk_violation_is_not_classified_as_duplicate():
    """Classification precision: a missing referenced row is a FAILURE,
    not a duplicate — misclassifying it would make importers silently
    skip data that should have failed loudly (the v0.13.2 bug class)."""
    svc = _migrated_sqlite_storage()
    try:
        with pytest.raises(StorageWriteError) as excinfo:
            await svc.save_event(424242, {"type": "pass", "timestamp": 1.0, "from_track_id": 5})
        assert not isinstance(excinfo.value, StorageDuplicateError)
    finally:
        svc._conn.close()


def test_duplicate_classification_by_driver_code_and_message():
    """Classifier: structured codes where the driver offers them, message
    fallback where it doesn't; FK violations never classify as duplicate."""

    # sqlite extended result codes: 1555 PK, 2067 unique index.
    pk = sqlite3.IntegrityError("UNIQUE constraint failed: events.id")
    pk.sqlite_errorcode = 1555
    idx = sqlite3.IntegrityError("UNIQUE constraint failed: x.y")
    idx.sqlite_errorcode = 2067
    assert is_duplicate_violation(pk)
    assert is_duplicate_violation(idx)

    # Postgres SQLSTATE 23505 (asyncpg carries .sqlstate).
    pg_like = RuntimeError("x")
    pg_like.sqlstate = "23505"
    assert is_duplicate_violation(pg_like)

    # Message fallback for drivers with neither attribute.
    assert is_duplicate_violation(RuntimeError("duplicate key value violates"))
    assert not is_duplicate_violation(RuntimeError("FOREIGN KEY constraint failed"))
    assert not is_duplicate_violation(RuntimeError("disk I/O error"))


@pytest.mark.asyncio
async def test_importer_dedup_contract_end_to_end():
    """The full designed flow through the real importer: the corpus sample
    contains same-second same-type events, which hit the migration-015
    dedup index, raise the typed error, and are SKIPPED + counted — not
    swallowed, not fatal (the exact path broken by the opaque
    StorageWriteError wrap)."""
    from kawkab.services.statsbomb_import_service import StatsBombImportService

    svc = _migrated_sqlite_storage()
    try:
        corpus = Path(__file__).resolve().parents[2] / "data" / "statsbomb_corpus"
        sample = next(corpus.glob("*.json"), None)
        if sample is None:
            pytest.skip("no committed statsbomb corpus file")
        importer = StatsBombImportService(svc)
        summary = await importer.import_match(sample)
        assert summary["events_imported"] > 0
        assert summary["events_skipped"] > 0
    finally:
        svc._conn.close()
