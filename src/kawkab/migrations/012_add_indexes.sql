-- Migration 012: Add missing indexes for query performance
CREATE INDEX IF NOT EXISTS idx_feedback_created ON coach_feedback(created_at);
CREATE INDEX IF NOT EXISTS idx_issue_reports_created ON issue_reports(created_at);
CREATE INDEX IF NOT EXISTS idx_video_clips_match ON video_clips(match_id);
CREATE INDEX IF NOT EXISTS idx_match_comparisons_m1 ON match_comparisons(match_id_1);
CREATE INDEX IF NOT EXISTS idx_match_comparisons_m2 ON match_comparisons(match_id_2);
CREATE INDEX IF NOT EXISTS idx_player_match_links_name ON player_match_links(player_name);
