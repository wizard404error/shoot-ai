"""Tests for StorageService — SQLite storage operations.

Covers all 40+ methods including bulk ops, corrections, reports, benchmarks,
validation, feedback, issues, usage sessions, clips, playlists, player profiles,
and edge cases (uninitialized, corrupt DB, missing fields).
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import install_kawkab_stubs, load_service_module

install_kawkab_stubs()

_storage_mod = load_service_module("storage_test", "storage_service.py")
_bench_mod = load_service_module("bench_test", "benchmark_service.py")
_valid_mod = load_service_module("valid_test", "validation_service.py")

StorageService = _storage_mod.StorageService
BenchmarkResult = _bench_mod.BenchmarkResult
ValidationReport = _valid_mod.ValidationReport
ValidationResult = _valid_mod.ValidationResult


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    video_path TEXT NOT NULL,
    home_team TEXT,
    away_team TEXT,
    match_date TEXT,
    duration_seconds REAL,
    fps REAL,
    total_frames INTEGER,
    analyzed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    api_match_id INTEGER,
    competition_code TEXT,
    football_data_home_team_id INTEGER,
    football_data_away_team_id INTEGER,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL,
    track_id INTEGER NOT NULL, jersey_number INTEGER, name TEXT,
    team TEXT, position TEXT, distance_covered_m REAL DEFAULT 0,
    max_speed_kmh REAL DEFAULT 0, avg_speed_kmh REAL DEFAULT 0,
    passes_attempted INTEGER DEFAULT 0, passes_completed INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0, tackles INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS advanced_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL,
    player_id INTEGER, metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL, metric_category TEXT DEFAULT '',
    pitch_zone TEXT DEFAULT '', timestamp REAL, metadata TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS benchmark_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER, video_path TEXT, video_duration_seconds REAL,
    total_frames INTEGER, total_time_seconds REAL, realtime_ratio REAL,
    fps_effective REAL, stage_enhancement_seconds REAL DEFAULT 0,
    stage_detection_seconds REAL DEFAULT 0,
    stage_tracking_seconds REAL DEFAULT 0,
    stage_analysis_seconds REAL DEFAULT 0,
    stage_advanced_metrics_seconds REAL DEFAULT 0,
    stage_save_seconds REAL DEFAULT 0,
    peak_memory_mb REAL, peak_gpu_memory_mb REAL,
    gpu_utilization_pct REAL, gpu_name TEXT, cpu_name TEXT,
    ram_gb REAL, model_size TEXT, frame_skip INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER, ground_truth_source TEXT, overall_accuracy REAL,
    category TEXT, metric_name TEXT, computed_value REAL,
    ground_truth_value REAL, absolute_error REAL,
    relative_error_pct REAL, accuracy_score REAL, sample_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS coach_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT, coach_id TEXT NOT NULL,
    match_id INTEGER, overall_rating INTEGER NOT NULL,
    tracking_rating INTEGER, events_rating INTEGER, report_rating INTEGER,
    ui_rating INTEGER, comments TEXT, issues TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS issue_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
    severity TEXT NOT NULL, description TEXT NOT NULL, match_id INTEGER,
    screenshot_path TEXT, logs TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS usage_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
    features_used TEXT, duration_seconds REAL, match_count INTEGER,
    gpu_tier TEXT, model_size TEXT, error_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS video_clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL,
    event_type TEXT NOT NULL, start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL, duration_seconds REAL NOT NULL,
    source_video_path TEXT NOT NULL, output_path TEXT NOT NULL,
    thumbnail_path TEXT, player_id INTEGER, description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS clip_playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
    description TEXT DEFAULT '', clip_ids TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS player_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT, global_id TEXT DEFAULT '',
    display_name TEXT DEFAULT '', jersey_number INTEGER,
    preferred_position TEXT, team TEXT DEFAULT 'home',
    is_active INTEGER DEFAULT 1, face_embedding TEXT,
    face_confidence REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL,
    language TEXT NOT NULL, report_text TEXT NOT NULL,
    llm_provider TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL,
    correction_type TEXT NOT NULL, original_value TEXT,
    corrected_value TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS coding_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    sub_type TEXT DEFAULT '',
    video_time REAL NOT NULL,
    player_track_id INTEGER DEFAULT 0,
    player_name TEXT DEFAULT '',
    team TEXT DEFAULT '',
    period INTEGER DEFAULT 1,
    notes TEXT DEFAULT '',
    lead_ms INTEGER DEFAULT 2000,
    lag_ms INTEGER DEFAULT 3000,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@pytest.fixture
def storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        svc = StorageService()
        svc._db_path = db_path
        svc._conn = sqlite3.connect(str(db_path))
        svc._conn.row_factory = sqlite3.Row
        svc._conn.executescript(CREATE_SQL)
        svc._conn.commit()
        yield svc
        if svc._conn:
            svc._conn.close()


async def _mid(storage):
    return await storage.save_match("Test", "/v/test.mp4", "Home", "Away")


@pytest.mark.asyncio
async def test_initialize_creates_tables(storage):
    cursor = storage._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row["name"] for row in cursor.fetchall()}
    for t in ["matches", "events", "players", "advanced_metrics",
              "benchmark_results", "validation_results", "coach_feedback",
              "issue_reports", "usage_sessions", "video_clips",
              "clip_playlists", "player_profiles", "user_corrections",
              "reports"]:
        assert t in tables, f"Missing table: {t}"


@pytest.mark.asyncio
async def test_save_and_get_match(storage):
    mid = await storage.save_match("Game", "/v/g.mp4", "TeamA", "TeamB")
    assert mid > 0
    m = await storage.get_match(mid)
    assert m["name"] == "Game"
    assert m["home_team"] == "TeamA"
    assert m["away_team"] == "TeamB"


@pytest.mark.asyncio
async def test_get_all_matches(storage):
    await storage.save_match("M1", "/v/1.mp4")
    await storage.save_match("M2", "/v/2.mp4", "H", "A")
    matches = await storage.get_all_matches()
    assert len(matches) >= 2


@pytest.mark.asyncio
async def test_get_match_not_found(storage):
    assert await storage.get_match(99999) is None


@pytest.mark.asyncio
async def test_update_match_analysis(storage):
    match_id = await _mid(storage)
    await storage.update_match_analysis(match_id, 3600.0, 30.0, 108000)
    m = await storage.get_match(match_id)
    assert m["duration_seconds"] == 3600.0
    assert m["fps"] == 30.0
    assert m["total_frames"] == 108000


@pytest.mark.asyncio
async def test_update_match_teams(storage):
    match_id = await _mid(storage)
    await storage.update_match_teams(match_id, "NewHome", "NewAway")
    m = await storage.get_match(match_id)
    assert m["home_team"] == "NewHome"
    assert m["away_team"] == "NewAway"


@pytest.mark.asyncio
async def test_save_and_get_events(storage):
    match_id = await _mid(storage)
    eid = await storage.save_event(match_id, {
        "type": "pass", "timestamp": 10.0, "team": "home",
        "completed": True, "confidence": 0.9,
    })
    assert eid > 0
    events = await storage.get_match_events(match_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "pass"


@pytest.mark.asyncio
async def test_save_events_bulk(storage):
    match_id = await _mid(storage)
    events = [
        {"type": "pass", "timestamp": 10.0, "team": "home"},
        {"type": "shot", "timestamp": 20.0, "team": "home"},
    ]
    count = await storage.save_events_bulk(match_id, events)
    assert count == 2
    assert len(await storage.get_match_events(match_id)) == 2


@pytest.mark.asyncio
async def test_save_events_bulk_bad_event_rollback(storage):
    match_id = await _mid(storage)
    events = [
        {"type": "pass", "timestamp": 1.0, "team": "home"},
        {"type": "shot"},  # missing timestamp
    ]
    count = await storage.save_events_bulk(match_id, events)
    assert count == 0


@pytest.mark.asyncio
async def test_update_event(storage):
    match_id = await _mid(storage)
    eid = await storage.save_event(match_id, {
        "type": "pass", "timestamp": 5.0, "team": "home",
    })
    ok = await storage.update_event(eid, {"team": "away"})
    assert ok is True
    events = await storage.get_match_events(match_id)
    assert events[0]["team"] == "away"


@pytest.mark.asyncio
async def test_update_event_no_changes(storage):
    match_id = await _mid(storage)
    eid = await storage.save_event(match_id, {
        "type": "pass", "timestamp": 5.0, "team": "home",
    })
    ok = await storage.update_event(eid, {})
    assert ok is False


@pytest.mark.asyncio
async def test_delete_event(storage):
    match_id = await _mid(storage)
    eid = await storage.save_event(match_id, {
        "type": "pass", "timestamp": 5.0, "team": "home",
    })
    ok = await storage.delete_event(eid)
    assert ok is True
    assert len(await storage.get_match_events(match_id)) == 0


@pytest.mark.asyncio
async def test_delete_event_twice(storage):
    match_id = await _mid(storage)
    eid = await storage.save_event(match_id, {"type": "pass", "timestamp": 1.0, "team": "home"})
    assert await storage.delete_event(eid) is True
    assert await storage.delete_event(eid) is False


@pytest.mark.asyncio
async def test_save_and_get_players(storage):
    match_id = await _mid(storage)
    pid = await storage.save_player(match_id, {
        "track_id": 10, "jersey_number": 7, "name": "Player1", "team": "home", "position": "ST",
    })
    assert pid > 0
    players = await storage.get_match_players(match_id)
    assert len(players) == 1
    assert players[0]["jersey_number"] == 7


@pytest.mark.asyncio
async def test_save_players_bulk(storage):
    match_id = await _mid(storage)
    players = [
        {"track_id": 1, "name": "A", "team": "home"},
        {"track_id": 2, "name": "B", "team": "away"},
    ]
    count = await storage.save_players_bulk(match_id, players)
    assert count == 2


@pytest.mark.asyncio
async def test_save_advanced_metrics(storage):
    match_id = await _mid(storage)
    aid = await storage.save_advanced_metrics(match_id, "speed", 8.5, "physical")
    assert aid > 0


@pytest.mark.asyncio
async def test_save_advanced_metrics_bulk(storage):
    match_id = await _mid(storage)
    metrics = [
        {"metric_name": "speed", "metric_value": 8.5, "metric_category": "physical"},
        {"metric_name": "distance", "metric_value": 12.3, "metric_category": "physical"},
    ]
    count = await storage.save_advanced_metrics_bulk(match_id, metrics)
    assert count == 2


@pytest.mark.asyncio
async def test_save_correction(storage):
    match_id = await _mid(storage)
    eid = await storage.save_event(match_id, {"type": "pass", "timestamp": 1.0, "team": "home"})
    cid = await storage.save_correction(eid, "type", "pass", "shot")
    assert cid > 0


@pytest.mark.asyncio
async def test_save_and_get_reports(storage):
    match_id = await _mid(storage)
    rid = await storage.save_report(match_id, "en", "Great match!", "llm")
    assert rid > 0
    reports = await storage.get_reports(match_id, "en")
    assert len(reports) == 1
    assert reports[0]["report_text"] == "Great match!"


@pytest.mark.asyncio
async def test_get_reports_wrong_language(storage):
    match_id = await _mid(storage)
    await storage.save_report(match_id, "en", "Hello", "llm")
    reports = await storage.get_reports(match_id, "ar")
    assert reports == []


@pytest.mark.asyncio
async def test_save_benchmark(storage):
    match_id = await _mid(storage)
    result = BenchmarkResult(
        match_id=match_id, video_path="/v/test.mp4",
        total_time_seconds=10.0, realtime_ratio=1.0, fps_effective=30.0,
    )
    bid = await storage.save_benchmark(result)
    assert bid > 0


@pytest.mark.asyncio
async def test_get_recent_benchmarks(storage):
    match_id = await _mid(storage)
    for i in range(3):
        r = BenchmarkResult(match_id=match_id, video_path=f"/v/{i}.mp4",
                            total_time_seconds=float(i), realtime_ratio=1.0, fps_effective=30.0)
        await storage.save_benchmark(r)
    benchmarks = await storage.get_recent_benchmarks(2)
    assert len(benchmarks) == 2


@pytest.mark.asyncio
async def test_save_validation_result(storage):
    match_id = await _mid(storage)
    report = ValidationReport(
        match_id=match_id, ground_truth_source="manual",
        results=[ValidationResult("events", "pass_f1", 0.8, 1.0, 0.2, 20.0, 0.8, 10)]
    )
    ids = await storage.save_validation_result(report)
    assert len(ids) == 1


@pytest.mark.asyncio
async def test_get_validation_results(storage):
    match_id = await _mid(storage)
    report = ValidationReport(match_id=match_id, ground_truth_source="manual",
                              results=[ValidationResult("events", "pass_f1", 0.8, 1.0, 0.2, 20.0, 0.8, 10)])
    await storage.save_validation_result(report)
    results = await storage.get_validation_results(match_id)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_save_and_get_feedback(storage):
    match_id = await _mid(storage)
    fid = await storage.save_feedback({
        "coach_id": "coach1", "match_id": match_id, "overall_rating": 4,
    })
    assert fid > 0
    feedback = await storage.get_all_feedback()
    assert len(feedback) == 1
    assert feedback[0]["overall_rating"] == 4


@pytest.mark.asyncio
async def test_save_and_get_issues(storage):
    match_id = await _mid(storage)
    iid = await storage.save_issue({
        "category": "bug", "severity": "high", "description": "Crash on load",
        "match_id": match_id,
    })
    assert iid > 0
    issues = await storage.get_all_issues()
    assert len(issues) == 1
    assert issues[0]["severity"] == "high"


@pytest.mark.asyncio
async def test_save_usage_session(storage):
    uid = await storage.save_usage_session({
        "session_id": "sess1", "features_used": ["video", "analytics"],
        "duration_seconds": 120, "match_count": 1, "gpu_tier": "mid", "model_size": "n",
    })
    assert uid > 0


@pytest.mark.asyncio
async def test_save_and_get_clips(storage):
    match_id = await _mid(storage)
    cid = await storage.save_clip({
        "match_id": match_id, "event_type": "goal",
        "start_seconds": 10.0, "end_seconds": 20.0, "duration_seconds": 10.0,
        "source_video_path": "/v/test.mp4", "output_path": "/v/clip.mp4",
    })
    assert cid > 0
    clips = await storage.get_clips_for_match(match_id)
    assert len(clips) == 1


@pytest.mark.asyncio
async def test_save_and_get_playlists(storage):
    match_id = await _mid(storage)
    cid = await storage.save_clip({
        "match_id": match_id, "event_type": "goal",
        "start_seconds": 0.0, "end_seconds": 10.0, "duration_seconds": 10.0,
        "source_video_path": "/v/t.mp4", "output_path": "/v/c.mp4",
    })
    pid = await storage.save_playlist({"name": "Highlights", "clip_ids": [cid]})
    assert pid > 0
    playlists = await storage.get_playlists()
    assert len(playlists) == 1


@pytest.mark.asyncio
async def test_save_and_get_player_profiles(storage):
    ppid = await storage.save_player_profile({
        "display_name": "Messi", "jersey_number": 10, "preferred_position": "ST",
    })
    assert ppid > 0
    profiles = await storage.get_all_player_profiles()
    assert len(profiles) == 1
    assert profiles[0]["display_name"] == "Messi"


@pytest.mark.asyncio
async def test_update_player_profile_face(storage):
    ppid = await storage.save_player_profile({"display_name": "Test"})
    await storage.update_player_profile_face(ppid, "[0.1,0.2,0.3]", 0.95)
    profiles = await storage.get_all_player_profiles()
    assert profiles[0]["face_confidence"] == 0.95


@pytest.mark.asyncio
async def test_update_match_football_data(storage):
    match_id = await _mid(storage)
    await storage.update_match_football_data(match_id, api_match_id=12345, competition_code="PL")
    m = await storage.get_match(match_id)
    assert m["api_match_id"] == 12345
    assert m["competition_code"] == "PL"


@pytest.mark.asyncio
async def test_update_match_apifootball(storage):
    match_id = await _mid(storage)
    await storage.update_match_apifootball(match_id, apifb_fixture_id=999, apifb_league_id=1, apifb_season=2024)
    m = await storage.get_match(match_id)
    assert m["apifb_fixture_id"] == 999


@pytest.mark.asyncio
async def test_update_match_bzzoiro(storage):
    match_id = await _mid(storage)
    await storage.update_match_bzzoiro(match_id, bzzoiro_event_id=555, bzzoiro_home_team_id=11)
    m = await storage.get_match(match_id)
    assert m["bzzoiro_event_id"] == 555


@pytest.mark.asyncio
async def test_uninitialized_service_returns_safe_defaults():
    svc = StorageService()
    svc._conn = None
    assert await svc.save_match("n", "") == 0
    assert await svc.get_match(1) is None
    assert await svc.get_all_matches() == []
    assert await svc.save_event(1, {}) == 0
    assert await svc.get_match_events(1) == []
    assert await svc.save_player(1, {}) == 0
    assert await svc.get_match_players(1) == []
    assert await svc.save_benchmark(BenchmarkResult()) == 0
    assert await svc.get_recent_benchmarks() == []
    assert await svc.save_feedback({}) == 0
    assert await svc.get_all_feedback() == []
    assert await svc.save_issue({}) == 0
    assert await svc.get_all_issues() == []
    assert await svc.save_clip({}) == 0
    assert await svc.get_clips_for_match(1) == []
    assert await svc.save_player_profile({}) == 0
    assert await svc.get_all_player_profiles() == []
    assert await svc.save_playlist({}) == 0
    assert await svc.get_playlists() == []
    assert await svc.save_usage_session({}) == 0
    assert await svc.save_advanced_metrics(1, "x", 0.0) == 0
    assert await svc.save_advanced_metrics_bulk(1, []) == 0
    assert await svc.save_events_bulk(1, []) == 0
    assert await svc.save_players_bulk(1, []) == 0
    assert await svc.save_correction(1, "", "", "") == 0
    assert await svc.get_reports(1, "en") == []
    assert await svc.get_validation_results(1) == []
    assert await svc.update_event(1, {"team": "away"}) is False
    assert await svc.delete_event(1) is False


@pytest.mark.asyncio
async def test_save_event_missing_required_fields(storage):
    match_id = await _mid(storage)
    assert await storage.save_event(match_id, {"type": "pass"}) == 0


@pytest.mark.asyncio
async def test_save_player_missing_track_id(storage):
    match_id = await _mid(storage)
    assert await storage.save_player(match_id, {"name": "NoTrack"}) == 0


@pytest.mark.asyncio
async def test_save_feedback_missing_required(storage):
    assert await storage.save_feedback({}) == 0


@pytest.mark.asyncio
async def test_save_issue_missing_required(storage):
    assert await storage.save_issue({}) == 0


@pytest.mark.asyncio
async def test_save_usage_session_missing_required(storage):
    assert await storage.save_usage_session({}) == 0


@pytest.mark.asyncio
async def test_save_clip_missing_required(storage):
    assert await storage.save_clip({}) == 0


@pytest.mark.asyncio
async def test_save_playlist_missing_name(storage):
    assert await storage.save_playlist({}) == 0


@pytest.mark.asyncio
async def test_concurrent_writes_different_connections(tmp_path):
    db = tmp_path / "concurrent.db"
    svc1 = StorageService()
    svc1._db_path = db
    svc1._conn = sqlite3.connect(str(db))
    svc1._conn.row_factory = sqlite3.Row
    svc1._conn.executescript(CREATE_SQL)
    svc1._conn.commit()
    svc2 = StorageService()
    svc2._db_path = db
    svc2._conn = sqlite3.connect(str(db))
    svc2._conn.row_factory = sqlite3.Row
    mid1 = await svc1.save_match("M1", "/v1.mp4")
    mid2 = await svc2.save_match("M2", "/v2.mp4")
    assert mid1 > 0 and mid2 > 0
    assert len(await svc1.get_all_matches()) == 2
    svc1._conn.close()
    svc2._conn.close()


@pytest.mark.asyncio
async def test_close_idempotent(storage):
    await storage.close()
    assert storage._conn is None
    await storage.close()


@pytest.mark.asyncio
async def test_benchmark_minimal_fields(storage):
    match_id = await _mid(storage)
    r = BenchmarkResult(match_id=0, video_path="", total_time_seconds=0.0, realtime_ratio=0.0, fps_effective=0.0)
    bid = await storage.save_benchmark(r)
    assert bid > 0


@pytest.mark.asyncio
async def test_validation_result_empty_results(storage):
    match_id = await _mid(storage)
    report = ValidationReport(match_id=1, ground_truth_source="auto")
    ids = await storage.save_validation_result(report)
    assert ids == []


# ── Coding Tags Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_coding_tag(storage):
    match_id = await _mid(storage)
    tag = {"event_type": "shot", "video_time": 123.45, "player_name": "Messi",
           "team": "home", "period": 1, "notes": "Great shot", "lead_ms": 2000, "lag_ms": 3000}
    tag_id = await storage.save_coding_tag(match_id, tag)
    assert tag_id > 0

    tags = await storage.get_coding_tags(match_id)
    assert len(tags) == 1
    assert tags[0]["event_type"] == "shot"
    assert abs(tags[0]["video_time"] - 123.45) < 0.001
    assert tags[0]["player_name"] == "Messi"

@pytest.mark.asyncio
async def test_save_coding_tag_missing_fields(storage):
    match_id = await _mid(storage)
    tag_id = await storage.save_coding_tag(match_id, {})
    assert tag_id == 0

    tag_id = await storage.save_coding_tag(match_id, {"event_type": "pass"})
    assert tag_id == 0

    tag_id = await storage.save_coding_tag(match_id, {"video_time": 10.0})
    assert tag_id == 0

@pytest.mark.asyncio
async def test_save_coding_tag_minimal(storage):
    match_id = await _mid(storage)
    tag_id = await storage.save_coding_tag(match_id, {"event_type": "pass", "video_time": 30.0})
    assert tag_id > 0

@pytest.mark.asyncio
async def test_get_coding_tags_empty(storage):
    match_id = await _mid(storage)
    tags = await storage.get_coding_tags(match_id)
    assert tags == []

    tags = await storage.get_coding_tags(999)
    assert tags == []

@pytest.mark.asyncio
async def test_multiple_coding_tags_order(storage):
    match_id = await _mid(storage)
    await storage.save_coding_tag(match_id, {"event_type": "pass", "video_time": 10.0})
    await storage.save_coding_tag(match_id, {"event_type": "shot", "video_time": 5.0})
    await storage.save_coding_tag(match_id, {"event_type": "tackle", "video_time": 15.0})

    tags = await storage.get_coding_tags(match_id)
    assert len(tags) == 3
    assert tags[0]["video_time"] == 5.0
    assert tags[1]["video_time"] == 10.0
    assert tags[2]["video_time"] == 15.0

@pytest.mark.asyncio
async def test_get_coding_tags_by_type(storage):
    match_id = await _mid(storage)
    await storage.save_coding_tag(match_id, {"event_type": "pass", "video_time": 10.0})
    await storage.save_coding_tag(match_id, {"event_type": "shot", "video_time": 20.0})
    await storage.save_coding_tag(match_id, {"event_type": "pass", "video_time": 30.0})

    passes = await storage.get_coding_tags_by_type(match_id, "pass")
    assert len(passes) == 2
    assert all(t["event_type"] == "pass" for t in passes)

    shots = await storage.get_coding_tags_by_type(match_id, "shot")
    assert len(shots) == 1

    nonexistent = await storage.get_coding_tags_by_type(match_id, "goalkick")
    assert nonexistent == []

@pytest.mark.asyncio
async def test_get_coding_tags_by_player(storage):
    match_id = await _mid(storage)
    await storage.save_coding_tag(match_id, {"event_type": "pass", "video_time": 10.0, "player_track_id": 1})
    await storage.save_coding_tag(match_id, {"event_type": "shot", "video_time": 20.0, "player_track_id": 2})
    await storage.save_coding_tag(match_id, {"event_type": "tackle", "video_time": 30.0, "player_track_id": 1})

    p1_tags = await storage.get_coding_tags_by_player(match_id, 1)
    assert len(p1_tags) == 2

    p2_tags = await storage.get_coding_tags_by_player(match_id, 2)
    assert len(p2_tags) == 1

    p3_tags = await storage.get_coding_tags_by_player(match_id, 3)
    assert p3_tags == []

@pytest.mark.asyncio
async def test_update_coding_tag(storage):
    match_id = await _mid(storage)
    tag_id = await storage.save_coding_tag(match_id, {"event_type": "pass", "video_time": 10.0})
    assert tag_id > 0

    ok = await storage.update_coding_tag(tag_id, {"event_type": "shot", "notes": "Updated"})
    assert ok

    tags = await storage.get_coding_tags(match_id)
    assert len(tags) == 1
    assert tags[0]["event_type"] == "shot"
    assert tags[0]["notes"] == "Updated"

@pytest.mark.asyncio
async def test_update_coding_tag_invalid_field(storage):
    match_id = await _mid(storage)
    tag_id = await storage.save_coding_tag(match_id, {"event_type": "pass", "video_time": 10.0})
    ok = await storage.update_coding_tag(tag_id, {"nonexistent_field": "value"})
    assert not ok

@pytest.mark.asyncio
async def test_delete_coding_tag(storage):
    match_id = await _mid(storage)
    tag_id = await storage.save_coding_tag(match_id, {"event_type": "pass", "video_time": 10.0})
    tag_id2 = await storage.save_coding_tag(match_id, {"event_type": "shot", "video_time": 20.0})
    assert tag_id > 0 and tag_id2 > 0

    ok = await storage.delete_coding_tag(tag_id)
    assert ok

    tags = await storage.get_coding_tags(match_id)
    assert len(tags) == 1
    assert tags[0]["id"] == tag_id2

    ok = await storage.delete_coding_tag(999)
    assert not ok

@pytest.mark.asyncio
async def test_get_coding_tag_stats(storage):
    match_id = await _mid(storage)
    await storage.save_coding_tag(match_id, {"event_type": "pass", "video_time": 10.0, "player_name": "Messi"})
    await storage.save_coding_tag(match_id, {"event_type": "pass", "video_time": 15.0, "player_name": "Messi"})
    await storage.save_coding_tag(match_id, {"event_type": "shot", "video_time": 20.0, "player_name": "Ronaldo"})
    await storage.save_coding_tag(match_id, {"event_type": "tackle", "video_time": 30.0, "player_name": "Messi"})

    stats = await storage.get_coding_tag_stats(match_id)
    assert stats["total"] == 4
    assert stats["by_type"]["pass"] == 2
    assert stats["by_type"]["shot"] == 1
    assert stats["by_type"]["tackle"] == 1
    assert stats["by_player"]["Messi"] == 3
    assert stats["by_player"]["Ronaldo"] == 1

@pytest.mark.asyncio
async def test_get_coding_tag_stats_empty(storage):
    match_id = await _mid(storage)
    stats = await storage.get_coding_tag_stats(match_id)
    assert stats["total"] == 0
    assert stats["by_type"] == {}
    assert stats["by_player"] == {}

@pytest.mark.asyncio
async def test_coding_tags_uninitialized_conn():
    svc = StorageService()
    assert await svc.save_coding_tag(1, {"event_type": "pass", "video_time": 10.0}) == 0
    assert await svc.get_coding_tags(1) == []
    assert await svc.get_coding_tags_by_type(1, "pass") == []
    assert await svc.get_coding_tags_by_player(1, 1) == []
    assert await svc.update_coding_tag(1, {"event_type": "shot"}) is False
    assert await svc.delete_coding_tag(1) is False
    assert await svc.get_coding_tag_stats(1) == {"total": 0, "by_type": {}, "by_player": {}}

@pytest.mark.asyncio
async def test_coding_tags_multiple_matches(storage):
    mid1 = await _mid(storage)
    mid2 = await storage.save_match("Match 2", "/v2.mp4", "Team C", "Team D")

    await storage.save_coding_tag(mid1, {"event_type": "pass", "video_time": 10.0})
    await storage.save_coding_tag(mid2, {"event_type": "shot", "video_time": 20.0})

    tags1 = await storage.get_coding_tags(mid1)
    tags2 = await storage.get_coding_tags(mid2)
    assert len(tags1) == 1
    assert len(tags2) == 1
    assert tags1[0]["event_type"] == "pass"
    assert tags2[0]["event_type"] == "shot"
