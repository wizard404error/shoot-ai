"""REST API v1 — analytics endpoints for Kawkab AI.

Extends the cloud FastAPI server with match analysis, player rating,
tactical, fitness, recruitment, and monitoring endpoints."""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from kawkab.api.models import (
    MatchOut, MatchListOut, EventOut, PlayerOut,
    ShotAnalysisOut, TacticalShapesOut, PressingOut,
    PlayerRatingOut, SquadSummaryOut, MatchReportOut,
    LlmQueryIn, LlmQueryOut, CalibrationOut, ModelComparisonOut,
    FitnessOut, RecruitmentSearchIn, TransferFeeEstimateOut,
    GamePlanOut, MonitoringDashboardOut, WebhookCreateIn, WebhookOut,
)

router = APIRouter(prefix="/api/v1", tags=["analytics"])


def _get_storage():
    from kawkab.services.storage_service import StorageService
    svc = StorageService()
    return svc


def _get_monitor():
    from kawkab.services.model_monitor_service import ModelMonitoringService
    return ModelMonitoringService()


def _not_found(msg: str):
    raise HTTPException(status_code=404, detail=msg)


# ── Matches ──

@router.get("/matches", response_model=MatchListOut)
async def list_matches():
    svc = _get_storage()
    matches = await svc.get_all_matches()
    return MatchListOut(matches=[MatchOut(**m) for m in matches], total=len(matches))


@router.get("/matches/{match_id}", response_model=MatchOut)
async def get_match(match_id: int):
    svc = _get_storage()
    match = await svc.get_match(match_id)
    if not match:
        _not_found(f"Match {match_id} not found")
    return MatchOut(**match)


@router.get("/matches/{match_id}/events", response_model=list[EventOut])
async def get_match_events(
    match_id: int,
    event_type: str | None = Query(None),
    limit: int = Query(1000, le=5000),
):
    svc = _get_storage()
    events = await svc.get_match_events(match_id)
    if event_type:
        events = [e for e in events if e.get("type") == event_type]
    return [EventOut(
        id=e.get("id", 0),
        match_id=e.get("match_id", match_id),
        event_type=e.get("type", ""),
        timestamp=float(e.get("timestamp", 0)),
        team=e.get("team", ""),
        from_track_id=int(e.get("from_track_id", 0)),
        x=float(e.get("x", 0)), y=float(e.get("y", 0)),
        end_x=float(e.get("end_x", 0)), end_y=float(e.get("end_y", 0)),
    ) for e in events[:limit]]


@router.get("/matches/{match_id}/players", response_model=list[PlayerOut])
async def get_match_players(match_id: int):
    svc = _get_storage()
    players = await svc.get_match_players(match_id)
    return [PlayerOut(
        track_id=p.get("track_id", 0),
        match_id=match_id,
        name=p.get("name", f"Player {p.get('track_id', '')}"),
        team=p.get("team", ""),
        jersey_number=int(p.get("jersey_number", 0)),
    ) for p in players]


# ── Analysis ──

@router.get("/matches/{match_id}/analysis/shots", response_model=ShotAnalysisOut)
async def analyze_shots(match_id: int):
    svc = _get_storage()
    events = await svc.get_match_events(match_id)
    shots = [e for e in events if e.get("type") == "shot"]
    from kawkab.core.xg_model import compute_xg_from_dict

    shot_data = []
    total_xg = 0.0
    total_goals = 0
    for s in shots:
        xg = compute_xg_from_dict(s)
        is_goal = bool(s.get("is_goal", False))
        total_xg += xg
        if is_goal:
            total_goals += 1
        shot_data.append({
            "timestamp": s.get("timestamp", 0),
            "x": s.get("x", 0), "y": s.get("y", 0),
            "xg": round(xg, 4),
            "is_goal": is_goal,
            "player": s.get("player_name", ""),
        })

    return ShotAnalysisOut(
        match_id=match_id,
        shots=shot_data,
        total_shots=len(shots),
        total_goals=total_goals,
        total_xg=round(total_xg, 4),
    )


@router.get("/matches/{match_id}/analysis/tactical-shapes", response_model=TacticalShapesOut)
async def get_tactical_shapes(match_id: int):
    from kawkab.core.tactical_shape_analyzer import TacticalShapeAnalyzer
    svc = _get_storage()
    events = await svc.get_match_events(match_id)
    analyzer = TacticalShapeAnalyzer()
    result = analyzer.analyze(events)
    return TacticalShapesOut(**result)


@router.get("/matches/{match_id}/analysis/pressing", response_model=PressingOut)
async def get_pressing(match_id: int):
    from kawkab.core.pressing_classifier import PressingClassifier
    svc = _get_storage()
    events = await svc.get_match_events(match_id)
    classifier = PressingClassifier()
    result = classifier.classify(events)
    return PressingOut(**result)


@router.get("/matches/{match_id}/analysis/report", response_model=MatchReportOut)
async def get_match_report(match_id: int):
    from kawkab.core.tactical_report import TacticalReportGenerator
    svc = _get_storage()
    events = await svc.get_match_events(match_id)
    generator = TacticalReportGenerator()
    report = generator.generate(events)
    return MatchReportOut(match_id=match_id, **report)


# ── AI / LLM ──

@router.post("/matches/{match_id}/ai/ask", response_model=LlmQueryOut)
async def ask_llm(match_id: int, body: LlmQueryIn):
    from kawkab.services.llm_service import LLMService
    svc = _get_storage()
    events = await svc.get_match_events(match_id)
    context = json.dumps({"match_id": match_id, "events_count": len(events)}, indent=2)
    llm = LLMService()
    answer = llm.generate(tactical_context=context, question=body.question)
    return LlmQueryOut(answer=answer, model_used=llm.model_name if hasattr(llm, "model_name") else "default")


# ── Player Ratings ──

@router.get("/matches/{match_id}/ratings", response_model=list[SquadSummaryOut])
async def get_player_ratings(match_id: int):
    from kawkab.services.rating_service import RatingService
    svc = _get_storage()
    events = await svc.get_match_events(match_id)
    players = await svc.get_match_players(match_id)
    rating_svc = RatingService()
    ratings = rating_svc.compute_ratings(events, players)

    teams: dict[str, list[PlayerRatingOut]] = {}
    for r in ratings:
        team = r.get("team", "unknown")
        if team not in teams:
            teams[team] = []
        teams[team].append(PlayerRatingOut(
            track_id=r.get("track_id", 0),
            name=r.get("name", f"Player {r.get('track_id', '')}"),
            rating=float(r.get("rating", 0)),
            pass_accuracy=float(r.get("pass_accuracy", 0)),
            shot_impact=float(r.get("shot_impact", 0)),
            tackles=int(r.get("tackles", 0)),
        ))
    return [SquadSummaryOut(team=t, players=ps) for t, ps in teams.items()]


# ── Calibration & Model Comparison ──

@router.get("/matches/{match_id}/calibration", response_model=CalibrationOut)
async def get_calibration(match_id: int):
    from kawkab.core.calibration import ModelCalibrator
    svc = _get_storage()
    events = await svc.get_match_events(match_id)
    calibrator = ModelCalibrator()
    report = calibrator.generate_calibration_report(events)
    return CalibrationOut(
        model_name="heuristic",
        total_xg=report.get("total_xg", 0),
        actual_goals=report.get("actual_goals", 0),
        calibration_error=report.get("calibration_error", 0),
        brier_score=report.get("brier_score", 0),
        log_loss=report.get("log_loss", 0),
        shots_evaluated=report.get("n_shots", 0),
        status=report.get("status", ""),
    )


@router.post("/model-comparison", response_model=ModelComparisonOut)
async def compare_models(shots: list[dict], n_folds: int = Query(5, ge=0, le=10)):
    from kawkab.core.model_comparison import compare_xg_models
    report = compare_xg_models(shots, n_folds=n_folds, compute_feature_importance=True)
    return ModelComparisonOut(
        models=report.to_dict().get("models", []),
        best_model=report.best_model,
        cv_summary=report.cv_summary,
    )


# ── Fitness / Wearables ──

@router.get("/players/{track_id}/fitness", response_model=FitnessOut)
async def get_player_fitness(track_id: int, match_id: int = Query(..., description="Match ID")):
    from kawkab.services.physical_load_service import PhysicalLoadService
    from kawkab.services.workload_service import WorkloadService
    svc = _get_storage()
    events = await svc.get_match_events(match_id)
    load_svc = PhysicalLoadService()
    load_data = load_svc.compute_load(events, player_track_id=track_id)
    wl_svc = WorkloadService()
    wl_data = wl_svc.compute_acwr(events, player_track_id=track_id)
    return FitnessOut(
        player_name=load_data.get("name", f"Player {track_id}"),
        total_distance=float(load_data.get("total_distance", 0)),
        max_speed=float(load_data.get("max_speed", 0)),
        sprints=int(load_data.get("sprints", 0)),
        high_intensity_distance=float(load_data.get("high_intensity_distance", 0)),
        workload_score=float(wl_data.get("acwr", 0)),
    )


# ── Recruitment ──

@router.post("/recruitment/search")
async def search_players(body: RecruitmentSearchIn):
    try:
        from kawkab.services.player_search import PlayerSearchService
        search_svc = PlayerSearchService()
        results = search_svc.search(
            position=body.position,
            min_age=body.min_age,
            max_age=body.max_age,
            league=body.league,
            stat_thresholds=body.stat_thresholds,
            limit=body.limit,
        )
        return {"results": results, "total": len(results)}
    except ImportError:
        return {"results": [], "total": 0, "note": "PlayerSearchService not available"}


@router.get("/recruitment/transfer-fee/{player_name}", response_model=TransferFeeEstimateOut)
async def estimate_transfer_fee(player_name: str):
    try:
        from kawkab.core.squad_valuation import estimate_player_transfer_fee
        fee_data = estimate_player_transfer_fee(player_name)
        return TransferFeeEstimateOut(
            player_name=player_name,
            estimated_fee=fee_data.get("estimated_fee", 0),
            fee_range_low=fee_data.get("fee_range_low", 0),
            fee_range_high=fee_data.get("fee_range_high", 0),
            confidence=fee_data.get("confidence", "medium"),
        )
    except Exception:
        return TransferFeeEstimateOut(player_name=player_name)


@router.get("/recruitment/shortlist")
async def get_shortlist():
    try:
        from kawkab.services.shortlist_service import ShortlistService
        shortlist_svc = ShortlistService()
        return shortlist_svc.get_shortlist()
    except (ImportError, AttributeError):
        return []


# ── Game Plan ──

@router.get("/game-plan/{match_id}/vs/{opponent}", response_model=GamePlanOut)
async def get_game_plan(match_id: int, opponent: str):
    from kawkab.core.game_plan import GamePlanGenerator
    svc = _get_storage()
    events = await svc.get_match_events(match_id)
    generator = GamePlanGenerator()
    plan = generator.generate(events, opponent=opponent)
    return GamePlanOut(**plan)


# ── Monitoring ──

@router.get("/monitoring/dashboard", response_model=MonitoringDashboardOut)
async def get_monitoring_dashboard():
    monitor = _get_monitor()
    dashboard = monitor.get_monitoring_dashboard()
    return MonitoringDashboardOut(**dashboard)


@router.get("/monitoring/drift")
async def get_drift_alerts():
    monitor = _get_monitor()
    alerts = monitor.monitor.detect_drift()
    return {
        "alerts": [
            {
                "model_name": a.model_name,
                "metric": a.metric,
                "message": a.message,
                "severity": a.severity,
            }
            for a in alerts
        ],
        "total": len(alerts),
    }


# ── Webhooks ──

@router.post("/webhooks", response_model=WebhookOut)
async def create_webhook(body: WebhookCreateIn):
    from kawkab.services.webhook_service import WebhookService
    wh_svc = WebhookService()
    wh = wh_svc.register(body.url, body.secret, body.events)
    return WebhookOut(**wh)


@router.get("/webhooks", response_model=list[WebhookOut])
async def list_webhooks():
    from kawkab.services.webhook_service import WebhookService
    wh_svc = WebhookService()
    return [WebhookOut(**wh) for wh in wh_svc.list_all()]


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: int):
    from kawkab.services.webhook_service import WebhookService
    wh_svc = WebhookService()
    wh_svc.unregister(webhook_id)
    return {"ok": True}


# ── Season Summary ──

@router.get("/season/summary")
async def get_season_summary():
    from kawkab.core.season_aggregator import SeasonAggregator
    aggregator = SeasonAggregator()
    return aggregator.aggregate_team_season([])


# ── Health ──

@router.get("/health")
async def api_health():
    return {"status": "ok", "api_version": "v1"}
