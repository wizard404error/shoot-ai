-- Migration 008: Add face embedding support for player recognition
ALTER TABLE player_profiles ADD COLUMN face_embedding TEXT;
ALTER TABLE player_profiles ADD COLUMN face_confidence REAL DEFAULT 0.0;