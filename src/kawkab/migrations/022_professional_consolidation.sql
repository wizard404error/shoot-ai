-- Migration 022: Professional consolidation
-- 1. Encryption key store for medical data at rest
-- 2. Tracking frames table (persist per-frame positional data)
-- 3. Normalized teams table + FKs

CREATE TABLE IF NOT EXISTS encryption_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name TEXT UNIQUE NOT NULL,
    key_value TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    rotated_at TEXT
);

INSERT OR IGNORE INTO encryption_keys (key_name, key_value)
VALUES ('medical_v1', hex(randomblob(32)));

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    short_name TEXT,
    home_color TEXT DEFAULT '#1e7e34',
    away_color TEXT DEFAULT '#ffffff',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tracking_frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    frame_number INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    player_detections TEXT DEFAULT '[]',
    ball_detections TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
    UNIQUE(match_id, frame_number)
);

CREATE INDEX IF NOT EXISTS idx_tracking_frames_match ON tracking_frames(match_id);
CREATE INDEX IF NOT EXISTS idx_tracking_frames_range ON tracking_frames(match_id, frame_number);

-- 4. Link matches to teams
ALTER TABLE matches ADD COLUMN home_team_id INTEGER REFERENCES teams(id);
ALTER TABLE matches ADD COLUMN away_team_id INTEGER REFERENCES teams(id);
CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_id);

INSERT OR REPLACE INTO schema_version (version) VALUES (22);
