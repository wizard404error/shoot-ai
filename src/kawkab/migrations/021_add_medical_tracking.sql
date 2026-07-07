CREATE TABLE IF NOT EXISTS injuries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    match_id INTEGER,
    injury_type TEXT NOT NULL,
    body_part TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'minor',
    mechanism TEXT DEFAULT '',
    date_injured TEXT NOT NULL,
    date_recovered TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_injuries_player ON injuries(player_id);
CREATE INDEX IF NOT EXISTS idx_injuries_status ON injuries(status);

CREATE TABLE IF NOT EXISTS rehab_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    injury_id INTEGER NOT NULL REFERENCES injuries(id),
    phase TEXT NOT NULL DEFAULT 'initial',
    start_date TEXT NOT NULL,
    target_end_date TEXT,
    actual_end_date TEXT,
    milestones TEXT DEFAULT '[]',
    protocols TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rehab_injury ON rehab_plans(injury_id);

CREATE TABLE IF NOT EXISTS concussion_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    match_id INTEGER,
    assessment_date TEXT NOT NULL,
    assessment_type TEXT NOT NULL DEFAULT 'scat5',
    symptoms_score INTEGER DEFAULT 0,
    cognitive_score INTEGER DEFAULT 0,
    balance_score INTEGER DEFAULT 0,
    clearance_status TEXT DEFAULT 'not_cleared',
    cleared_by TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_concussion_player ON concussion_assessments(player_id);

CREATE TABLE IF NOT EXISTS medical_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    condition_type TEXT NOT NULL,
    diagnosis TEXT NOT NULL,
    diagnosis_date TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    severity TEXT DEFAULT 'moderate',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_medhist_player ON medical_history(player_id);

INSERT OR REPLACE INTO schema_version (version) VALUES (21);
