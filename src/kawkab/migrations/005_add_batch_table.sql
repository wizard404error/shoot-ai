-- Migration 005: Add batch processing table
-- Stores batch jobs for overnight multi-match analysis

CREATE TABLE IF NOT EXISTS batch_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
    total_matches INTEGER DEFAULT 0,
    completed_matches INTEGER DEFAULT 0,
    failed_matches INTEGER DEFAULT 0,
    match_ids TEXT,  -- JSON array of match IDs
    options TEXT,  -- JSON: {generate_reports, export_csv, frame_skip, model_size}
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_batch_status ON batch_jobs(status);
CREATE INDEX IF NOT EXISTS idx_batch_created ON batch_jobs(created_at);
