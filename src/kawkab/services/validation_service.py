"""Data accuracy validation service - compares computed metrics against ground truth.

Validates analysis outputs by comparing against manually annotated or
publicly available benchmark datasets (e.g., SoccerNet, StatsBomb Open Data).

Tracks accuracy metrics over time to measure improvement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json

from kawkab.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EventGroundTruth:
    """A single ground truth event."""

    event_type: str
    timestamp: float
    team: str
    player_id: int | None = None
    position: tuple[float, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Accuracy validation result for a single metric category."""

    category: str  # e.g., 'events', 'tracking', 'team_assignment', 'speeds'
    metric_name: str  # e.g., 'pass_precision', 'shot_recall'
    computed_value: float
    ground_truth_value: float
    absolute_error: float
    relative_error_pct: float
    accuracy_score: float  # 0-1, higher is better
    sample_count: int = 0


@dataclass
class ValidationReport:
    """Complete validation report for a match."""

    match_id: int
    ground_truth_source: str
    overall_accuracy: float = 0.0
    results: list[ValidationResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "ground_truth_source": self.ground_truth_source,
            "overall_accuracy": self.overall_accuracy,
            "results": [
                {
                    "category": r.category,
                    "metric_name": r.metric_name,
                    "computed_value": r.computed_value,
                    "ground_truth_value": r.ground_truth_value,
                    "absolute_error": r.absolute_error,
                    "relative_error_pct": r.relative_error_pct,
                    "accuracy_score": r.accuracy_score,
                    "sample_count": r.sample_count,
                }
                for r in self.results
            ],
            "summary": self.summary,
        }


class ValidationService:
    """Validates analysis outputs against ground truth data."""

    # Event type mapping: our names -> ground truth names
    EVENT_TYPE_MAP = {
        "pass": ["pass", "pass_completion"],
        "shot": ["shot", "shot_attempt"],
        "tackle": ["tackle", "duel"],
        "interception": ["interception", "ball_recovery"],
        "clearance": ["clearance"],
        "cross": ["cross"],
        "dribble": ["dribble", "carry"],
    }

    def __init__(self) -> None:
        logger.info("ValidationService initialized")

    def load_ground_truth_events(self, path: Path | str) -> list[EventGroundTruth]:
        """Load ground truth events from a JSON or CSV file.

        JSON format:
        [
          {"event_type": "pass", "timestamp": 45.2, "team": "home", "player_id": 7},
          ...
        ]

        CSV format: event_type,timestamp,team,player_id,x,y
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Ground truth file not found: {path}")

        events = []
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data:
                events.append(EventGroundTruth(
                    event_type=item.get("event_type", "unknown"),
                    timestamp=item.get("timestamp", 0.0),
                    team=item.get("team", "unknown"),
                    player_id=item.get("player_id"),
                    position=(item.get("x"), item.get("y")) if "x" in item else None,
                    metadata=item.get("metadata", {}),
                ))
        elif path.suffix.lower() in (".csv", ".txt"):
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            if not lines:
                return []
            header = lines[0].split(",")
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) < 3:
                    continue
                events.append(EventGroundTruth(
                    event_type=parts[0],
                    timestamp=float(parts[1]),
                    team=parts[2] if len(parts) > 2 else "unknown",
                    player_id=int(parts[3]) if len(parts) > 3 and parts[3] else None,
                    position=(float(parts[4]), float(parts[5])) if len(parts) > 5 else None,
                ))
        else:
            raise ValueError(f"Unsupported ground truth format: {path.suffix}")

        logger.info(f"Loaded {len(events)} ground truth events from {path}")
        return events

    def validate_events(
        self,
        computed_events: list[dict],
        ground_truth_events: list[EventGroundTruth],
        tolerance_seconds: float = 2.0,
    ) -> list[ValidationResult]:
        """Validate event detection accuracy.

        Computes precision, recall, and F1 for each event type.
        A computed event is a "match" if it's within tolerance_seconds
        of a ground truth event of the same type.
        """
        results = []

        # Group by event type
        gt_by_type: dict[str, list[EventGroundTruth]] = {}
        for e in ground_truth_events:
            gt_by_type.setdefault(e.event_type, []).append(e)

        comp_by_type: dict[str, list[dict]] = {}
        for e in computed_events:
            comp_by_type.setdefault(e.get("type", "unknown"), []).append(e)

        # Validate each event type we have ground truth for
        all_types = set(gt_by_type.keys()) | set(comp_by_type.keys())
        for event_type in all_types:
            gt_list = gt_by_type.get(event_type, [])
            comp_list = comp_by_type.get(event_type, [])

            tp, fp, fn = 0, 0, 0
            matched_gt = set()

            for comp in comp_list:
                comp_ts = comp.get("timestamp", 0.0)
                found = False
                for i, gt in enumerate(gt_list):
                    if i in matched_gt:
                        continue
                    if abs(comp_ts - gt.timestamp) <= tolerance_seconds:
                        tp += 1
                        matched_gt.add(i)
                        found = True
                        break
                if not found:
                    fp += 1

            fn = len(gt_list) - len(matched_gt)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

            results.append(ValidationResult(
                category="events",
                metric_name=f"{event_type}_f1",
                computed_value=f1,
                ground_truth_value=1.0,
                absolute_error=1.0 - f1,
                relative_error_pct=(1.0 - f1) * 100,
                accuracy_score=f1,
                sample_count=len(gt_list),
            ))

            results.append(ValidationResult(
                category="events",
                metric_name=f"{event_type}_precision",
                computed_value=precision,
                ground_truth_value=1.0,
                absolute_error=1.0 - precision,
                relative_error_pct=(1.0 - precision) * 100,
                accuracy_score=precision,
                sample_count=len(gt_list),
            ))

            results.append(ValidationResult(
                category="events",
                metric_name=f"{event_type}_recall",
                computed_value=recall,
                ground_truth_value=1.0,
                absolute_error=1.0 - recall,
                relative_error_pct=(1.0 - recall) * 100,
                accuracy_score=recall,
                sample_count=len(gt_list),
            ))

        return results

    def validate_possession(
        self,
        computed_possession_pct: float,
        ground_truth_possession_pct: float,
    ) -> ValidationResult:
        """Validate possession percentage accuracy."""
        error = abs(computed_possession_pct - ground_truth_possession_pct)
        accuracy = max(0.0, 1.0 - error / 100.0)
        return ValidationResult(
            category="possession",
            metric_name="possession_pct",
            computed_value=computed_possession_pct,
            ground_truth_value=ground_truth_possession_pct,
            absolute_error=error,
            relative_error_pct=(error / ground_truth_possession_pct * 100) if ground_truth_possession_pct > 0 else 0.0,
            accuracy_score=accuracy,
            sample_count=1,
        )

    def validate_team_assignment(
        self,
        computed_assignments: dict[int, str],
        ground_truth_assignments: dict[int, str],
    ) -> ValidationResult:
        """Validate team assignment accuracy.

        Args:
            computed_assignments: {track_id: "home"/"away"}
            ground_truth_assignments: {track_id: "home"/"away"}
        """
        total = len(ground_truth_assignments)
        if total == 0:
            return ValidationResult(
                category="team_assignment",
                metric_name="accuracy",
                computed_value=0.0,
                ground_truth_value=1.0,
                absolute_error=1.0,
                relative_error_pct=100.0,
                accuracy_score=0.0,
                sample_count=0,
            )

        correct = sum(
            1 for tid, team in ground_truth_assignments.items()
            if computed_assignments.get(tid) == team
        )
        accuracy = correct / total
        return ValidationResult(
            category="team_assignment",
            metric_name="accuracy",
            computed_value=accuracy,
            ground_truth_value=1.0,
            absolute_error=1.0 - accuracy,
            relative_error_pct=(1.0 - accuracy) * 100,
            accuracy_score=accuracy,
            sample_count=total,
        )

    def validate_speeds(
        self,
        computed_speeds: dict[int, float],
        ground_truth_speeds: dict[int, float],
        max_acceptable_error_kmh: float = 5.0,
    ) -> list[ValidationResult]:
        """Validate max speed accuracy per player.

        Returns MAE and % of players within acceptable error.
        """
        errors = []
        for tid, gt_speed in ground_truth_speeds.items():
            comp_speed = computed_speeds.get(tid, 0.0)
            errors.append(abs(comp_speed - gt_speed))

        if not errors:
            return []

        mae = sum(errors) / len(errors)
        within_threshold = sum(1 for e in errors if e <= max_acceptable_error_kmh) / len(errors)

        return [
            ValidationResult(
                category="speeds",
                metric_name="max_speed_mae_kmh",
                computed_value=mae,
                ground_truth_value=0.0,
                absolute_error=mae,
                relative_error_pct=0.0,
                accuracy_score=max(0.0, 1.0 - mae / max_acceptable_error_kmh),
                sample_count=len(errors),
            ),
            ValidationResult(
                category="speeds",
                metric_name="max_speed_within_threshold_pct",
                computed_value=within_threshold,
                ground_truth_value=1.0,
                absolute_error=1.0 - within_threshold,
                relative_error_pct=(1.0 - within_threshold) * 100,
                accuracy_score=within_threshold,
                sample_count=len(errors),
            ),
        ]

    def build_report(
        self,
        match_id: int,
        ground_truth_source: str,
        results: list[ValidationResult],
    ) -> ValidationReport:
        """Build a complete validation report from individual results."""
        if results:
            overall = sum(r.accuracy_score for r in results) / len(results)
        else:
            overall = 0.0

        # Group by category for summary
        by_category: dict[str, list[float]] = {}
        for r in results:
            by_category.setdefault(r.category, []).append(r.accuracy_score)

        summary = {
            cat: round(sum(scores) / len(scores), 3)
            for cat, scores in by_category.items()
        }

        return ValidationReport(
            match_id=match_id,
            ground_truth_source=ground_truth_source,
            overall_accuracy=round(overall, 3),
            results=results,
            summary=summary,
        )
