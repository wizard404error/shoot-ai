"""Tactical reasoning service - diagnoses match issues using the knowledge base.

This is the "Detective" layer of Kawkab AI. It:
1. Takes match analysis data (stats, formations, PPDA, events)
2. Queries the knowledge base for relevant tactical rules
3. Tests each rule's hypotheses against the data
4. Returns ranked diagnoses with confidence scores
5. Recommends training drills for each diagnosed issue
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from kawkab.core.logging import get_logger
from kawkab.services.knowledge_service import KnowledgeService, TacticalRule, Drill
from kawkab.services.analysis_service import MatchAnalysis

logger = get_logger(__name__)


@dataclass
class Diagnosis:
    """A single diagnosis of a tactical issue."""

    rule_id: str
    rule_name: str
    rule_name_ar: str
    category: str
    severity: str
    confidence: float
    evidence: dict[str, Any]
    explanation: str
    explanation_ar: str
    recommended_drills: list[str] = field(default_factory=list)
    video_timestamps: list[dict] = field(default_factory=list)


@dataclass
class DiagnosisReport:
    """Complete tactical diagnosis report for a match."""

    match_id: int
    diagnoses: list[Diagnosis]
    overall_assessment: str
    overall_assessment_ar: str
    priority_actions: list[str]
    priority_actions_ar: list[str]
    confidence: float


class ReasoningService:
    """Diagnoses tactical issues from match analysis data.

    Uses the knowledge base of tactical rules and the match analysis
    output to identify what's going wrong and what to fix.
    """

    def __init__(self, knowledge_service: KnowledgeService) -> None:
        self.kb = knowledge_service
        self._initialized = False
        logger.info("ReasoningService created")

    async def initialize(self) -> None:
        """Initialize by loading the knowledge base."""
        if not self._initialized:
            await self.kb.initialize()
            self._initialized = True
            logger.info(f"ReasoningService ready with {self.kb.stats['rules']} rules")

    async def diagnose_match(
        self,
        analysis: MatchAnalysis,
        events: list[dict] | None = None,
        language: str = "en",
    ) -> DiagnosisReport:
        """Run full tactical diagnosis on match analysis.

        Args:
            analysis: Output from AnalysisService.analyze_match
            events: Optional list of events (uses analysis.events if None)
            language: "en" or "ar" for explanations

        Returns:
            DiagnosisReport with ranked diagnoses and recommendations
        """
        await self.initialize()

        events = events or analysis.events

        logger.info(
            f"Diagnosing match {analysis.match_id}: "
            f"{len(events)} events, "
            f"possession {analysis.home_team.possession_pct:.1f}%/{analysis.away_team.possession_pct:.1f}%"
        )

        diagnoses = []
        all_rules = self.kb.get_all_rules()

        for rule in all_rules:
            diagnosis = await self._test_rule(rule, analysis, events)
            if diagnosis and diagnosis.confidence > 0.3:
                diagnoses.append(diagnosis)

        diagnoses.sort(key=lambda d: d.confidence, reverse=True)

        priority_actions = self._build_priority_actions(diagnoses, language)
        overall = self._build_overall_assessment(diagnoses, analysis, language)
        overall_conf = (
            sum(d.confidence for d in diagnoses[:5]) / min(5, len(diagnoses))
            if diagnoses else 0.0
        )

        logger.info(
            f"Diagnosis complete: {len(diagnoses)} issues found, "
            f"top: {diagnoses[0].rule_name if diagnoses else 'none'}"
        )

        return DiagnosisReport(
            match_id=analysis.match_id,
            diagnoses=diagnoses,
            overall_assessment=overall["en"],
            overall_assessment_ar=overall["ar"],
            priority_actions=priority_actions["en"],
            priority_actions_ar=priority_actions["ar"],
            confidence=overall_conf,
        )

    async def _test_rule(
        self,
        rule: TacticalRule,
        analysis: MatchAnalysis,
        events: list[dict],
    ) -> Diagnosis | None:
        """Test if a rule's pattern matches the match data.

        Returns None if rule doesn't apply, else a Diagnosis with
        confidence based on how well the pattern matches.
        """
        sig = rule.pattern_signature
        pattern_type = sig.get("type", "")

        confidence = 0.0
        evidence = {}

        if pattern_type == "zone_based_goal_concession":
            confidence, evidence = self._check_zone_concession(rule, analysis, events)
        elif pattern_type == "zone_based_possession_loss":
            confidence, evidence = self._check_possession_loss(rule, analysis, events)
        elif pattern_type == "through_balls_behind_defense":
            confidence, evidence = self._check_high_line(rule, analysis, events)
        elif pattern_type == "counter_attack_conceded":
            confidence, evidence = self._check_counter_attack(rule, analysis, events)
        elif pattern_type == "set_piece_goals_conceded":
            confidence, evidence = self._check_set_piece(rule, analysis, events)
        elif pattern_type == "low_final_third_entries":
            confidence, evidence = self._check_final_third(rule, analysis, events)
        elif pattern_type == "fullback_isolated_1v1":
            confidence, evidence = self._check_fullback_iso(rule, analysis, events)
        elif pattern_type == "striker_isolated":
            confidence, evidence = self._check_striker_iso(rule, analysis, events)
        elif pattern_type == "high_turnover_rate":
            confidence, evidence = self._check_turnovers(rule, analysis, events)
        elif pattern_type == "late_game_decline":
            confidence, evidence = self._check_late_game(rule, analysis, events)
        elif pattern_type == "poor_wide_play":
            confidence, evidence = self._check_wide_play(rule, analysis, events)
        else:
            return None

        if confidence < 0.3:
            return None

        primary_hyp = rule.hypotheses[0] if rule.hypotheses else None
        explanation_en = primary_hyp.coaching_notes.get("en", "") if primary_hyp else ""
        explanation_ar = primary_hyp.coaching_notes.get("ar", "") if primary_hyp else ""

        recommended_drill_ids = []
        if primary_hyp and primary_hyp.recommended_drills:
            recommended_drill_ids = primary_hyp.recommended_drills
        elif rule.recommended_drills and isinstance(rule.recommended_drills, list):
            if isinstance(rule.recommended_drills[0], dict):
                recommended_drill_ids = [
                    d.get("drill_id") for d in rule.recommended_drills
                    if isinstance(d, dict) and d.get("drill_id")
                ]

        return Diagnosis(
            rule_id=rule.rule_id,
            rule_name=rule.names.get("en", rule.rule_id),
            rule_name_ar=rule.names.get("ar", rule.rule_id),
            category=rule.category,
            severity=rule.severity,
            confidence=round(confidence, 3),
            evidence=evidence,
            explanation=explanation_en,
            explanation_ar=explanation_ar,
            recommended_drills=recommended_drill_ids,
        )

    def _check_zone_concession(
        self, rule: TacticalRule, analysis: MatchAnalysis, events: list[dict]
    ) -> tuple[float, dict]:
        """Check for goals conceded from a specific zone (e.g., left channel)."""
        zone_events = [
            e for e in events
            if e.get("type") == "goal" and e.get("zone") == rule.pattern_signature.get("zone")
        ]
        all_goals = [e for e in events if e.get("type") == "goal"]
        if not all_goals:
            return 0.0, {}
        pct = len(zone_events) / len(all_goals)
        if pct >= 0.5 and len(zone_events) >= 2:
            confidence = 0.6 + min(0.3, pct - 0.5)
            return confidence, {
                "zone_goals": len(zone_events),
                "total_goals_conceded": len(all_goals),
                "zone_pct": round(pct, 2),
            }
        return 0.0, {}

    def _check_possession_loss(
        self, rule: TacticalRule, analysis: MatchAnalysis, events: list[dict]
    ) -> tuple[float, dict]:
        """Check for high possession loss in defensive third."""
        def_turnovers = [
            e for e in events
            if e.get("type") == "turnover"
            and e.get("zone") == "defensive_third"
        ]
        all_turnovers = [e for e in events if e.get("type") == "turnover"]
        if not all_turnovers:
            return 0.0, {}
        pct = len(def_turnovers) / len(all_turnovers)
        if pct >= 0.3:
            confidence = 0.5 + min(0.3, (pct - 0.3) * 0.5)
            return confidence, {
                "def_third_turnovers": len(def_turnovers),
                "total_turnovers": len(all_turnovers),
                "pct": round(pct, 2),
            }
        return 0.0, {}

    def _check_high_line(
        self, rule: TacticalRule, analysis: MatchAnalysis, events: list[dict]
    ) -> tuple[float, dict]:
        """Check if high defensive line is being exposed."""
        formations = analysis.formations
        if not formations:
            return 0.0, {}
        home = formations.get("home", {})
        line_h = home.get("line_height")
        if line_h is None:
            return 0.0, {}
        behind_events = [
            e for e in events
            if e.get("zone") == "behind_defensive_line"
        ]
        if line_h > 0.7 and len(behind_events) >= 2:
            return 0.7, {
                "line_height": round(line_h, 2),
                "through_balls_behind": len(behind_events),
            }
        return 0.0, {}

    def _check_counter_attack(
        self, rule: TacticalRule, analysis: MatchAnalysis, events: list[dict]
    ) -> tuple[float, dict]:
        """Check for counter-attack vulnerability."""
        ca_shots = [
            e for e in events
            if e.get("type") == "shot"
            and e.get("situation") == "counter_attack"
        ]
        ca_goals = [e for e in ca_shots if e.get("outcome") == "goal"]
        if len(ca_shots) >= 3:
            return 0.6, {
                "counter_attack_shots": len(ca_shots),
                "counter_attack_goals": len(ca_goals),
            }
        return 0.0, {}

    def _check_set_piece(
        self, rule: TacticalRule, analysis: MatchAnalysis, events: list[dict]
    ) -> tuple[float, dict]:
        """Check for set piece weakness."""
        sp_goals = [
            e for e in events
            if e.get("type") == "goal"
            and e.get("situation") in {"corner", "free_kick", "throw_in"}
        ]
        all_goals = [e for e in events if e.get("type") == "goal"]
        if not all_goals:
            return 0.0, {}
        pct = len(sp_goals) / len(all_goals)
        if pct >= 0.3 and len(sp_goals) >= 2:
            return 0.65, {
                "set_piece_goals": len(sp_goals),
                "pct": round(pct, 2),
            }
        return 0.0, {}

    def _check_final_third(
        self, rule: TacticalRule, analysis: MatchAnalysis, events: list[dict]
    ) -> tuple[float, dict]:
        """Check for low final third entries."""
        ft_entries = [e for e in events if e.get("zone") == "final_third"]
        shots = [e for e in events if e.get("type") == "shot"]
        if not shots:
            return 0.0, {}
        if len(ft_entries) < 15 and len(shots) < 8:
            return 0.55, {
                "ft_entries": len(ft_entries),
                "shots": len(shots),
            }
        return 0.0, {}

    def _check_fullback_iso(
        self, rule: TacticalRule, analysis: MatchAnalysis, events: list[dict]
    ) -> tuple[float, dict]:
        """Check for isolated fullback situations."""
        iso_events = [
            e for e in events
            if e.get("type") == "1v1_situation" and e.get("position") == "fullback"
        ]
        if len(iso_events) >= 5:
            opp_success = sum(
                1 for e in iso_events if e.get("outcome") == "beaten"
            ) / len(iso_events)
            if opp_success > 0.55:
                return 0.6, {
                    "1v1_count": len(iso_events),
                    "opponent_success_rate": round(opp_success, 2),
                }
        return 0.0, {}

    def _check_striker_iso(
        self, rule: TacticalRule, analysis: MatchAnalysis, events: list[dict]
    ) -> tuple[float, dict]:
        """Check for isolated striker."""
        striker_passes = [
            e for e in events
            if e.get("type") == "pass" and e.get("to_position") == "striker"
        ]
        if 0 < len(striker_passes) < 15:
            return 0.5, {
                "passes_to_striker": len(striker_passes),
            }
        return 0.0, {}

    def _check_turnovers(
        self, rule: TacticalRule, analysis: MatchAnalysis, events: list[dict]
    ) -> tuple[float, dict]:
        """Check for high turnover rate."""
        turnovers = [e for e in events if e.get("type") == "turnover"]
        own_half = [e for e in turnovers if e.get("zone") in {"defensive_third", "middle_third"}]
        if not events:
            return 0.0, {}
        turnover_rate = len(turnovers) / len(events) if events else 0
        if len(turnovers) > 40 and len(own_half) / max(1, len(turnovers)) > 0.25:
            return 0.55, {
                "total_turnovers": len(turnovers),
                "own_half_turnovers": len(own_half),
                "turnover_rate": round(turnover_rate, 3),
            }
        return 0.0, {}

    def _check_late_game(
        self, rule: TacticalRule, analysis: MatchAnalysis, events: list[dict]
    ) -> tuple[float, dict]:
        """Check for late-game decline."""
        total = analysis.duration_seconds
        if total < 60:
            return 0.0, {}
        last_quarter_start = total * 0.75
        last_events = [e for e in events if e.get("timestamp", 0) > last_quarter_start]
        first_quarter_end = total * 0.25
        first_events = [e for e in events if e.get("timestamp", 0) < first_quarter_end]

        late_goals = sum(1 for e in last_events if e.get("type") == "goal")
        late_shots = sum(1 for e in last_events if e.get("type") == "shot")
        first_goals = sum(1 for e in first_events if e.get("type") == "goal")
        first_shots = sum(1 for e in first_events if e.get("type") == "shot")

        if late_goals > first_goals and first_shots > 0:
            return 0.6, {
                "late_goals": late_goals,
                "first_quarter_goals": first_goals,
                "late_shots": late_shots,
                "first_quarter_shots": first_shots,
            }
        return 0.0, {}

    def _check_wide_play(
        self, rule: TacticalRule, analysis: MatchAnalysis, events: list[dict]
    ) -> tuple[float, dict]:
        """Check for poor wide play."""
        crosses = [e for e in events if e.get("type") == "cross"]
        if not crosses:
            return 0.0, {}
        accurate = sum(1 for c in crosses if c.get("outcome") in {"completed", "shot_created"})
        accuracy = accurate / len(crosses) if crosses else 0
        if len(crosses) < 8 and accuracy < 0.25:
            return 0.5, {
                "crosses": len(crosses),
                "accuracy": round(accuracy, 2),
            }
        return 0.0, {}

    def _build_priority_actions(
        self, diagnoses: list[Diagnosis], language: str
    ) -> dict[str, list[str]]:
        """Build prioritized list of actions for the coach."""
        actions_en = []
        actions_ar = []
        for i, diag in enumerate(diagnoses[:5]):
            if diag.recommended_drills:
                drills = [
                    self.kb.get_drill(d_id) for d_id in diag.recommended_drills[:2]
                ]
                drills = [d for d in drills if d is not None]
                if drills:
                    drill_names_en = ", ".join(d.name for d in drills)
                    drill_names_ar = ", ".join(d.name_ar or d.name for d in drills)
                    actions_en.append(
                        f"Priority {i+1}: {drill_names_en} "
                        f"(addresses {diag.rule_name}, confidence {diag.confidence:.0%})"
                    )
                    actions_ar.append(
                        f"الأولوية {i+1}: {drill_names_ar} "
                        f"(يعالج: {diag.rule_name_ar}, الثقة {diag.confidence:.0%})"
                    )
        if not actions_en:
            actions_en = ["No critical issues detected. Continue current training plan."]
            actions_ar = ["لم يتم اكتشاف مشاكل حرجة. استمر في خطة التدريب الحالية."]
        return {"en": actions_en, "ar": actions_ar}

    def _build_overall_assessment(
        self, diagnoses: list[Diagnosis], analysis: MatchAnalysis, language: str
    ) -> dict[str, str]:
        """Build overall assessment summary."""
        if not diagnoses:
            return {
                "en": (
                    f"Match analysis complete. Possession: "
                    f"{analysis.home_team.possession_pct:.1f}% vs "
                    f"{analysis.away_team.possession_pct:.1f}%. "
                    f"No critical tactical issues detected. "
                    f"Continue monitoring for patterns across multiple matches."
                ),
                "ar": (
                    f"اكتمل تحليل المباراة. الاستحواذ: "
                    f"{analysis.home_team.possession_pct:.1f}% مقابل "
                    f"{analysis.away_team.possession_pct:.1f}%. "
                    f"لم يتم اكتشاف مشاكل تكتيكية حرجة. "
                    f"استمر في المراقبة لاكتشاف الأنماط عبر مباريات متعددة."
                ),
            }

        top = diagnoses[0]
        return {
            "en": (
                f"Match analysis complete. {len(diagnoses)} tactical issues identified. "
                f"Top concern: {top.rule_name} (confidence {top.confidence:.0%}). "
                f"{top.explanation or 'See recommended drills below.'}"
            ),
            "ar": (
                f"اكتمل تحليل المباراة. تم تحديد {len(diagnoses)} مشكلة تكتيكية. "
                f"أهم مشكلة: {top.rule_name_ar} (الثقة {top.confidence:.0%}). "
                f"{top.explanation_ar or 'راجع التدريبات الموصى بها أدناه.'}"
            ),
        }
