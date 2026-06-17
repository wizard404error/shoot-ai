-- Migration 010: Add Bzzoiro and EasySoccerData reference columns
-- Adds columns to link matches/profiles with Bzzoiro entities
-- and a unified external_data_cache for all source types

ALTER TABLE matches ADD COLUMN bzzoiro_home_team_id INTEGER;
ALTER TABLE matches ADD COLUMN bzzoiro_away_team_id INTEGER;
ALTER TABLE matches ADD COLUMN bzzoiro_event_id INTEGER;
ALTER TABLE matches ADD COLUMN bzzoiro_league_id INTEGER;
ALTER TABLE matches ADD COLUMN bzzoiro_competition_code TEXT;
ALTER TABLE matches ADD COLUMN prediction_data TEXT;

ALTER TABLE player_profiles ADD COLUMN bzzoiro_person_id INTEGER;
ALTER TABLE player_profiles ADD COLUMN bzzoiro_team_id INTEGER;

-- Unified external cache for Bzzoiro, EasySoccerData, and future sources
CREATE TABLE IF NOT EXISTS external_data_cache (
    cache_key TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
