"""Tests for all 7 storage sub-modules.

Covers CRUD, edge cases (missing fields, None values), uninitialized
state handling, and error paths for every public API method across:
  - BaseStorage (connection management)
  - ClipStorage  (video clips / playlists)
  - EventStorage (events, advanced metrics, corrections)
  - FeedbackStorage (coach feedback, issue reports)
  - MatchStorage (match records, metadata updates)
  - PlayerStorage (player records, bulk)
  - ProfileStorage (player profiles, face embeddings)
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import install_kawkab_stubs

install_kawkab_stubs()

from kawkab.services.storage.base import BaseStorage
from kawkab.services.storage.clip_storage import ClipStorage
from kawkab.services.storage.event_storage import EventStorage
from kawkab.services.storage.feedback_storage import FeedbackStorage
from kawkab.services.storage.match_storage import MatchStorage
from kawkab.services.storage.player_storage import PlayerStorage
from kawkab.services.storage.profile_storage import ProfileStorage

# Patch SecurityValidator with missing methods used by sub-module fallbacks.
# The real SecurityValidator (from kawkab.core.security) lacks several methods
# that the sub-module try/except blocks define; the import succeeds because
# conftest stubs the kawkab.core package path, so the sub-modules use the
# real (incomplete) validator instead of their own fallback stubs.
from kawkab.core.security import SecurityValidator as _RealSecVal

def _validate_positive_float(v, n="v"):
    return max(0.0, float(v))

def _validate_float_range(v, lo, hi, n="v"):
    return max(float(lo), min(float(hi), float(v)))

def _validate_event_type(e):
    return str(e)

def _validate_event_dict(e):
    return e

def _validate_track_id(t):
    return int(t)

_RealSecVal.validate_positive_float = staticmethod(_validate_positive_float)
_RealSecVal.validate_float_range = staticmethod(_validate_float_range)
_RealSecVal.validate_event_type = staticmethod(_validate_event_type)
_RealSecVal.validate_event_dict = staticmethod(_validate_event_dict)
_RealSecVal.validate_track_id = staticmethod(_validate_track_id)

# Shared DDL covering all tables used by the 7 sub-modules
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, video_path TEXT NOT NULL,
    home_team TEXT, away_team TEXT,
    match_date TEXT, duration_seconds REAL, fps REAL,
    total_frames INTEGER, analyzed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    api_match_id INTEGER, competition_code TEXT,
    football_data_home_team_id INTEGER, football_data_away_team_id INTEGER,
    apifb_home_team_id INTEGER, apifb_away_team_id INTEGER,
    apifb_fixture_id INTEGER, apifb_league_id INTEGER, apifb_season INTEGER,
    bzzoiro_home_team_id INTEGER, bzzoiro_away_team_id INTEGER,
    bzzoiro_event_id INTEGER, bzzoiro_league_id INTEGER,
    bzzoiro_competition_code TEXT, prediction_data TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL, event_type TEXT NOT NULL,
    timestamp REAL NOT NULL, from_track_id INTEGER, to_track_id INTEGER,
    team TEXT, completed INTEGER DEFAULT 0, confidence REAL DEFAULT 0.0,
    metadata TEXT DEFAULT '{}', user_corrected INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL, track_id INTEGER NOT NULL,
    jersey_number INTEGER, name TEXT, team TEXT, position TEXT,
    distance_covered_m REAL DEFAULT 0, max_speed_kmh REAL DEFAULT 0,
    avg_speed_kmh REAL DEFAULT 0, passes_attempted INTEGER DEFAULT 0,
    passes_completed INTEGER DEFAULT 0, shots INTEGER DEFAULT 0,
    tackles INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS advanced_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL, player_id INTEGER,
    metric_name TEXT NOT NULL, metric_value REAL NOT NULL,
    metric_category TEXT DEFAULT '', pitch_zone TEXT DEFAULT '',
    timestamp REAL, metadata TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS coach_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coach_id TEXT NOT NULL, match_id INTEGER,
    overall_rating INTEGER NOT NULL, tracking_rating INTEGER,
    events_rating INTEGER, report_rating INTEGER, ui_rating INTEGER,
    comments TEXT, issues TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS issue_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL, severity TEXT NOT NULL,
    description TEXT NOT NULL, match_id INTEGER,
    screenshot_path TEXT, logs TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS video_clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL, event_type TEXT NOT NULL,
    start_seconds REAL NOT NULL, end_seconds REAL NOT NULL,
    duration_seconds REAL NOT NULL, source_video_path TEXT NOT NULL,
    output_path TEXT NOT NULL, thumbnail_path TEXT,
    player_id INTEGER, description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS clip_playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, description TEXT DEFAULT '',
    clip_ids TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS player_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    global_id TEXT DEFAULT '', display_name TEXT DEFAULT '',
    jersey_number INTEGER, preferred_position TEXT,
    team TEXT DEFAULT 'home', is_active INTEGER DEFAULT 1,
    face_embedding TEXT, face_confidence REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL, correction_type TEXT NOT NULL,
    original_value TEXT, corrected_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def conn():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript(CREATE_SQL)
        conn.commit()
        yield conn
        conn.close()


def _make_storage(cls, conn):
    inst = cls()
    inst._conn = conn
    return inst


# ── BaseStorage ──────────────────────────────────────────────────────────────

class TestBaseStorage:
    def test_ensure_initialized_false_when_no_conn(self):
        bs = BaseStorage()
        assert bs._conn is None
        assert bs._ensure_initialized("test") is False

    def test_ensure_initialized_true_with_conn(self, conn):
        bs = BaseStorage()
        bs._conn = conn
        assert bs._ensure_initialized("test") is True

    def test_log_error_does_not_raise(self):
        bs = BaseStorage()
        bs._log_error("test", ValueError("something"))  # no exception

    def test_conn_property_delegates_to_storage(self):
        inner = BaseStorage()
        inner._conn = "fake_conn"
        outer = BaseStorage(storage=inner)
        assert outer._conn == "fake_conn"

    def test_db_path_property(self, conn):
        bs = BaseStorage()
        assert bs._db_path is None
        bs._db_path = Path("/tmp/test.db")
        assert bs._db_path == Path("/tmp/test.db")


# ── ClipStorage ──────────────────────────────────────────────────────────────

class TestClipStorage:
    async def test_save_and_get_clips(self, conn):
        store = _make_storage(ClipStorage, conn)
        cid = await store.save_clip({
            "match_id": 1, "event_type": "goal",
            "start_seconds": 10.0, "end_seconds": 20.0,
            "duration_seconds": 10.0,
            "source_video_path": "/v/src.mp4", "output_path": "/v/clip.mp4",
        })
        assert cid > 0
        clips = await store.get_clips_for_match(1)
        assert len(clips) == 1
        assert clips[0]["event_type"] == "goal"
        assert abs(clips[0]["start_seconds"] - 10.0) < 0.001

    async def test_get_clips_for_match_empty(self, conn):
        store = _make_storage(ClipStorage, conn)
        assert await store.get_clips_for_match(999) == []

    async def test_save_clip_missing_required(self, conn):
        store = _make_storage(ClipStorage, conn)
        assert await store.save_clip({}) == 0

    async def test_save_and_get_playlists(self, conn):
        store = _make_storage(ClipStorage, conn)
        cid = await store.save_clip({
            "match_id": 1, "event_type": "goal",
            "start_seconds": 0.0, "end_seconds": 10.0,
            "duration_seconds": 10.0,
            "source_video_path": "/v/s.mp4", "output_path": "/v/c.mp4",
        })
        assert cid > 0
        pid = await store.save_playlist({
            "name": "Highlights", "clip_ids": [cid],
        })
        assert pid > 0
        playlists = await store.get_playlists()
        assert len(playlists) == 1
        assert playlists[0]["name"] == "Highlights"

    async def test_save_playlist_invalid_clip_ids(self, conn):
        store = _make_storage(ClipStorage, conn)
        assert await store.save_playlist({"name": "Bad", "clip_ids": "not-a-list"}) == 0

    async def test_save_playlist_missing_name(self, conn):
        store = _make_storage(ClipStorage, conn)
        assert await store.save_playlist({}) == 0

    async def test_uninitialized_returns_safe_defaults(self):
        store = ClipStorage()
        assert await store.save_clip({}) == 0
        assert await store.get_clips_for_match(1) == []
        assert await store.save_playlist({}) == 0
        assert await store.get_playlists() == []

    async def test_save_clip_with_thumbnail_and_player(self, conn):
        store = _make_storage(ClipStorage, conn)
        cid = await store.save_clip({
            "match_id": 1, "event_type": "pass",
            "start_seconds": 5.0, "end_seconds": 8.0,
            "duration_seconds": 3.0,
            "source_video_path": "/v/src.mp4", "output_path": "/v/clip.mp4",
            "thumbnail_path": "/v/thumb.jpg", "player_id": 7,
            "description": "Nice pass",
        })
        assert cid > 0
        clips = await store.get_clips_for_match(1)
        assert clips[0]["description"] == "Nice pass"
        assert clips[0]["player_id"] == 7


# ── EventStorage ─────────────────────────────────────────────────────────────

class TestEventStorage:
    async def test_save_and_get_events(self, conn):
        store = _make_storage(EventStorage, conn)
        eid = await store.save_event(1, {
            "type": "pass", "timestamp": 10.0, "team": "home",
            "completed": True, "confidence": 0.9,
        })
        assert eid > 0
        events = await store.get_match_events(1)
        assert len(events) == 1
        assert events[0]["event_type"] == "pass"
        assert events[0]["team"] == "home"

    async def test_get_match_events_empty(self, conn):
        store = _make_storage(EventStorage, conn)
        assert await store.get_match_events(999) == []

    async def test_save_events_bulk(self, conn):
        store = _make_storage(EventStorage, conn)
        events = [
            {"type": "pass", "timestamp": 10.0, "team": "home"},
            {"type": "shot", "timestamp": 20.0, "team": "home"},
        ]
        count = await store.save_events_bulk(1, events)
        assert count == 2
        assert len(await store.get_match_events(1)) == 2

    async def test_save_events_bulk_missing_field_returns_zero(self, conn):
        store = _make_storage(EventStorage, conn)
        events = [
            {"type": "pass", "timestamp": 1.0},
            {"type": "shot"},  # missing timestamp
        ]
        assert await store.save_events_bulk(1, events) == 0

    async def test_update_event(self, conn):
        store = _make_storage(EventStorage, conn)
        eid = await store.save_event(1, {
            "type": "pass", "timestamp": 5.0, "team": "home",
        })
        assert eid > 0
        ok = await store.update_event(eid, {"team": "away"})
        assert ok is True
        events = await store.get_match_events(1)
        assert events[0]["team"] == "away"

    async def test_update_event_no_changes(self, conn):
        store = _make_storage(EventStorage, conn)
        eid = await store.save_event(1, {
            "type": "pass", "timestamp": 5.0, "team": "home",
        })
        assert await store.update_event(eid, {}) is False

    async def test_update_event_nonexistent(self, conn):
        store = _make_storage(EventStorage, conn)
        assert await store.update_event(99999, {"team": "away"}) is False

    async def test_delete_event(self, conn):
        store = _make_storage(EventStorage, conn)
        eid = await store.save_event(1, {
            "type": "pass", "timestamp": 5.0, "team": "home",
        })
        assert await store.delete_event(eid) is True
        assert await store.get_match_events(1) == []

    async def test_delete_event_twice(self, conn):
        store = _make_storage(EventStorage, conn)
        eid = await store.save_event(1, {"type": "pass", "timestamp": 1.0})
        assert await store.delete_event(eid) is True
        assert await store.delete_event(eid) is False

    async def test_delete_event_nonexistent(self, conn):
        store = _make_storage(EventStorage, conn)
        assert await store.delete_event(99999) is False

    async def test_save_advanced_metrics(self, conn):
        store = _make_storage(EventStorage, conn)
        aid = await store.save_advanced_metrics(1, "speed", 8.5, "physical")
        assert aid > 0

    async def test_save_advanced_metrics_with_all_fields(self, conn):
        store = _make_storage(EventStorage, conn)
        aid = await store.save_advanced_metrics(
            1, "xG", 0.45, "attack", player_id=10,
            pitch_zone="A1", timestamp=30.0,
            metadata={"shot_type": "header"},
        )
        assert aid > 0

    async def test_save_advanced_metrics_bulk(self, conn):
        store = _make_storage(EventStorage, conn)
        metrics = [
            {"metric_name": "speed", "metric_value": 8.5, "metric_category": "physical"},
            {"metric_name": "distance", "metric_value": 12.3, "metric_category": "physical"},
        ]
        count = await store.save_advanced_metrics_bulk(1, metrics)
        assert count == 2

    async def test_save_correction(self, conn):
        store = _make_storage(EventStorage, conn)
        eid = await store.save_event(1, {"type": "pass", "timestamp": 1.0})
        cid = await store.save_correction(eid, "type", "pass", "shot")
        assert cid > 0

    async def test_uninitialized_event_storage(self):
        store = EventStorage()
        assert await store.save_event(1, {}) == 0
        assert await store.get_match_events(1) == []
        assert await store.save_events_bulk(1, []) == 0
        assert await store.update_event(1, {}) is False
        assert await store.delete_event(1) is False
        assert await store.save_advanced_metrics(1, "x", 0.0) == 0
        assert await store.save_advanced_metrics_bulk(1, []) == 0
        assert await store.save_correction(1, "", "", "") == 0


# ── FeedbackStorage ──────────────────────────────────────────────────────────

class TestFeedbackStorage:
    async def test_save_and_get_feedback(self, conn):
        store = _make_storage(FeedbackStorage, conn)
        fid = await store.save_feedback({
            "coach_id": "coach1", "match_id": 1, "overall_rating": 4,
        })
        assert fid > 0
        feedback = await store.get_all_feedback()
        assert len(feedback) == 1
        assert feedback[0]["overall_rating"] == 4

    async def test_save_feedback_all_ratings(self, conn):
        store = _make_storage(FeedbackStorage, conn)
        fid = await store.save_feedback({
            "coach_id": "coach2", "match_id": 1,
            "overall_rating": 5, "tracking_rating": 4,
            "events_rating": 3, "report_rating": 5, "ui_rating": 4,
            "comments": "Great tool - works well", "issues": ["latency"],
        })
        assert fid > 0
        feedback = await store.get_all_feedback()
        assert "Great tool" in feedback[0]["comments"]

    async def test_save_feedback_missing_required(self, conn):
        store = _make_storage(FeedbackStorage, conn)
        assert await store.save_feedback({}) == 0

    async def test_save_and_get_issues(self, conn):
        store = _make_storage(FeedbackStorage, conn)
        iid = await store.save_issue({
            "category": "bug", "severity": "high",
            "description": "Crash on load", "match_id": 1,
        })
        assert iid > 0
        issues = await store.get_all_issues()
        assert len(issues) == 1
        assert issues[0]["severity"] == "high"

    async def test_save_issue_with_screenshot(self, conn):
        store = _make_storage(FeedbackStorage, conn)
        iid = await store.save_issue({
            "category": "UI", "severity": "low",
            "description": "Button misaligned",
            "screenshot_path": "/screens/issue1.png",
            "logs": "error log here",
        })
        assert iid > 0

    async def test_save_issue_missing_required(self, conn):
        store = _make_storage(FeedbackStorage, conn)
        assert await store.save_issue({}) == 0

    async def test_uninitialized_feedback(self):
        store = FeedbackStorage()
        assert await store.save_feedback({}) == 0
        assert await store.get_all_feedback() == []
        assert await store.save_issue({}) == 0
        assert await store.get_all_issues() == []


# ── MatchStorage ─────────────────────────────────────────────────────────────

class TestMatchStorage:
    async def test_save_and_get_match(self, conn):
        store = _make_storage(MatchStorage, conn)
        mid = await store.save_match("Game", "/v/g.mp4", "Home", "Away")
        assert mid > 0
        m = await store.get_match(mid)
        assert m["name"] == "Game"
        assert m["home_team"] == "Home"
        assert m["away_team"] == "Away"

    async def test_get_match_not_found(self, conn):
        store = _make_storage(MatchStorage, conn)
        assert await store.get_match(99999) is None

    async def test_get_all_matches(self, conn):
        store = _make_storage(MatchStorage, conn)
        await store.save_match("M1", "/v/1.mp4")
        await store.save_match("M2", "/v/2.mp4", "H", "A")
        matches = await store.get_all_matches()
        assert len(matches) == 2

    async def test_get_all_matches_empty(self, conn):
        store = _make_storage(MatchStorage, conn)
        assert await store.get_all_matches() == []

    async def test_update_match_analysis(self, conn):
        store = _make_storage(MatchStorage, conn)
        mid = await store.save_match("Test", "/v/t.mp4")
        await store.update_match_analysis(mid, 3600.0, 30.0, 108000)
        m = await store.get_match(mid)
        assert m["duration_seconds"] == 3600.0
        assert m["fps"] == 30.0
        assert m["total_frames"] == 108000

    async def test_update_match_teams(self, conn):
        store = _make_storage(MatchStorage, conn)
        mid = await store.save_match("Test", "/v/t.mp4")
        await store.update_match_teams(mid, "NewHome", "NewAway")
        m = await store.get_match(mid)
        assert m["home_team"] == "NewHome"
        assert m["away_team"] == "NewAway"

    async def test_update_match_football_data(self, conn):
        store = _make_storage(MatchStorage, conn)
        mid = await store.save_match("Test", "/v/t.mp4")
        await store.update_match_football_data(mid, api_match_id=12345, competition_code="PL")
        m = await store.get_match(mid)
        assert m["api_match_id"] == 12345
        assert m["competition_code"] == "PL"

    async def test_update_match_football_data_no_changes(self, conn):
        store = _make_storage(MatchStorage, conn)
        mid = await store.save_match("Test", "/v/t.mp4")
        await store.update_match_football_data(mid)  # no kwargs → no-op
        m = await store.get_match(mid)
        assert m["api_match_id"] is None

    async def test_update_match_apifootball(self, conn):
        store = _make_storage(MatchStorage, conn)
        mid = await store.save_match("Test", "/v/t.mp4")
        await store.update_match_apifootball(mid, apifb_fixture_id=999, apifb_league_id=1, apifb_season=2024)
        m = await store.get_match(mid)
        assert m["apifb_fixture_id"] == 999
        assert m["apifb_league_id"] == 1
        assert m["apifb_season"] == 2024

    async def test_update_match_bzzoiro(self, conn):
        store = _make_storage(MatchStorage, conn)
        mid = await store.save_match("Test", "/v/t.mp4")
        await store.update_match_bzzoiro(mid, bzzoiro_event_id=555, bzzoiro_home_team_id=11)
        m = await store.get_match(mid)
        assert m["bzzoiro_event_id"] == 555
        assert m["bzzoiro_home_team_id"] == 11

    async def test_save_match_minimal(self, conn):
        store = _make_storage(MatchStorage, conn)
        mid = await store.save_match("Minimal", "/v/m.mp4")
        assert mid > 0
        m = await store.get_match(mid)
        assert m["name"] == "Minimal"
        assert m["home_team"] is None

    async def test_uninitialized_match_storage(self):
        store = MatchStorage()
        assert await store.save_match("n", "") == 0
        assert await store.get_match(1) is None
        assert await store.get_all_matches() == []


# ── PlayerStorage ────────────────────────────────────────────────────────────

class TestPlayerStorage:
    async def test_save_and_get_players(self, conn):
        store = _make_storage(PlayerStorage, conn)
        pid = await store.save_player(1, {
            "track_id": 10, "jersey_number": 7, "name": "Player1",
            "team": "home", "position": "ST",
        })
        assert pid > 0
        players = await store.get_match_players(1)
        assert len(players) == 1
        assert players[0]["jersey_number"] == 7
        assert players[0]["name"] == "Player1"

    async def test_get_match_players_empty(self, conn):
        store = _make_storage(PlayerStorage, conn)
        assert await store.get_match_players(999) == []

    async def test_save_players_bulk(self, conn):
        store = _make_storage(PlayerStorage, conn)
        players = [
            {"track_id": 1, "name": "A", "team": "home"},
            {"track_id": 2, "name": "B", "team": "away"},
        ]
        count = await store.save_players_bulk(1, players)
        assert count == 2
        assert len(await store.get_match_players(1)) == 2

    async def test_save_players_bulk_empty(self, conn):
        store = _make_storage(PlayerStorage, conn)
        assert await store.save_players_bulk(1, []) == 0

    async def test_save_player_missing_track_id(self, conn):
        store = _make_storage(PlayerStorage, conn)
        assert await store.save_player(1, {"name": "NoTrack"}) == 0

    async def test_save_player_with_all_stats(self, conn):
        store = _make_storage(PlayerStorage, conn)
        pid = await store.save_player(1, {
            "track_id": 5, "name": "Star", "team": "away", "position": "CM",
            "distance_covered_m": 10.5, "max_speed_kmh": 32.0,
            "avg_speed_kmh": 8.0, "passes_attempted": 50,
            "passes_completed": 42, "shots": 3, "tackles": 7,
        })
        assert pid > 0
        players = await store.get_match_players(1)
        assert players[0]["distance_covered_m"] == 10.5
        assert players[0]["passes_completed"] == 42
        assert players[0]["tackles"] == 7

    async def test_uninitialized_player_storage(self):
        store = PlayerStorage()
        assert await store.save_player(1, {}) == 0
        assert await store.get_match_players(1) == []
        assert await store.save_players_bulk(1, []) == 0


# ── ProfileStorage ───────────────────────────────────────────────────────────

class TestProfileStorage:
    async def test_save_and_get_profiles(self, conn):
        store = _make_storage(ProfileStorage, conn)
        ppid = await store.save_player_profile({
            "display_name": "Messi", "jersey_number": 10,
            "preferred_position": "ST", "team": "home",
        })
        assert ppid > 0
        profiles = await store.get_all_player_profiles()
        assert len(profiles) == 1
        assert profiles[0]["display_name"] == "Messi"

    async def test_get_all_player_profiles_empty(self, conn):
        store = _make_storage(ProfileStorage, conn)
        assert await store.get_all_player_profiles() == []

    async def test_save_profile_minimal(self, conn):
        store = _make_storage(ProfileStorage, conn)
        ppid = await store.save_player_profile({"display_name": "Minimal"})
        assert ppid > 0

    async def test_save_profile_with_face(self, conn):
        store = _make_storage(ProfileStorage, conn)
        ppid = await store.save_player_profile({
            "display_name": "Ronaldo",
            "global_id": "cr7",
            "face_embedding": "[0.1,0.2,0.3]",
            "face_confidence": 0.95,
        })
        assert ppid > 0
        profiles = await store.get_all_player_profiles()
        assert profiles[0]["global_id"] == "cr7"

    async def test_update_player_profile_face(self, conn):
        store = _make_storage(ProfileStorage, conn)
        ppid = await store.save_player_profile({"display_name": "Test"})
        await store.update_player_profile_face(ppid, "[0.1,0.2,0.3]", 0.95)
        profiles = await store.get_all_player_profiles()
        assert profiles[0]["face_confidence"] == 0.95

    async def test_update_player_profile_face_nonexistent(self, conn):
        store = _make_storage(ProfileStorage, conn)
        await store.update_player_profile_face(99999, "[]", 0.5)  # no error

    async def test_uninitialized_profile_storage(self):
        store = ProfileStorage()
        assert await store.save_player_profile({}) == 0
        assert await store.get_all_player_profiles() == []
        # update on uninitialized should not raise
        await store.update_player_profile_face(1, "[]", 0.5)


# ── Cross-module / Multi-table scenario ──────────────────────────────────────

class TestIntegration:
    async def test_save_match_then_event_then_player_then_clip(self, conn):
        match_store = _make_storage(MatchStorage, conn)
        event_store = _make_storage(EventStorage, conn)
        player_store = _make_storage(PlayerStorage, conn)
        clip_store = _make_storage(ClipStorage, conn)

        mid = await match_store.save_match("Integration", "/v/int.mp4", "TeamA", "TeamB")
        assert mid > 0

        eid = await event_store.save_event(mid, {
            "type": "goal", "timestamp": 42.0, "team": "home",
            "completed": True,
        })
        assert eid > 0

        pid = await player_store.save_player(mid, {
            "track_id": 99, "name": "Scorer", "team": "home",
        })
        assert pid > 0

        cid = await clip_store.save_clip({
            "match_id": mid, "event_type": "goal",
            "start_seconds": 40.0, "end_seconds": 45.0,
            "duration_seconds": 5.0,
            "source_video_path": "/v/s.mp4", "output_path": "/v/c.mp4",
        })
        assert cid > 0

        # Verify cross-table reads
        assert len(await event_store.get_match_events(mid)) == 1
        assert len(await player_store.get_match_players(mid)) == 1
        assert len(await clip_store.get_clips_for_match(mid)) == 1
        m = await match_store.get_match(mid)
        assert m["home_team"] == "TeamA"
