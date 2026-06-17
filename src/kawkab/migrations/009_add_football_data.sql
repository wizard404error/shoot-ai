-- Migration 009: Add football-data.org API reference columns
-- Adds columns to link Kawkab matches/profiles with football-data.org entities

ALTER TABLE matches ADD COLUMN api_match_id INTEGER;
ALTER TABLE matches ADD COLUMN competition_code TEXT;
ALTER TABLE matches ADD COLUMN football_data_home_team_id INTEGER;
ALTER TABLE matches ADD COLUMN football_data_away_team_id INTEGER;

ALTER TABLE player_profiles ADD COLUMN football_data_person_id INTEGER;
ALTER TABLE player_profiles ADD COLUMN football_data_team_id INTEGER;

-- Persistent cache table for football-data.org responses
CREATE TABLE IF NOT EXISTS football_data_cache (
    cache_key TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
