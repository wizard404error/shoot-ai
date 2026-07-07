from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Optional


class InjurySeverity(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class InjuryStatus(str, Enum):
    ACTIVE = "active"
    RECOVERED = "recovered"
    CHRONIC = "chronic"


class BodyPart(str, Enum):
    HEAD = "head"
    NECK = "neck"
    SHOULDER = "shoulder"
    UPPER_ARM = "upper_arm"
    ELBOW = "elbow"
    FOREARM = "forearm"
    WRIST = "wrist"
    HAND = "hand"
    CHEST = "chest"
    RIBS = "ribs"
    UPPER_BACK = "upper_back"
    LOWER_BACK = "lower_back"
    ABDOMEN = "abdomen"
    HIP = "hip"
    GROIN = "groin"
    THIGH = "thigh"
    KNEE = "knee"
    SHIN = "shin"
    CALF = "calf"
    ANKLE = "ankle"
    FOOT = "foot"


@dataclass
class InjuryRecord:
    player_id: int
    injury_type: str
    body_part: str
    severity: str = "minor"
    mechanism: str = ""
    date_injured: str = ""
    match_id: Optional[int] = None
    status: str = "active"
    notes: str = ""
    id: int = 0
    date_recovered: str = ""
    created_at: str = ""

    def days_since_injury(self) -> int:
        if not self.date_injured:
            return 0
        try:
            d = datetime.strptime(self.date_injured[:10], "%Y-%m-%d").date()
            return (date.today() - d).days
        except (ValueError, TypeError):
            return 0

    def estimated_recovery_days(self) -> int:
        estimates = {
            "minor": 7, "sprain": 14, "strain": 14,
            "moderate": 21, "fracture": 42, "concussion": 14,
            "severe": 60, "acl": 180, "hamstring_tear": 56,
            "critical": 120,
        }
        key = self.severity.lower()
        if self.injury_type.lower() in estimates:
            key = self.injury_type.lower()
        return estimates.get(key, 14)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "player_id": self.player_id, "injury_type": self.injury_type,
            "body_part": self.body_part, "severity": self.severity, "mechanism": self.mechanism,
            "date_injured": self.date_injured, "date_recovered": self.date_recovered,
            "match_id": self.match_id, "status": self.status, "notes": self.notes,
            "days_since_injury": self.days_since_injury(),
            "estimated_recovery_days": self.estimated_recovery_days(),
            "created_at": self.created_at,
        }


class InjuryTrackerService:
    def __init__(self, db: Any) -> None:
        self._db = db

    def record_injury(self, record: InjuryRecord) -> int:
        cur = self._db.execute(
            """INSERT INTO injuries (player_id, match_id, injury_type, body_part, severity, mechanism, date_injured, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (record.player_id, record.match_id, record.injury_type, record.body_part,
             record.severity, record.mechanism, record.date_injured or datetime.now().isoformat(),
             record.status, record.notes),
        )
        self._db.commit()
        return cur.lastrowid

    def get_player_injuries(self, player_id: int) -> list[dict]:
        rows = self._db.execute(
            "SELECT * FROM injuries WHERE player_id = ? ORDER BY date_injured DESC",
            (player_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_active_injuries(self, team_player_ids: Optional[list[int]] = None) -> list[dict]:
        if team_player_ids:
            placeholders = ",".join("?" * len(team_player_ids))
            rows = self._db.execute(
                f"SELECT * FROM injuries WHERE status IN ('active','chronic') AND player_id IN ({placeholders}) ORDER BY date_injured DESC",
                team_player_ids,
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM injuries WHERE status IN ('active','chronic') ORDER BY date_injured DESC",
            ).fetchall()
        return [dict(r) for r in rows]

    def update_injury_status(self, injury_id: int, status: str, date_recovered: str = "") -> None:
        if status == "recovered" and not date_recovered:
            date_recovered = datetime.now().isoformat()
        self._db.execute(
            "UPDATE injuries SET status = ?, date_recovered = ?, updated_at = datetime('now') WHERE id = ?",
            (status, date_recovered, injury_id),
        )
        self._db.commit()

    def get_squad_injury_report(self, team_player_ids: list[int]) -> dict:
        active = self.get_active_injuries(team_player_ids)
        total = len(active)
        by_severity: dict[str, int] = {}
        by_body_part: dict[str, int] = {}
        for inj in active:
            s = inj.get("severity", "unknown")
            by_severity[s] = by_severity.get(s, 0) + 1
            bp = inj.get("body_part", "unknown")
            by_body_part[bp] = by_body_part.get(bp, 0) + 1
        return {
            "total_active": total,
            "injuries": active,
            "by_severity": by_severity,
            "by_body_part": by_body_part,
            "report_date": datetime.now().isoformat(),
        }

    def get_injury_stats(self, player_id: int) -> dict:
        rows = self._db.execute(
            "SELECT injury_type, COUNT(*) as cnt FROM injuries WHERE player_id = ? GROUP BY injury_type ORDER BY cnt DESC",
            (player_id,),
        ).fetchall()
        total = self._db.execute(
            "SELECT COUNT(*) as cnt FROM injuries WHERE player_id = ?",
            (player_id,),
        ).fetchone()["cnt"]
        return {"total_injuries": total, "by_type": {r["injury_type"]: r["cnt"] for r in rows}}
