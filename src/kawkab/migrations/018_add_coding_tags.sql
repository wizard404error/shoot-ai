-- Migration 018: Add coding tags table for manual video tagging (Sportscode/Nacsport-style)

CREATE TABLE IF NOT EXISTS coding_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    sub_type TEXT DEFAULT '',
    video_time REAL NOT NULL,
    player_track_id INTEGER DEFAULT 0,
    player_name TEXT DEFAULT '',
    team TEXT DEFAULT '',
    period INTEGER DEFAULT 1,
    notes TEXT DEFAULT '',
    lead_ms INTEGER DEFAULT 2000,
    lag_ms INTEGER DEFAULT 3000,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_coding_tags_match ON coding_tags(match_id);
CREATE INDEX IF NOT EXISTS idx_coding_tags_type ON coding_tags(event_type);
CREATE INDEX IF NOT EXISTS idx_coding_tags_player ON coding_tags(player_track_id);
CREATE INDEX IF NOT EXISTS idx_coding_tags_time ON coding_tags(match_id, video_time);
