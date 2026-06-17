-- Migration 003: Add performance benchmarking table
-- Tracks per-stage performance metrics for analysis runs

CREATE TABLE IF NOT EXISTS benchmark_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER,
    video_path TEXT,
    video_duration_seconds REAL,
    total_frames INTEGER,
    -- Overall metrics
    total_time_seconds REAL,
    realtime_ratio REAL,  -- total_time / video_duration
    fps_effective REAL,  -- total_frames / total_time
    -- Per-stage metrics (seconds)
    stage_enhancement_seconds REAL,
    stage_detection_seconds REAL,
    stage_tracking_seconds REAL,
    stage_analysis_seconds REAL,
    stage_advanced_metrics_seconds REAL,
    stage_save_seconds REAL,
    -- Resource metrics
    peak_memory_mb REAL,
    peak_gpu_memory_mb REAL,
    gpu_utilization_pct REAL,  -- average GPU utilization
    -- System info
    gpu_name TEXT,
    cpu_name TEXT,
    ram_gb REAL,
    model_size TEXT,  -- yolo11n/s/m/l/x
    frame_skip INTEGER,
    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL
);

-- Index for filtering by date range
CREATE INDEX IF NOT EXISTS idx_benchmark_created ON benchmark_results(created_at);
CREATE INDEX IF NOT EXISTS idx_benchmark_gpu ON benchmark_results(gpu_name);
CREATE INDEX IF NOT EXISTS idx_benchmark_model ON benchmark_results(model_size);
