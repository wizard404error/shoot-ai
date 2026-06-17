-- Migration 002: Add professional analytics tables
-- Seasons, player profiles, match comparisons, advanced metrics, quality scoring

-- Seasons table for organizing matches by season/competition
CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    team_name TEXT,
    competition TEXT,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Link matches to seasons
ALTER TABLE matches ADD COLUMN season_id INTEGER;
ALTER TABLE matches ADD COLUMN competition TEXT;
ALTER TABLE matches ADD COLUMN round TEXT;
ALTER TABLE matches ADD COLUMN opponent TEXT;
ALTER TABLE matches ADD COLUMN score_home INTEGER;
ALTER TABLE matches ADD COLUMN score_away INTEGER;
ALTER TABLE matches ADD COLUMN match_type TEXT DEFAULT 'unknown';

-- Player profiles (persistent identity across matches)
CREATE TABLE IF NOT EXISTS player_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    global_id TEXT UNIQUE NOT NULL,  -- e.g., "team_jersey_7" or UUID
    display_name TEXT,
    jersey_number INTEGER,
    preferred_position TEXT,
    height_cm INTEGER,
    weight_kg INTEGER,
    dominant_foot TEXT,
    date_of_birth TIMESTAMP,
    nationality TEXT,
    photo_path TEXT,
    team TEXT DEFAULT 'home',
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Link match players to persistent profiles
CREATE TABLE IF NOT EXISTS player_match_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    track_id INTEGER,
    confidence REAL DEFAULT 0.0,  -- match confidence (0-1)
    is_verified BOOLEAN DEFAULT 0,  -- user confirmed this link
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES player_profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
    UNIQUE(player_id, match_id)
);

-- Advanced metrics per match (structured, queryable)
CREATE TABLE IF NOT EXISTS advanced_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    player_id INTEGER,  -- NULL for team-level metrics
    metric_name TEXT NOT NULL,
    metric_value REAL,
    metric_category TEXT,  -- e.g., 'passing', 'defending', 'physical'
    pitch_zone TEXT,  -- e.g., 'defensive_third', 'middle_third', 'final_third'
    timestamp REAL,
    metadata TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES player_profiles(id) ON DELETE SET NULL
);

-- Match comparisons (saved comparison configurations)
CREATE TABLE IF NOT EXISTS match_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    match_id_1 INTEGER NOT NULL,
    match_id_2 INTEGER NOT NULL,
    comparison_type TEXT,  -- 'team', 'player', 'tactical'
    focus_areas TEXT,  -- JSON array of focus areas
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id_1) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY (match_id_2) REFERENCES matches(id) ON DELETE CASCADE
);

-- Data quality scores per match
CREATE TABLE IF NOT EXISTS analysis_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    overall_score REAL,  -- 0-1
    tracking_score REAL,
    event_detection_score REAL,
    homography_score REAL,
    team_assignment_score REAL,
    issues TEXT,  -- JSON array of issue objects
    warnings TEXT,  -- JSON array of warning strings
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
);

-- Exported data log
CREATE TABLE IF NOT EXISTS exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER,
    season_id INTEGER,
    export_type TEXT NOT NULL,  -- 'match', 'season', 'player'
    format TEXT NOT NULL,  -- 'csv', 'json', 'statsbomb'
    file_path TEXT,
    file_size_bytes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL,
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE SET NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season_id);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_players_match ON players(match_id);
CREATE INDEX IF NOT EXISTS idx_events_match ON events(match_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_advanced_metrics_match ON advanced_metrics(match_id);
CREATE INDEX IF NOT EXISTS idx_advanced_metrics_player ON advanced_metrics(player_id);
CREATE INDEX IF NOT EXISTS idx_player_match_links_player ON player_match_links(player_id);
CREATE INDEX IF NOT EXISTS idx_player_match_links_match ON player_match_links(match_id);
CREATE INDEX IF NOT EXISTS idx_quality_match ON analysis_quality(match_id);
