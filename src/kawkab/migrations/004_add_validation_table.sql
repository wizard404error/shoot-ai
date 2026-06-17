-- Migration 004: Add validation results table
-- Stores accuracy validation reports against ground truth data

CREATE TABLE IF NOT EXISTS validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    ground_truth_source TEXT,  -- e.g., 'statsbomb', 'soccer_net', 'manual'
    overall_accuracy REAL,  -- 0-1
    category TEXT,  -- 'events', 'possession', 'team_assignment', 'speeds'
    metric_name TEXT NOT NULL,
    computed_value REAL,
    ground_truth_value REAL,
    absolute_error REAL,
    relative_error_pct REAL,
    accuracy_score REAL,  -- 0-1
    sample_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_validation_match ON validation_results(match_id);
CREATE INDEX IF NOT EXISTS idx_validation_category ON validation_results(category);
