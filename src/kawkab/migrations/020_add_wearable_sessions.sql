-- Migration 020: Add wearable_sessions table
-- Persists parsed wearable sessions (Catapult, STATSports, Polar, FIT, TCX)
-- for later analysis, fusion with video, and historical dashboard views.

CREATE TABLE IF NOT EXISTS wearable_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        INTEGER,
    athlete_id      TEXT,
    athlete_name    TEXT,
    device_type     TEXT NOT NULL,           -- 'catapult', 'statsports', 'polar', 'fit', 'tcx'
    device_serial   TEXT,
    start_time      TEXT,                    -- ISO 8601
    duration_s      REAL DEFAULT 0.0,
    sample_rate_hz  REAL DEFAULT 0.0,
    avg_hr          REAL,
    max_hr          REAL,
    min_hr          REAL,
    total_distance_m REAL DEFAULT 0.0,
    max_speed_ms    REAL,
    avg_speed_ms    REAL,
    player_load     REAL,
    body_load       REAL,
    high_speed_running_m REAL DEFAULT 0.0,
    sprint_distance_m    REAL DEFAULT 0.0,
    accelerations   INTEGER DEFAULT 0,
    decelerations   INTEGER DEFAULT 0,
    point_count     INTEGER DEFAULT 0,
    metadata_json   TEXT,                    -- JSON blob for vendor-specific extras
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_wearable_sessions_match ON wearable_sessions(match_id);
CREATE INDEX IF NOT EXISTS idx_wearable_sessions_device ON wearable_sessions(device_type);
CREATE INDEX IF NOT EXISTS idx_wearable_sessions_athlete ON wearable_sessions(athlete_id);
