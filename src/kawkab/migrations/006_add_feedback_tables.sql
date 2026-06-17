-- Migration 006: Add feedback and telemetry tables for v0.8.0

-- Coach feedback table
CREATE TABLE IF NOT EXISTS coach_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coach_id TEXT NOT NULL,
    match_id INTEGER,
    overall_rating INTEGER NOT NULL CHECK(overall_rating BETWEEN 1 AND 5),
    tracking_rating INTEGER CHECK(tracking_rating BETWEEN 1 AND 5),
    events_rating INTEGER CHECK(events_rating BETWEEN 1 AND 5),
    report_rating INTEGER CHECK(report_rating BETWEEN 1 AND 5),
    ui_rating INTEGER CHECK(ui_rating BETWEEN 1 AND 5),
    comments TEXT,
    issues TEXT, -- JSON array
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Issue reports table
CREATE TABLE IF NOT EXISTS issue_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL CHECK(category IN ('tracking', 'events', 'performance', 'ui', 'crash', 'other')),
    severity TEXT NOT NULL CHECK(severity IN ('low', 'medium', 'high', 'critical')),
    description TEXT NOT NULL,
    match_id INTEGER,
    screenshot_path TEXT,
    logs TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Usage sessions (anonymized telemetry)
CREATE TABLE IF NOT EXISTS usage_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    features_used TEXT NOT NULL, -- JSON array
    duration_seconds REAL NOT NULL,
    match_count INTEGER DEFAULT 0,
    gpu_tier TEXT,
    model_size TEXT,
    error_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_feedback_coach ON coach_feedback(coach_id);
CREATE INDEX IF NOT EXISTS idx_feedback_match ON coach_feedback(match_id);
CREATE INDEX IF NOT EXISTS idx_issues_category ON issue_reports(category);
CREATE INDEX IF NOT EXISTS idx_issues_severity ON issue_reports(severity);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON usage_sessions(created_at);
