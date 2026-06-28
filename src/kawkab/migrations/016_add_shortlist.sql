-- Migration 016: Add player shortlist table for recruitment tracking

CREATE TABLE IF NOT EXISTS player_shortlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    position TEXT DEFAULT '',
    team TEXT DEFAULT '',
    league TEXT DEFAULT '',
    added_date TEXT NOT NULL DEFAULT (datetime('now')),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    status TEXT NOT NULL DEFAULT 'scouted' CHECK(status IN ('scouted','shortlisted','contacted','trial','signed','rejected','archived')),
    notes TEXT DEFAULT '',
    scout_rating REAL DEFAULT 0.0 CHECK(scout_rating >= 0 AND scout_rating <= 10),
    estimated_value REAL DEFAULT NULL,
    age INTEGER DEFAULT NULL,
    nationality TEXT DEFAULT '',
    last_updated TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_shortlist_status ON player_shortlist(status);
CREATE INDEX IF NOT EXISTS idx_shortlist_priority ON player_shortlist(priority);
CREATE INDEX IF NOT EXISTS idx_shortlist_player ON player_shortlist(player_id);
