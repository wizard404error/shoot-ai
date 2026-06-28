"""Feedback storage — coach feedback and issue reports."""

from __future__ import annotations

import json

from kawkab.core.logging import get_logger
from kawkab.services.storage.base import BaseStorage

try:
    from kawkab.core.security import SecurityValidator as _SecVal
    SecurityValidator = _SecVal
except ImportError:
    class _SecurityValidator:
        @staticmethod
        def validate_match_id(mid): return int(mid)
        @staticmethod
        def validate_float_range(v, lo, hi, n="v"): return max(float(lo), min(float(hi), float(v)))
        @staticmethod
        def sanitize_string(s, max_length=255): return str(s)[:max_length]
    SecurityValidator = _SecurityValidator()

logger = get_logger(__name__)


class FeedbackStorage(BaseStorage):
    """CRUD for coach feedback and issue reports."""

    async def save_feedback(self, feedback: dict) -> int:
        if not self._ensure_initialized("save_feedback"):
            return 0
        try:
            coach_id = SecurityValidator.sanitize_string(str(feedback["coach_id"]), max_length=100)
            overall_rating = SecurityValidator.validate_float_range(feedback["overall_rating"], 1, 5, "overall_rating")
            tracking_rating = SecurityValidator.validate_float_range(feedback["tracking_rating"], 1, 5, "tracking_rating") if feedback.get("tracking_rating") is not None else None
            events_rating = SecurityValidator.validate_float_range(feedback["events_rating"], 1, 5, "events_rating") if feedback.get("events_rating") is not None else None
            report_rating = SecurityValidator.validate_float_range(feedback["report_rating"], 1, 5, "report_rating") if feedback.get("report_rating") is not None else None
            ui_rating = SecurityValidator.validate_float_range(feedback["ui_rating"], 1, 5, "ui_rating") if feedback.get("ui_rating") is not None else None
            comments = SecurityValidator.sanitize_string(str(feedback.get("comments", "")), max_length=2000)
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO coach_feedback (
                    coach_id, match_id, overall_rating, tracking_rating,
                    events_rating, report_rating, ui_rating, comments, issues, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    coach_id,
                    feedback["match_id"],
                    overall_rating,
                    tracking_rating,
                    events_rating,
                    report_rating,
                    ui_rating,
                    comments,
                    json.dumps(feedback.get("issues", [])),
                    feedback.get("created_at", ""),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            self._log_error("save_feedback", e)
            return 0

    async def get_all_feedback(self) -> list[dict]:
        if not self._ensure_initialized("get_all_feedback"):
            return []
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM coach_feedback ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self._log_error("get_all_feedback", e)
            return []

    async def save_issue(self, issue: dict) -> int:
        if not self._ensure_initialized("save_issue"):
            return 0
        try:
            match_id = SecurityValidator.validate_match_id(issue["match_id"]) if issue.get("match_id") is not None else None
            category = SecurityValidator.sanitize_string(str(issue["category"]), max_length=50)
            severity = SecurityValidator.sanitize_string(str(issue["severity"]), max_length=50)
            description = SecurityValidator.sanitize_string(str(issue["description"]), max_length=5000)
            screenshot_path = SecurityValidator.sanitize_string(str(issue.get("screenshot_path", "")), max_length=500) if issue.get("screenshot_path") else None
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO issue_reports (
                    category, severity, description, match_id, screenshot_path, logs, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    category,
                    severity,
                    description,
                    match_id,
                    screenshot_path,
                    issue.get("logs", ""),
                    issue.get("created_at", ""),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            self._log_error("save_issue", e)
            return 0

    async def get_all_issues(self) -> list[dict]:
        if not self._ensure_initialized("get_all_issues"):
            return []
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM issue_reports ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self._log_error("get_all_issues", e)
            return []
