-- Migration 015: Prevent duplicate events from repeated analysis runs

CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedup
ON events(match_id, timestamp, event_type, from_track_id);

-- Also add index for user_corrections cascade path
CREATE INDEX IF NOT EXISTS idx_user_corrections_event
ON user_corrections(event_id);
