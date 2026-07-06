"""Tests for the PostgreSQL storage adapter."""

from __future__ import annotations

import pytest
from kawkab.services.postgres_storage import PostgresStorageAdapter


class TestPostgresStorageAdapter:
    @pytest.fixture
    def adapter(self):
        return PostgresStorageAdapter()

    def test_not_available_without_dsn(self, adapter):
        assert adapter.available is False

    def test_initialize_no_dsn(self, adapter):
        import asyncio
        asyncio.run(adapter.initialize())
        assert adapter.available is False

    def test_fetch_empty_when_not_available(self, adapter):
        import asyncio
        result = asyncio.run(adapter.fetch("SELECT 1"))
        assert result == []

    def test_fetchrow_none_when_not_available(self, adapter):
        import asyncio
        result = asyncio.run(adapter.fetchrow("SELECT 1"))
        assert result is None

    def test_execute_returns_zero_when_not_available(self, adapter):
        import asyncio
        result = asyncio.run(adapter.execute("SELECT 1"))
        assert result == "0"

    def test_save_match_zero_when_not_available(self, adapter):
        import asyncio
        result = asyncio.run(adapter.save_match("test", "/path/to/video.mp4"))
        assert result == 0

    def test_get_all_matches_empty(self, adapter):
        import asyncio
        result = asyncio.run(adapter.get_all_matches())
        assert result == []

    def test_get_match_none(self, adapter):
        import asyncio
        result = asyncio.run(adapter.get_match(1))
        assert result is None

    def test_save_events_bulk_zero(self, adapter):
        import asyncio
        result = asyncio.run(adapter.save_events_bulk(1, [{"type": "pass"}]))
        assert result == 0

    def test_get_match_events_empty(self, adapter):
        import asyncio
        result = asyncio.run(adapter.get_match_events(1))
        assert result == []

    def test_save_players_bulk_zero(self, adapter):
        import asyncio
        result = asyncio.run(adapter.save_players_bulk(1, [{"track_id": 1, "name": "P1"}]))
        assert result == 0

    def test_get_match_players_empty(self, adapter):
        import asyncio
        result = asyncio.run(adapter.get_match_players(1))
        assert result == []

    def test_close_no_error(self, adapter):
        import asyncio
        asyncio.run(adapter.close())

    def test_executemany_no_error(self, adapter):
        import asyncio
        asyncio.run(adapter.executemany("SELECT 1", [(1,), (2,)]))
