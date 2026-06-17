-- Migration 014: Add weather conditions for matches
CREATE TABLE IF NOT EXISTS match_weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    latitude REAL,
    longitude REAL,
    temperature_c REAL,
    feels_like_c REAL,
    precipitation_mm REAL,
    wind_speed_kmh REAL,
    wind_direction_deg REAL,
    humidity_pct REAL,
    cloud_cover_pct REAL,
    conditions TEXT,
    pitch_state TEXT,
    source TEXT,
    recorded_at TEXT,
    FOREIGN KEY (match_id) REFERENCES matches(id)
);
CREATE INDEX IF NOT EXISTS idx_match_weather_match_id ON match_weather(match_id);

-- Migration 015: Add card events table
CREATE TABLE IF NOT EXISTS card_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    player_track_id INTEGER,
    player_name TEXT,
    card_type TEXT NOT NULL,
    minute INTEGER NOT NULL,
    second INTEGER DEFAULT 0,
    detection_source TEXT,
    confidence REAL,
    description TEXT,
    FOREIGN KEY (match_id) REFERENCES matches(id)
);
CREATE INDEX IF NOT EXISTS idx_card_events_match_id ON card_events(match_id);

-- Migration 016: Add psychology events table
CREATE TABLE IF NOT EXISTS psychology_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    minute INTEGER NOT NULL,
    second INTEGER DEFAULT 0,
    team TEXT,
    description TEXT,
    severity REAL,
    data_json TEXT,
    FOREIGN KEY (match_id) REFERENCES matches(id)
);
CREATE INDEX IF NOT EXISTS idx_psychology_events_match_id ON psychology_events(match_id);
