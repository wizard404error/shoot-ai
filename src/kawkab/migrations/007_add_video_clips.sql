-- Migration 007: Add video clips and playlists tables for v0.8.2

CREATE TABLE IF NOT EXISTS video_clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    duration_seconds REAL NOT NULL,
    source_video_path TEXT NOT NULL,
    output_path TEXT NOT NULL,
    thumbnail_path TEXT,
    player_id INTEGER,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clip_playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    clip_ids TEXT NOT NULL, -- JSON array
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clips_match ON video_clips(match_id);
CREATE INDEX IF NOT EXISTS idx_clips_event ON video_clips(event_type);
