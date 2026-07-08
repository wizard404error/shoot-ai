"""Tests for the PostgreSQL storage adapter."""

from __future__ import annotations

import os
from typing import AsyncGenerator

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


@pytest.mark.skipif(
    not os.environ.get("KAWKAB_DB_URL"),
    reason="KAWKAB_DB_URL not set — integration tests skipped",
)
class TestPostgresStorageIntegration:
    @pytest.fixture
    async def pg(self) -> AsyncGenerator[PostgresStorageAdapter, None]:
        adapter = PostgresStorageAdapter()
        await adapter.initialize()
        assert adapter.available is True, "PostgreSQL must be available for integration tests"
        yield adapter
        # Clean up test data
        await adapter.execute("DELETE FROM events WHERE match_id = 999999")
        await adapter.execute("DELETE FROM players WHERE match_id = 999999")
        await adapter.execute("DELETE FROM matches WHERE id = 999999")
        await adapter.close()

    async def test_initialize_sets_available(self, pg):
        assert pg.available is True

    async def test_fetch_basic_query(self, pg):
        rows = await pg.fetch("SELECT current_database() AS db")
        assert len(rows) >= 1
        assert rows[0]["db"] == "kawkab"

    async def test_fetchrow_returns_one(self, pg):
        row = await pg.fetchrow("SELECT 1 AS val, 2 AS val2")
        assert row is not None
        assert row["val"] == 1
        assert row["val2"] == 2

    async def test_execute_returning(self, pg):
        result = await pg.execute("SELECT 42 AS answer")
        assert result is not None

    async def test_save_and_get_match(self, pg):
        mid = await pg.save_match("Integration Test Match", "/videos/test.mp4")
        assert mid > 0

        match = await pg.get_match(mid)
        assert match is not None
        assert match["name"] == "Integration Test Match"
        assert match["video_path"] == "/videos/test.mp4"

        matches = await pg.get_all_matches()
        assert any(m["id"] == mid for m in matches)

    async def test_update_match_teams(self, pg):
        mid = await pg.save_match("Teams Match", "/videos/teams.mp4")
        await pg.update_match_teams(mid, "Home FC", "Away FC")
        match = await pg.get_match(mid)
        assert match["home_team"] == "Home FC"
        assert match["away_team"] == "Away FC"

    async def test_update_match_analysis(self, pg):
        mid = await pg.save_match("Analysis Match", "/videos/analysis.mp4")
        analysis_data = {"shots": 10, "possession": 55}
        await pg.update_match_analysis(mid, analysis_data)
        match = await pg.get_match(mid)
        assert match is not None

    async def test_save_and_get_events(self, pg):
        mid = await pg.save_match("Events Match", "/videos/events.mp4")
        events = [
            {"type": "pass", "timestamp": 1.0, "team": "home", "x": 10, "y": 20, "end_x": 30, "end_y": 40, "from_track_id": 1},
            {"type": "shot", "timestamp": 2.0, "team": "away", "x": 50, "y": 60, "end_x": 70, "end_y": 80, "from_track_id": 2},
        ]
        count = await pg.save_events_bulk(mid, events)
        assert count > 0

        saved = await pg.get_match_events(mid)
        assert len(saved) >= 2
        types = {e["type"] for e in saved}
        assert "pass" in types
        assert "shot" in types

    async def test_save_and_get_players(self, pg):
        mid = await pg.save_match("Players Match", "/videos/players.mp4")
        players = [
            {"track_id": 101, "name": "Alice", "team": "home", "jersey_number": 10},
            {"track_id": 102, "name": "Bob", "team": "away", "jersey_number": 7},
        ]
        count = await pg.save_players_bulk(mid, players)
        assert count > 0

        saved = await pg.get_match_players(mid)
        assert len(saved) >= 2
        names = {p["name"] for p in saved}
        assert "Alice" in names
        assert "Bob" in names

    async def test_update_event(self, pg):
        mid = await pg.save_match("Update Event Match", "/videos/update.mp4")
        await pg.save_events_bulk(mid, [{"type": "pass", "timestamp": 5.0, "from_track_id": 1}])
        events = await pg.get_match_events(mid)
        assert len(events) >= 1
        eid = events[0]["id"]

        result = await pg.update_event(eid, {"event_type": "shot"})
        assert result is True
        updated = await pg.get_match_events(mid)
        updated_event = next(e for e in updated if e["id"] == eid)
        # DB stores as event_type, get_match_events returns raw column names
        assert updated_event["event_type"] == "shot"

    async def test_delete_event(self, pg):
        mid = await pg.save_match("Delete Event Match", "/videos/delete.mp4")
        await pg.save_events_bulk(mid, [{"type": "pass", "timestamp": 10.0, "from_track_id": 1}])
        events = await pg.get_match_events(mid)
        assert len(events) >= 1
        eid = events[0]["id"]

        await pg.delete_event(eid)
        remaining = await pg.get_match_events(mid)
        assert all(e["id"] != eid for e in remaining)

    async def test_coding_tags_crud(self, pg):
        mid = await pg.save_match("Tags Match", "/videos/tags.mp4")
        # save tag (takes a dict)
        tag_dict = {
            "tag_type": "good_attack",
            "category": "attack",
            "start_time": 10.0,
            "end_time": 20.0,
            "player_track_id": 5,
            "period": 1,
            "timestamp": 15.0,
        }
        tid = await pg.save_coding_tag(mid, tag_dict)
        assert tid > 0

        # get by match
        tags = await pg.get_coding_tags(mid)
        assert len(tags) >= 1

        # get by type
        by_type = await pg.get_coding_tags_by_type(mid, "good_attack")
        assert len(by_type) >= 1

        # get by player
        by_player = await pg.get_coding_tags_by_player(mid, 5)
        assert len(by_player) >= 1

        # get stats
        stats = await pg.get_coding_tag_stats(mid)
        assert stats["total_tags"] >= 1

        # update
        await pg.update_coding_tag(tid, {"notes": "Updated note"})
        tags_after = await pg.get_coding_tags(mid)
        updated = next(t for t in tags_after if t["id"] == tid)
        assert updated.get("notes") == "Updated note"

        # delete
        await pg.delete_coding_tag(tid)
        tags_final = await pg.get_coding_tags(mid)
        assert all(t["id"] != tid for t in tags_final)

    async def test_save_advanced_metrics(self, pg):
        mid = await pg.save_match("Metrics Match", "/videos/metrics.mp4")
        metrics = {"xg": 1.5, "xt": 0.8, "vaep": 0.3}
        result = await pg.save_advanced_metrics(mid, metrics)
        assert result is not None

    async def test_save_advanced_metrics_bulk(self, pg):
        mid = await pg.save_match("Bulk Metrics", "/videos/bulk.mp4")
        items = [{"track_id": 1, "xg": 0.5}, {"track_id": 2, "xg": 0.3}]
        result = await pg.save_advanced_metrics_bulk(mid, items)
        assert result is not None

    async def test_reports_crud(self, pg):
        mid = await pg.save_match("Reports Match", "/videos/reports.mp4")
        rid = await pg.save_report(mid, "test report", language="en", report_type="match")
        assert rid > 0

        reports = await pg.get_reports(mid, "en")
        assert len(reports) >= 1

    async def test_save_validation_and_benchmark(self, pg):
        mid = await pg.save_match("Validation Match", "/videos/validation.mp4")
        class FakeReport:
            match_id = mid
            events_accuracy = 0.95
            possession_accuracy = 0.88
            team_assignment_accuracy = 0.92
            speed_accuracy = 0.85
            def to_dict(self):
                return {"events_accuracy": 0.95, "possession_accuracy": 0.88}
        result_key = await pg.save_validation_result(FakeReport())
        assert len(result_key) == 4

        bench = await pg.get_recent_benchmarks(limit=5)
        assert isinstance(bench, list)

    async def test_feedback_and_issues(self, pg):
        mid = await pg.save_match("Feedback Match", "/videos/feedback.mp4")
        fid = await pg.save_feedback({"match_id": mid, "user_name": "user1", "comments": "Great tool!"})
        assert fid > 0
        all_feedback = await pg.get_all_feedback()
        assert any(f["id"] == fid for f in all_feedback)

        iid = await pg.save_issue({"match_id": mid, "description": "Test issue", "severity": "high", "status": "bug"})
        assert iid > 0
        all_issues = await pg.get_all_issues()
        assert any(iss["id"] == iid for iss in all_issues)

    async def test_playlists_crud(self, pg):
        mid = await pg.save_match("Playlist Match", "/videos/playlist.mp4")
        pid = await pg.save_playlist({"name": "Test Playlist", "match_id": mid, "clips": [1, 2, 3]})
        assert pid > 0

        playlists = await pg.get_playlists()
        assert any(p["id"] == pid for p in playlists)

    async def test_clips_crud(self, pg):
        mid = await pg.save_match("Clips Match", "/videos/clips.mp4")
        cid = await pg.save_clip({"match_id": mid, "name": "test clip", "start_time": 10.0, "end_time": 20.0})
        assert cid > 0

        clips = await pg.get_clips_for_match(mid)
        assert any(c["id"] == cid for c in clips)

    async def test_player_profiles(self, pg):
        await pg.save_player_profile({"track_id": 201, "height_cm": 180, "weight_kg": 75})
        all_profiles = await pg.get_all_player_profiles()
        assert isinstance(all_profiles, list)
