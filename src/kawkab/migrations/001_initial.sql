-- Migration 001: Initial database schema
-- This matches the schema created by StorageService._create_tables()

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    video_path TEXT NOT NULL,
    home_team TEXT,
    away_team TEXT,
    match_date TIMESTAMP,
    duration_seconds REAL,
    fps REAL,
    total_frames INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analyzed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    track_id INTEGER NOT NULL,
    jersey_number INTEGER,
    name TEXT,
    team TEXT,
    position TEXT,
    distance_covered_m REAL,
    max_speed_kmh REAL,
    avg_speed_kmh REAL,
    passes_attempted INTEGER DEFAULT 0,
    passes_completed INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    tackles INTEGER DEFAULT 0,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    timestamp REAL NOT NULL,
    from_track_id INTEGER,
    to_track_id INTEGER,
    team TEXT,
    completed BOOLEAN,
    confidence REAL,
    metadata TEXT,
    user_corrected BOOLEAN DEFAULT 0,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    possession_home REAL,
    possession_away REAL,
    passes_home INTEGER,
    passes_away INTEGER,
    shots_home INTEGER,
    shots_away INTEGER,
    confidence_overall REAL,
    full_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    report_text TEXT NOT NULL,
    llm_provider TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    correction_type TEXT NOT NULL,
    original_value TEXT,
    corrected_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
