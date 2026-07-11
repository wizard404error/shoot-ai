from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from kawkab.core.encryption import decrypt_dict, encrypt_dict


class ConcussionClearance(str, Enum):
    NOT_CLEARED = "not_cleared"
    STAGE_1 = "stage_1"
    STAGE_2 = "stage_2"
    STAGE_3 = "stage_3"
    STAGE_4 = "stage_4"
    STAGE_5 = "stage_5"
    FULL_CLEARED = "full_cleared"


STAGE_DESCRIPTIONS: dict[str, str] = {
    "stage_1": "Light aerobic exercise (walking, stationary bike) — no resistance training",
    "stage_2": "Moderate aerobic exercise (jogging, dynamic stretching) — sport-specific drills",
    "stage_3": "Non-contact training drills — resistance training allowed",
    "stage_4": "Full contact training — clearance from medical staff required",
    "stage_5": "Full game participation — final clearance",
}


@dataclass
class SCAT5Assessment:
    player_id: int
    symptoms_score: int = 0
    cognitive_score: int = 0
    balance_score: int = 0
    match_id: Optional[int] = None
    clearance_status: str = "not_cleared"
    notes: str = ""
    id: int = 0

    def total_score(self) -> int:
        return self.symptoms_score + self.cognitive_score + self.balance_score

    def is_symptomatic(self) -> bool:
        return self.symptoms_score > 0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "player_id": self.player_id, "match_id": self.match_id,
            "symptoms_score": self.symptoms_score, "cognitive_score": self.cognitive_score,
            "balance_score": self.balance_score, "total_score": self.total_score(),
            "is_symptomatic": self.is_symptomatic(),
            "clearance_status": self.clearance_status, "notes": self.notes,
        }


class ConcussionProtocolService:
    """Implements graduated return-to-play protocol for concussion management."""

    MIN_REST_DAYS = 24  # hours minimum rest before starting RTP stages
    STAGE_MIN_DAYS = 1  # minimum days per stage (no same-day advancement)

    def __init__(self, db: Any) -> None:
        self._db = db

    def record_assessment(self, assessment: SCAT5Assessment) -> int:
        encrypted_notes = encrypt_dict({"notes": assessment.notes}, ["notes"], in_place=False)["notes"]
        cur = self._db.execute(
            """INSERT INTO concussion_assessments
               (player_id, match_id, symptoms_score, cognitive_score, balance_score, clearance_status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (assessment.player_id, assessment.match_id, assessment.symptoms_score,
             assessment.cognitive_score, assessment.balance_score,
             assessment.clearance_status, encrypted_notes),
        )
        self._db.commit()
        return cur.lastrowid

    def get_assessments(self, player_id: int) -> list[dict]:
        rows = self._db.execute(
            "SELECT * FROM concussion_assessments WHERE player_id = ? ORDER BY assessment_date DESC",
            (player_id,),
        ).fetchall()
        return [decrypt_dict(dict(r), ["notes"]) for r in rows]

    def advance_clearance(self, assessment_id: int, cleared_by: str = "") -> Optional[dict]:
        row = self._db.execute(
            "SELECT * FROM concussion_assessments WHERE id = ?", (assessment_id,),
        ).fetchone()
        if row is None:
            return None
        current = decrypt_dict(dict(row), ["notes"])
        stages = [s.value for s in ConcussionClearance]
        try:
            idx = stages.index(current["clearance_status"])
        except ValueError:
            return current
        if idx >= len(stages) - 1:
            return current
        next_status = stages[idx + 1]
        appended = current.get("notes", "") + f" | Advanced to {next_status}"
        encrypted = encrypt_dict({"notes": appended}, ["notes"], in_place=False)["notes"]
        self._db.execute(
            """UPDATE concussion_assessments
               SET clearance_status = ?, cleared_by = COALESCE(?, cleared_by), notes = ?
               WHERE id = ?""",
            (next_status, cleared_by, encrypted, assessment_id),
        )
        self._db.commit()
        current["clearance_status"] = next_status
        current["notes"] = appended
        return current

    def get_clearance_status(self, player_id: int) -> dict:
        row = self._db.execute(
            "SELECT * FROM concussion_assessments WHERE player_id = ? ORDER BY assessment_date DESC LIMIT 1",
            (player_id,),
        ).fetchone()
        if row is None:
            return {"player_id": player_id, "clearance_status": "not_cleared", "has_assessment": False}
        r = decrypt_dict(dict(row), ["notes"])
        r["has_assessment"] = True
        r["stage_description"] = STAGE_DESCRIPTIONS.get(r["clearance_status"], "")
        return r

    def get_stage_protocol(self, stage: str) -> dict:
        return {
            "stage": stage,
            "description": STAGE_DESCRIPTIONS.get(stage, "Unknown stage"),
            "min_duration_days": self.STAGE_MIN_DAYS,
            "min_rest_hours": self.MIN_REST_DAYS,
        }

    def check_return_to_play_readiness(self, player_id: int) -> dict:
        status = self.get_clearance_status(player_id)
        if not status.get("has_assessment", False):
            return {"ready": False, "reason": "No concussion assessment recorded", "status": "not_assessed"}
        if status["clearance_status"] == "full_cleared":
            return {"ready": True, "status": "full_cleared", "reason": "Full clearance granted"}
        if status["is_symptomatic"]:
            return {"ready": False, "status": status["clearance_status"], "reason": "Player still symptomatic"}
        stage = status["clearance_status"]
        description = STAGE_DESCRIPTIONS.get(stage, "")
        return {
            "ready": stage == "full_cleared",
            "status": stage,
            "current_stage_description": description,
            "reason": "Progressing through RTP protocol" if stage != "full_cleared" else "Ready for full participation",
        }
