-- Migration 017: Add contract tracking for squad management

CREATE TABLE IF NOT EXISTS player_contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_profile_id INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    contract_type TEXT NOT NULL DEFAULT 'permanent' CHECK(contract_type IN ('permanent','loan','youth','scholar','trial')),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    club_option_years INTEGER DEFAULT 0,
    player_option_years INTEGER DEFAULT 0,
    release_clause_millions REAL DEFAULT NULL,
    wage_weekly_pounds REAL DEFAULT NULL,
    agent_name TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    last_updated TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (player_profile_id) REFERENCES player_profiles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_contracts_end_date ON player_contracts(end_date);
CREATE INDEX IF NOT EXISTS idx_contracts_type ON player_contracts(contract_type);
CREATE INDEX IF NOT EXISTS idx_contracts_profile ON player_contracts(player_profile_id);

ALTER TABLE player_profiles ADD COLUMN contract_end_date TEXT DEFAULT NULL;
ALTER TABLE player_profiles ADD COLUMN contract_type TEXT DEFAULT 'permanent';
ALTER TABLE player_profiles ADD COLUMN wage_weekly_pounds REAL DEFAULT NULL;
