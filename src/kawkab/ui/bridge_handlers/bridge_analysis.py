"""Handler for analysis bridge methods - match analysis, player profiles,
specialized services (set piece, goalkeeper, substitution, possession,
psychology, rules, cards, pose, weather, mujoco, fluidx3d, roboflow, etc.)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kawkab.core.logging import get_logger
from kawkab.core.paths import get_paths
from kawkab.core.observability import metrics
from kawkab.core.security import SecurityValidator, ErrorSanitizer

logger = get_logger(__name__)


def _compute_hot_zones(events, grid_cols=6, grid_rows=4):
    if not events:
        return []
    x_vals = [e["x"] for e in events if e.get("x") is not None]
    y_vals = [e["y"] for e in events if e.get("y") is not None]
    if not x_vals or not y_vals:
        return []
    min_x, max_x = min(x_vals), max(x_vals)
    min_y, max_y = min(y_vals), max(y_vals)
    x_range = max(max_x - min_x, 1)
    y_range = max(max_y - min_y, 1)
    cells = {}
    for e in events:
        if e.get("x") is None or e.get("y") is None:
            continue
        cx = int((e["x"] - min_x) / x_range * grid_cols)
        cy = int((e["y"] - min_y) / y_range * grid_rows)
        key = f"{cx},{cy}"
        cells[key] = cells.get(key, 0) + 1
    max_count = max(cells.values()) if cells else 1
    return [{"x": int(k.split(",")[0]), "y": int(k.split(",")[1]), "count": v, "intensity": round(v / max_count, 2)} for k, v in cells.items()]


class AnalysisHandler:
    """Handles match analysis and specialized service operations for Bridge."""

    def __init__(self, bridge, services, rate_limiter=None):
        self._bridge = bridge
        self._services = services
        self._rate_limiter = rate_limiter
        self._overlay_cache: dict[int, list[dict]] = {}
        self._tracking_cache: dict[int, Any] = {}

    # ── service accessors ────────────────────────────────────────

    @property
    def cv_service(self): return self._services.get("cv_service")

    @property
    def enhancement_service(self): return self._services.get("enhancement_service")

    @property
    def analysis_service(self): return self._services.get("analysis_service")

    @property
    def llm_service(self): return self._services.get("llm_service")

    @property
    def knowledge_service(self): return self._services.get("knowledge_service")

    @property
    def storage_service(self): return self._services.get("storage_service")

    @property
    def homography_service(self): return self._services.get("homography_service")

    @property
    def lightglue_homography_service(self): return self._services.get("lightglue_homography_service")

    @property
    def benchmark_service(self): return self._services.get("benchmark_service")

    @property
    def player_profile_service(self): return self._services.get("player_profile_service")

    @property
    def multi_match_service(self): return self._services.get("multi_match_service")

    @property
    def visualization_service(self): return self._services.get("visualization_service")

    @property
    def quality_scoring_service(self): return self._services.get("quality_scoring_service")

    @property
    def advanced_event_detection_service(self): return self._services.get("advanced_event_detection_service")

    @property
    def physical_load_service(self): return self._services.get("physical_load_service")

    @property
    def injury_risk_predictor(self):
        from kawkab.core.injury_risk import InjuryRiskPredictor
        if not hasattr(self, '_injury_risk_predictor'):
            self._injury_risk_predictor = InjuryRiskPredictor()
        return self._injury_risk_predictor

    @property
    def training_plan_generator(self):
        if not hasattr(self, '_training_plan_generator'):
            from kawkab.services.training_plan_service import TrainingPlanGenerator
            kb = self.knowledge_service
            self._training_plan_generator = TrainingPlanGenerator(kb)
        return self._training_plan_generator

    @property
    def pressure_metrics_service(self): return self._services.get("pressure_metrics_service")

    @property
    def face_recognition_service(self): return self._services.get("face_recognition_service")

    @property
    def setpiece_service(self): return self._services.get("setpiece_service")

    @property
    def goalkeeper_service(self): return self._services.get("goalkeeper_service")

    @property
    def substitution_service(self): return self._services.get("substitution_service")

    @property
    def possession_service(self): return self._services.get("possession_service")

    @property
    def psychology_service(self): return self._services.get("psychology_service")

    @property
    def football_rules_service(self): return self._services.get("football_rules_service")

    @property
    def card_detection_service(self): return self._services.get("card_detection_service")

    @property
    def pose_analysis_service(self): return self._services.get("pose_analysis_service")

    @property
    def mujoco_ball_service(self): return self._services.get("mujoco_ball_service")

    @property
    def fluidx3d_service(self): return self._services.get("fluidx3d_service")

    @property
    def weather_service(self): return self._services.get("weather_service")

    @property
    def roboflow_sports_service(self): return self._services.get("roboflow_sports_service")

    @property
    def statsbomb_service(self): return self._services.get("statsbomb_service")

    @property
    def profiler(self): return self._services.get("profiler")

    @property
    def frame_skip(self): return self._services.get("frame_skip", 3)

    def _check_rate_limit(self, category: str = "analysis") -> None:
        if self._rate_limiter is not None and not self._rate_limiter.acquire(category):
            raise RuntimeError(f"Rate limit exceeded for {category}")

    # ── private helpers ──────────────────────────────────────────

    def _compute_overlay_data(self, track_data):
        data = []
        w = track_data.frames[0].image_width if track_data.frames else 1
        h = track_data.frames[0].image_height if track_data.frames else 1
        for frame in track_data.frames:
            if frame.image_width:
                w, h = frame.image_width, frame.image_height
            entry = {"f": frame.frame_number, "t": frame.timestamp, "p": [], "b": None}
            for det in frame.detections:
                x1, y1, x2, y2 = det.bbox
                cx = round(((x1 + x2) / 2) / w, 4)
                cy = round(((y1 + y2) / 2) / h, 4)
                if det.class_name == "person" and det.track_id is not None:
                    team = track_data.player_teams.get(det.track_id, "u")
                    entry["p"].append({"i": det.track_id, "x": cx, "y": cy, "m": team})
                elif det.class_name == "sports ball":
                    entry["b"] = {"x": cx, "y": cy}
            data.append(entry)
        return data

    # ================================================================
    # Core match operations
    # ================================================================

    async def get_first_frame(self, match_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            match = await self.storage_service.get_match(match_id)
            if not match or not match.get("video_path"):
                return json.dumps({"error": "No video found"})
            return json.dumps({"path": match["video_path"], "match_id": match_id})
        except Exception as e:
            logger.error(f"get_first_frame failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def save_homography(self, match_id, corners_json, pitch_length_m=105.0, pitch_width_m=68.0):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            if self.homography_service is None:
                return json.dumps({"success": False, "error": "HomographyService not initialized"})

            if corners_json == "auto":
                match = await self.storage_service.get_match(match_id)
                if not match:
                    return json.dumps({"success": False, "error": "Match not found"})
                import cv2
                cap = cv2.VideoCapture(match["video_path"])
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                matrix = self.homography_service.compute_homography_from_visible_markings(
                    frame_width=w, frame_height=h
                )
            elif corners_json == "lightglue":
                if self.lightglue_homography_service is None:
                    return json.dumps({
                        "success": False,
                        "error": "LightGlue not available (install with: uv sync --extra lightglue)",
                    })
                self.lightglue_homography_service.ensure_model()
                match = await self.storage_service.get_match(match_id)
                if not match:
                    return json.dumps({"success": False, "error": "Match not found"})
                import cv2
                cap = cv2.VideoCapture(match["video_path"])
                ret, frame = cap.read()
                cap.release()
                if not ret:
                    return json.dumps({"success": False, "error": "Could not read video frame"})
                matrix = self.lightglue_homography_service.auto_calibrate(
                    frame, pitch_length_m, pitch_width_m
                )
                if matrix is None:
                    return json.dumps({
                        "success": False,
                        "error": "LightGlue could not find enough matches. Try manual calibration.",
                    })
            else:
                # P0.5: Prefer LightGlue auto-calibration over manual 4-click path
                if self.lightglue_homography_service is not None:
                    try:
                        self.lightglue_homography_service.ensure_model()
                        match = await self.storage_service.get_match(match_id)
                        if match and match.get("video_path"):
                            import cv2
                            cap = cv2.VideoCapture(match["video_path"])
                            ret, frame = cap.read()
                            cap.release()
                            if ret:
                                lg_matrix = self.lightglue_homography_service.auto_calibrate(
                                    frame, pitch_length_m, pitch_width_m
                                )
                                if lg_matrix is not None:
                                    self.homography_service.save_calibration(match_id, lg_matrix)
                                    self._bridge.calibrationSaved.emit(match_id, {
                                        "success": True,
                                        "method": "lightglue",
                                        "confidence": 0.85,
                                        "error_px": 2.5,
                                    })
                                    return json.dumps({
                                        "success": True,
                                        "method": "lightglue",
                                        "confidence": 0.85,
                                        "error_px": 2.5,
                                    })
                    except Exception:
                        pass
                corners = json.loads(corners_json)
                matrix = self.homography_service.compute_homography_from_corners(
                    pixel_corners=[(c["x"], c["y"]) for c in corners],
                    pitch_length_m=pitch_length_m,
                    pitch_width_m=pitch_width_m,
                )

            self.homography_service.save_calibration(match_id, matrix)
            self._bridge.calibrationSaved.emit(match_id, {
                "confidence": matrix.confidence,
                "error_px": matrix.error_px,
            })
            return json.dumps({"success": True, "confidence": matrix.confidence, "error_px": matrix.error_px})
        except Exception as e:
            logger.error(f"save_homography failed: {e}")
            return json.dumps({"success": False, "error": ErrorSanitizer.sanitize_error(e)})

    async def get_homography(self, match_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            if self.homography_service is None:
                return json.dumps({"error": "Service not initialized"})
            matrix = self.homography_service.load_calibration(match_id)
            if matrix is None:
                return json.dumps({"error": "No calibration saved"})
            return json.dumps({
                "matrix": matrix.matrix,
                "pitch_length_m": matrix.pitch_length_m,
                "pitch_width_m": matrix.pitch_width_m,
                "confidence": matrix.confidence,
            })
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def save_segment_homography(self, match_id, segment_index, corners_json, pitch_length_m=105.0, pitch_width_m=68.0):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            segment_index = int(segment_index)
            if self.homography_service is None:
                return json.dumps({"success": False, "error": "HomographyService not initialized"})

            if corners_json == "auto":
                match = await self.storage_service.get_match(match_id)
                if not match:
                    return json.dumps({"success": False, "error": "Match not found"})
                import cv2
                cap = cv2.VideoCapture(match["video_path"])
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                matrix = self.homography_service.compute_homography_from_visible_markings(
                    frame_width=w, frame_height=h
                )
            elif corners_json == "lightglue":
                if self.lightglue_homography_service is None:
                    return json.dumps({
                        "success": False,
                        "error": "LightGlue not available (install with: uv sync --extra lightglue)",
                    })
                self.lightglue_homography_service.ensure_model()
                match = await self.storage_service.get_match(match_id)
                if not match:
                    return json.dumps({"success": False, "error": "Match not found"})
                import cv2
                cap = cv2.VideoCapture(match["video_path"])
                ret, frame = cap.read()
                cap.release()
                if not ret:
                    return json.dumps({"success": False, "error": "Could not read video frame"})
                matrix = self.lightglue_homography_service.auto_calibrate(
                    frame, pitch_length_m, pitch_width_m
                )
                if matrix is None:
                    return json.dumps({
                        "success": False,
                        "error": "LightGlue could not find enough matches. Try manual calibration.",
                    })
            else:
                corners = json.loads(corners_json)
                matrix = self.homography_service.compute_homography_from_corners(
                    pixel_corners=[(c["x"], c["y"]) for c in corners],
                    pitch_length_m=pitch_length_m,
                    pitch_width_m=pitch_width_m,
                )

            self.homography_service.save_segment_calibration(match_id, segment_index, matrix)
            return json.dumps({"success": True, "confidence": matrix.confidence, "error_px": matrix.error_px})
        except Exception as e:
            logger.error(f"save_segment_homography failed: {e}")
            return json.dumps({"success": False, "error": ErrorSanitizer.sanitize_error(e)})

    async def get_segment_homographies(self, match_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            if self.homography_service is None:
                return json.dumps({"error": "Service not initialized"})
            segments = self.homography_service.load_segment_calibrations(match_id)
            result = {}
            for seg_idx, matrix in segments.items():
                result[str(seg_idx)] = {
                    "matrix": matrix.matrix,
                    "pitch_length_m": matrix.pitch_length_m,
                    "pitch_width_m": matrix.pitch_width_m,
                    "confidence": matrix.confidence,
                    "source": matrix.source,
                }
            return json.dumps({"segments": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def save_match(self, name, video_path):
        self._check_rate_limit()
        try:
            name = SecurityValidator.validate_team_name(name)
            video_path = str(SecurityValidator.validate_video_path(video_path))
            match_id = await self.storage_service.save_match(name=name, video_path=video_path)
            self._bridge.matchSaved.emit(match_id)
            return match_id
        except Exception as e:
            logger.error(f"Failed to save match: {e}")
            return 0

    async def analyze_match(self, match_id, video_path):
        self._check_rate_limit()
        import json

        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            video_path_obj = SecurityValidator.validate_video_path(video_path)
            if not video_path_obj.exists():
                raise FileNotFoundError(f"Video not found: {video_path}")

            metrics.counter("videos_processed_total", "Total videos analyzed").inc()
            self._bridge.analysisProgress.emit(0.0, "Starting analysis...")
            if self.benchmark_service is not None:
                self.benchmark_service.reset()

            self._bridge.analysisProgress.emit(0.05, "Enhancing video...")
            if self.benchmark_service is not None:
                self.benchmark_service.start_stage("enhancement")
            self.profiler.begin("enhancement")
            preprocessed_path = get_paths().cache / f"{video_path_obj.stem}_preprocessed.mp4"
            await self.enhancement_service.preprocess_video(video_path_obj, preprocessed_path)
            self.profiler.end("enhancement")
            if self.benchmark_service is not None:
                self.benchmark_service.end_stage("enhancement")

            self._bridge.analysisProgress.emit(0.15, "Detecting players and ball...")
            if self.benchmark_service is not None:
                self.benchmark_service.start_stage("detection")
                self.benchmark_service.start_stage("tracking")
            self.profiler.begin("cv_detection")

            async def progress_cb(progress, msg):
                total = 0.15 + progress * 0.55
                self._bridge.analysisProgress.emit(total, msg)

            track_data = await self.cv_service.process_video(
                preprocessed_path,
                progress_callback=progress_cb,
                frame_skip=self.frame_skip,
                enable_team_detection=True,
            )
            self.profiler.end("cv_detection")
            if self.benchmark_service is not None:
                self.benchmark_service.end_stage("detection")
                self.benchmark_service.end_stage("tracking")

            self._overlay_cache[match_id] = self._compute_overlay_data(track_data)
            self._tracking_cache[match_id] = track_data

            await self.storage_service.update_match_analysis(
                match_id=match_id,
                duration=track_data.duration_seconds,
                fps=track_data.fps,
                total_frames=track_data.total_frames,
            )

            homography_matrix = None
            if self.homography_service is not None:
                homography_matrix = self.homography_service.load_calibration(match_id)

            self._bridge.analysisProgress.emit(0.75, "Computing statistics...")
            if self.benchmark_service is not None:
                self.benchmark_service.start_stage("analysis")
            self.profiler.begin("analysis")
            analysis = await self.analysis_service.analyze_match(
                track_data, match_id=match_id, homography_matrix=homography_matrix
            )
            self.profiler.end("analysis")
            if self.benchmark_service is not None:
                self.benchmark_service.end_stage("analysis")

            self._bridge.analysisProgress.emit(0.85, "Saving results...")
            if self.benchmark_service is not None:
                self.benchmark_service.start_stage("save")
            self.profiler.begin("save")
            for track_id, player in analysis.players.items():
                await self.storage_service.save_player(
                    match_id=match_id,
                    player_data={
                        "track_id": player.track_id,
                        "jersey_number": player.jersey_number,
                        "name": player.name,
                        "team": player.team,
                        "position": player.position,
                        "distance_covered_m": player.distance_covered_m,
                        "max_speed_kmh": player.max_speed_kmh,
                        "avg_speed_kmh": player.avg_speed_kmh,
                        "passes_attempted": player.passes_attempted,
                        "passes_completed": player.passes_completed,
                        "shots": player.shots,
                        "tackles": player.tackles,
                    },
                )
            for event in analysis.events:
                await self.storage_service.save_event(match_id=match_id, event=event)
            self.profiler.end("save")
            if self.benchmark_service is not None:
                self.benchmark_service.end_stage("save")

            self._bridge.analysisProgress.emit(0.88, "Computing advanced metrics...")
            if self.benchmark_service is not None:
                self.benchmark_service.start_stage("advanced_metrics")
            self.profiler.begin("advanced_metrics")

            advanced_events = []
            physical_loads = {}
            pressure_metrics = {}

            try:
                if self.advanced_event_detection_service is not None:
                    advanced_events = await self.advanced_event_detection_service.detect_all_advanced_events(
                        track_data, analysis.events, homography_matrix
                    )
                    for event in advanced_events:
                        await self.storage_service.save_event(match_id=match_id, event=event)
            except Exception as e:
                logger.warning(f"Advanced event detection failed: {e}")

            try:
                if self.physical_load_service is not None:
                    physical_loads = await self.physical_load_service.compute_physical_load(
                        track_data, homography_matrix
                    )
                    for track_id, m in physical_loads.items():
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id, metric_name="sprint_count",
                            metric_value=m.sprint_count, metric_category="physical", player_id=None,
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id, metric_name="sprint_distance_m",
                            metric_value=m.sprint_distance_m, metric_category="physical",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id, metric_name="hi_distance_m",
                            metric_value=m.high_intensity_distance_m, metric_category="physical",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id, metric_name="acceleration_count",
                            metric_value=m.acceleration_count, metric_category="physical",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id, metric_name="deceleration_count",
                            metric_value=m.deceleration_count, metric_category="physical",
                        )
            except Exception as e:
                logger.warning(f"Physical load computation failed: {e}")

            try:
                if self.pressure_metrics_service is not None:
                    all_events = analysis.events + advanced_events
                    pressure_metrics = await self.pressure_metrics_service.compute_pressure_metrics(
                        track_data, all_events, homography_matrix
                    )
                    for team, m in pressure_metrics.items():
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id, metric_name="ppda",
                            metric_value=m.ppda_overall, metric_category="pressure",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id, metric_name="passes_under_pressure_pct",
                            metric_value=m.passes_under_pressure_pct, metric_category="pressure",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id, metric_name="pressure_events",
                            metric_value=m.pressure_events, metric_category="pressure",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id, metric_name="counter_press_success_rate",
                            metric_value=m.counter_press_success_rate, metric_category="pressure",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id, metric_name="defensive_line_height_m",
                            metric_value=m.defensive_line_height_m, metric_category="pressure",
                        )
            except Exception as e:
                logger.warning(f"Pressure metrics computation failed: {e}")

            self.profiler.end("advanced_metrics")
            if self.benchmark_service is not None:
                self.benchmark_service.end_stage("advanced_metrics")

            self.profiler.stop()
            metrics.counter("events_detected_total", "Total events detected across all analyses").inc(len(analysis.events))
            metrics.gauge("players_detected", "Players in last analysis").set(len(analysis.players))
            metrics.histogram("analysis_duration_seconds", "End-to-end analysis time").observe(
                self.profiler.report().total_s if self.profiler else 0
            )
            self._bridge.analysisProgress.emit(1.0, "Analysis complete!")

            result = {
                "match_id": analysis.match_id,
                "duration": analysis.duration_seconds,
                "home_team": {
                    "possession": analysis.home_team.possession_pct,
                    "passes_completed": analysis.home_team.passes_completed,
                    "passes_attempted": analysis.home_team.passes_attempted,
                    "shots": analysis.home_team.shots,
                    "pass_accuracy": analysis.home_team.pass_accuracy,
                },
                "away_team": {
                    "possession": analysis.away_team.possession_pct,
                    "passes_completed": analysis.away_team.passes_completed,
                    "passes_attempted": analysis.away_team.passes_attempted,
                    "shots": analysis.away_team.shots,
                    "pass_accuracy": analysis.away_team.pass_accuracy,
                },
                "player_count": len(analysis.players),
                "event_count": len(analysis.events),
                "advanced_event_count": len(advanced_events),
                "confidence": analysis.confidence_overall,
                "advanced_metrics": {
                    "physical_load": {
                        str(tid): {
                            "sprint_count": m.sprint_count,
                            "sprint_distance_m": m.sprint_distance_m,
                            "hi_distance_m": m.high_intensity_distance_m,
                            "acceleration_count": m.acceleration_count,
                            "deceleration_count": m.deceleration_count,
                        }
                        for tid, m in physical_loads.items()
                    } if physical_loads else {},
                    "pressure": {
                        team: {
                            "ppda": m.ppda_overall,
                            "passes_under_pressure_pct": m.passes_under_pressure_pct,
                            "pressure_events": m.pressure_events,
                            "counter_press_success_rate": m.counter_press_success_rate,
                            "defensive_line_height_m": m.defensive_line_height_m,
                        }
                        for team, m in pressure_metrics.items()
                    } if pressure_metrics else {},
                },
            }

            if self.benchmark_service is not None:
                bench_result = self.benchmark_service.build_result(
                    match_id=match_id,
                    video_path=str(video_path_obj),
                    video_duration_seconds=track_data.duration_seconds,
                    total_frames=track_data.total_frames,
                    model_size=self.cv_service.model_size if self.cv_service else "l",
                    frame_skip=self.frame_skip,
                )
                try:
                    await self.storage_service.save_benchmark(bench_result)
                except Exception as e:
                    logger.warning(f"Failed to save benchmark: {e}")
                result["benchmark"] = {
                    "total_time_seconds": bench_result.total_time_seconds,
                    "realtime_ratio": bench_result.realtime_ratio,
                    "fps_effective": bench_result.fps_effective,
                    "peak_memory_mb": bench_result.peak_memory_mb,
                    "peak_gpu_memory_mb": bench_result.peak_gpu_memory_mb,
                    "stages": {
                        "enhancement": bench_result.stage_enhancement_seconds,
                        "detection": bench_result.stage_detection_seconds,
                        "tracking": bench_result.stage_tracking_seconds,
                        "analysis": bench_result.stage_analysis_seconds,
                        "advanced_metrics": bench_result.stage_advanced_metrics_seconds,
                        "save": bench_result.stage_save_seconds,
                    },
                }

            self._bridge.analysisComplete.emit(result)
            return json.dumps(result)
        except Exception as e:
            logger.exception(f"Analysis failed: {e}")
            self._bridge.analysisError.emit(ErrorSanitizer.sanitize_error(e))
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def get_overlay_data(self, match_id, timestamp):
        data = self._overlay_cache.get(match_id)
        if not data:
            return "{}"
        lo, hi = 0, len(data) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if data[mid]["t"] <= timestamp:
                lo = mid
            else:
                hi = mid - 1
        return json.dumps(data[lo])

    async def get_all_matches(self):
        self._check_rate_limit()
        try:
            matches = await self.storage_service.get_all_matches()
            return json.dumps(matches)
        except Exception as e:
            logger.error(f"Failed to get matches: {e}")
            return json.dumps([])

    async def get_match_events(self, match_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)
            return json.dumps(events)
        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ── Event Review / Correction (Phase 2) ──────────────────────

    async def get_unreviewed_events(self, match_id, min_confidence=0.0, max_confidence=0.7):
        self._check_rate_limit()
        """Get auto-detected events with low confidence that need review.

        Returns events sorted by confidence ascending (lowest first),
        with auto_detected flag and metadata parsed from JSON.
        """
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)
            unreviewed = []
            for ev in events:
                if ev.get("user_corrected", 0):
                    continue
                conf = ev.get("confidence", 0.0)
                if conf is None:
                    conf = 0.0
                if conf < min_confidence or conf > max_confidence:
                    continue
                meta = ev.get("metadata", "{}")
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        meta = {}
                ev["_meta"] = meta
                ev["_needs_review"] = conf < 0.5
                unreviewed.append(ev)

            unreviewed.sort(key=lambda e: (e.get("confidence", 0) or 0))
            return json.dumps({"success": True, "events": unreviewed, "total": len(unreviewed)})
        except Exception as e:
            logger.error(f"get_unreviewed_events failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_detection_summary(self, match_id):
        self._check_rate_limit()
        """Get auto-detection stats by event type with average confidence."""
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)

            by_type = {}
            for ev in events:
                etype = ev.get("event_type", "unknown")
                conf = ev.get("confidence", 0) or 0
                corrected = ev.get("user_corrected", 0)
                if etype not in by_type:
                    by_type[etype] = {"count": 0, "corrected": 0, "total_confidence": 0.0, "avg_confidence": 0.0}
                by_type[etype]["count"] += 1
                by_type[etype]["total_confidence"] += conf
                if corrected:
                    by_type[etype]["corrected"] += 1

            for etype, stats in by_type.items():
                stats["avg_confidence"] = round(stats["total_confidence"] / stats["count"], 3) if stats["count"] else 0
                del stats["total_confidence"]

            total = len(events)
            corrected = sum(1 for e in events if e.get("user_corrected", 0))
            return json.dumps({
                "success": True,
                "by_type": by_type,
                "total": total,
                "corrected": corrected,
                "unreviewed": total - corrected,
            })
        except Exception as e:
            logger.error(f"get_detection_summary failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def submit_event_correction(self, match_id, event_id, action, corrections_json):
        self._check_rate_limit()
        """Submit a correction for an auto-detected event.

        Actions: 'confirm' (mark reviewed), 'reject' (delete event),
                 'edit' (update event fields + save correction record)
        """
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            event_id = SecurityValidator.validate_match_id(event_id) if hasattr(SecurityValidator, 'validate_match_id') else int(event_id)

            if action == "confirm":
                ok = await self.storage_service.update_event(event_id, {"user_corrected": 1})
                return json.dumps({"success": bool(ok), "action": "confirmed"})

            elif action == "reject":
                ok = await self.storage_service.delete_event(event_id)
                return json.dumps({"success": bool(ok), "action": "deleted"})

            elif action == "edit":
                corrections = json.loads(corrections_json) if corrections_json else {}
                allowed_updates = {}
                original = None
                events = await self.storage_service.get_match_events(match_id)
                for ev in events:
                    if ev.get("id") == event_id:
                        original = dict(ev)
                        break

                if "event_type" in corrections:
                    allowed_updates["event_type"] = corrections["event_type"]
                if "team" in corrections:
                    allowed_updates["team"] = corrections["team"]
                if "completed" in corrections:
                    allowed_updates["completed"] = bool(corrections["completed"])
                if "confidence" in corrections:
                    allowed_updates["confidence"] = float(corrections["confidence"])
                if "metadata" in corrections:
                    allowed_updates["metadata"] = corrections["metadata"]

                allowed_updates["user_corrected"] = 1
                ok = await self.storage_service.update_event(event_id, allowed_updates)

                if ok and original:
                    await self.storage_service.save_correction(
                        event_id=event_id,
                        correction_type="edit",
                        original_value={"event_type": original.get("event_type"), "team": original.get("team")},
                        corrected_value=corrections,
                    )

                return json.dumps({"success": bool(ok), "action": "edited"})

            else:
                return json.dumps({"error": f"Unknown action: {action}"})
        except Exception as e:
            logger.error(f"submit_event_correction failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_video_path(self, match_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            match = await self.storage_service.get_match(match_id)
            if not match or not match.get("video_path"):
                return json.dumps({"error": "No video found"})
            return json.dumps({"path": match["video_path"]})
        except Exception as e:
            logger.error(f"get_video_path failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def generate_report(self, match_id, language, summary):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            language = SecurityValidator.sanitize_string(language, max_length=10)
            if language not in ("en", "ar"):
                language = "en"
            report = await self.llm_service.generate_coach_report(
                match_analysis_summary=summary, language=language
            )
            await self.storage_service.save_report(
                match_id=match_id, language=language, report_text=report,
                llm_provider=self.llm_service.config.provider,
            )
            return report
        except Exception as e:
            logger.exception(f"Report generation failed: {e}")
            return f"Error generating report: {ErrorSanitizer.sanitize_error(e)}"

    async def get_knowledge_base_stats(self):
        await self.knowledge_service.initialize()
        return json.dumps(self.knowledge_service.stats)

    async def check_llm_availability(self):
        self._check_rate_limit()
        try:
            ollama_available = False
            for provider in self.llm_service.providers:
                if hasattr(provider, "is_available"):
                    if await provider.is_available():
                        ollama_available = True
                        break
            return json.dumps({
                "ollama": ollama_available,
                "provider": self.llm_service.config.provider,
                "model": (
                    self.llm_service.config.ollama_model
                    if self.llm_service.config.provider == "ollama"
                    else "external"
                ),
            })
        except Exception as e:
            logger.error(f"LLM check failed: {e}")
            return json.dumps({"ollama": False, "error": str(e)})

    # ================================================================
    # Player Profile operations
    # ================================================================

    async def create_player_profile(self, name, jersey, number, position):
        self._check_rate_limit()
        try:
            name = SecurityValidator.sanitize_string(name, max_length=100)
            number = SecurityValidator.validate_jersey_number(number)
            position = SecurityValidator.sanitize_string(position, max_length=50)
            if self.player_profile_service is None:
                return json.dumps({"error": "PlayerProfileService not available"})
            profile = await self.player_profile_service.create_profile(
                display_name=name, jersey_number=number, preferred_position=position,
            )
            return json.dumps({"success": True, "profile_id": profile.id, "global_id": profile.global_id})
        except Exception as e:
            logger.error(f"Create profile failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_all_player_profiles(self):
        self._check_rate_limit()
        try:
            if self.player_profile_service is None:
                return json.dumps({"profiles": []})
            profiles = await self.player_profile_service.get_all_profiles()
            return json.dumps({
                "profiles": [
                    {"id": p.id, "name": p.display_name, "jersey": p.jersey_number, "position": p.preferred_position}
                    for p in profiles
                ]
            })
        except Exception as e:
            logger.error(f"Get profiles failed: {e}")
            return json.dumps({"profiles": []})

    async def get_face_gallery(self):
        try:
            profiles = await self.storage_service.get_all_player_profiles()
            result = []
            for p in profiles:
                result.append({
                    "id": p["id"],
                    "display_name": p.get("display_name", ""),
                    "jersey_number": p.get("jersey_number"),
                    "team": p.get("team", "home"),
                    "has_face": bool(p.get("face_embedding")),
                    "face_confidence": p.get("face_confidence", 0.0),
                    "photo_path": p.get("photo_path", ""),
                })
            return json.dumps({"success": True, "profiles": result})
        except Exception as e:
            logger.error(f"get_face_gallery failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def upload_face_photo(self, photo_path, display_name, jersey_number):
        try:
            if self.face_recognition_service is None:
                return json.dumps({"success": False, "error": "FaceRecognitionService not available (insightface not installed)"})
            import cv2
            img = cv2.imread(photo_path)
            if img is None:
                return json.dumps({"success": False, "error": "Could not read image"})
            faces = self.face_recognition_service.detect_faces(img)
            if not faces:
                return json.dumps({"success": False, "error": "No face detected in photo"})
            best = max(faces, key=lambda f: f["confidence"])
            global_id = f"upload_{jersey_number}_{display_name.replace(' ', '_')}"
            profile = await self.storage_service.save_player_profile({
                "global_id": global_id,
                "display_name": display_name,
                "jersey_number": jersey_number,
                "team": "home",
                "face_embedding": json.dumps(best["embedding"]),
                "face_confidence": best["confidence"],
            })
            return json.dumps({
                "success": True, "profile_id": profile,
                "display_name": display_name, "confidence": best["confidence"],
            })
        except Exception as e:
            logger.error(f"upload_face_photo failed: {e}")
            return json.dumps({"success": False, "error": ErrorSanitizer.sanitize_error(e)})

    async def match_faces_in_match(self, match_id):
        try:
            if self.face_recognition_service is None:
                return json.dumps({"success": False, "error": "FaceRecognitionService not available (install insightface)"})
            track_data = self._tracking_cache.get(match_id)
            if not track_data:
                return json.dumps({"success": False, "error": "No tracking data cached. Run analysis first."})
            profiles = await self.storage_service.get_all_player_profiles()
            identified = self.face_recognition_service.identify_players_in_match(profiles, track_data)
            return json.dumps({"success": True, "identified_count": len(identified)})
        except Exception as e:
            logger.error(f"match_faces_in_match failed: {e}")
            return json.dumps({"success": False, "error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Multi-match & quality
    # ================================================================

    async def compare_matches(self, match_id_1, match_id_2, focus):
        self._check_rate_limit()
        try:
            m1 = SecurityValidator.validate_match_id(match_id_1)
            m2 = SecurityValidator.validate_match_id(match_id_2)
            focus = SecurityValidator.sanitize_string(focus, max_length=50)
            if self.multi_match_service is None:
                return json.dumps({"error": "MultiMatchAnalysisService not available"})
            comparison = await self.multi_match_service.compare_matches(m1, m2)
            return json.dumps({
                "match_1": comparison.match_1_name,
                "match_2": comparison.match_2_name,
                "possession_diff": comparison.possession_diff,
                "shots_diff": comparison.shots_diff,
                "formation_diff": comparison.formation_diff,
                "key_differences": comparison.key_differences,
                "tactical_evolution": comparison.tactical_evolution,
            })
        except Exception as e:
            logger.error(f"Compare matches failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_match_quality_report(self, match_id_str):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id_str)
            if self.quality_scoring_service is None:
                return json.dumps({"error": "QualityScoringService not available"})
            scores = await self.quality_scoring_service.get_scores(match_id)
            if scores is None:
                return json.dumps({"error": "No quality scores found"})
            return json.dumps({
                "overall": scores.overall,
                "tracking": scores.tracking,
                "events": scores.events,
                "homography": scores.homography,
                "team_assignment": scores.team_assignment,
            })
        except Exception as e:
            logger.error(f"Quality report failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Team & visualization operations
    # ================================================================

    async def swap_teams(self, match_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            match = await self.storage_service.get_match(match_id)
            if not match:
                return json.dumps({"error": "Match not found"})
            home = match.get("home_team", "Home")
            away = match.get("away_team", "Away")
            await self.storage_service.update_match_teams(match_id=match_id, home_team=away, away_team=home)
            logger.info(f"Swapped teams for match {match_id}: {home} ↔ {away}")
            return json.dumps({"success": True, "home": away, "away": home})
        except Exception as e:
            logger.error(f"swap_teams failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def generate_visualizations(self, match_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            if self.visualization_service is None:
                return json.dumps({"error": "VisualizationService not available"})
            events = await self.storage_service.get_match_events(match_id)
            pass_events = [e for e in events if e.get("type") == "pass" and e.get("completed")]
            if not pass_events:
                return json.dumps({"error": "No pass events to visualize"})
            pass_network_path = None
            heatmap_path = None
            if pass_events:
                player_positions = {}
                for pe in pass_events:
                    meta = pe.get("metadata", {})
                    src = pe.get("from_track_id")
                    dst = pe.get("to_track_id")
                    if src is not None:
                        sx = meta.get("start_x_pct", 0.5) * 105.0
                        sy = meta.get("start_y_pct", 0.5) * 68.0
                        if src not in player_positions:
                            player_positions[src] = (sx, sy)
                    if dst is not None:
                        ex = meta.get("end_x_pct", 0.5) * 105.0
                        ey = meta.get("end_y_pct", 0.5) * 68.0
                        if dst not in player_positions:
                            player_positions[dst] = (ex, ey)
                pass_network_path = await self.visualization_service.generate_pass_network(
                    pass_events=pass_events, player_positions=player_positions,
                    output_name=f"pass_network_{match_id}.png",
                )
                positions_list = list(player_positions.values())
                if positions_list:
                    heatmap_path = await self.visualization_service.generate_heatmap(
                        positions=positions_list, output_name=f"heatmap_{match_id}.png",
                    )
            return json.dumps({
                "success": True,
                "pass_network": str(pass_network_path) if pass_network_path else None,
                "heatmap": str(heatmap_path) if heatmap_path else None,
            })
        except Exception as e:
            logger.error(f"generate_visualizations failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Set-piece analysis
    # ================================================================

    async def check_setpiece_status(self):
        if self.setpiece_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.setpiece_service.available})

    async def analyze_setpieces(self, events_json, home_team):
        if self.setpiece_service is None:
            return json.dumps({"error": "Set-piece service not initialized"})
        try:
            from kawkab.services.setpiece_service import SetPieceEvent
            events_data = json.loads(events_json) if events_json else []
            events = [
                SetPieceEvent(
                    set_piece_type=e.get("set_piece_type", "corner"),
                    minute=e.get("minute", 0),
                    second=e.get("second", 0),
                    team=e.get("team", ""),
                    delivery_x=e.get("delivery_x", 50),
                    delivery_y=e.get("delivery_y", 34),
                    delivery_style=e.get("delivery_style", "lofted"),
                    first_contact_x=e.get("first_contact_x"),
                    first_contact_y=e.get("first_contact_y"),
                    outcome=e.get("outcome", "unknown"),
                )
                for e in events_data
            ]
            away_team = "away" if home_team == "home" else "home"
            report = self.setpiece_service.analyze(events, home_team, away_team)
            return json.dumps({
                "home": {
                    "total_corners": report.home_stats.total_corners,
                    "total_free_kicks": report.home_stats.total_free_kicks,
                    "shots_per_corner": report.home_stats.shots_per_corner,
                    "goals_per_corner": report.home_stats.goals_per_corner,
                    "favorite_target_zone": report.home_stats.favorite_target_zone,
                    "common_routines": report.home_stats.common_routines,
                    "threat_per_set_piece": report.home_stats.threat_per_set_piece,
                },
                "away": {
                    "total_corners": report.away_stats.total_corners,
                    "total_free_kicks": report.away_stats.total_free_kicks,
                    "shots_per_corner": report.away_stats.shots_per_corner,
                    "goals_per_corner": report.away_stats.goals_per_corner,
                    "favorite_target_zone": report.away_stats.favorite_target_zone,
                    "common_routines": report.away_stats.common_routines,
                    "threat_per_set_piece": report.away_stats.threat_per_set_piece,
                },
                "home_threat_total": report.home_threat_total,
                "away_threat_total": report.away_threat_total,
                "set_piece_differential": report.set_piece_differential,
                "notes": report.notes,
            })
        except Exception as e:
            logger.error(f"analyze_setpieces failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Goalkeeper analysis
    # ================================================================

    async def check_goalkeeper_status(self):
        if self.goalkeeper_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.goalkeeper_service.available})

    async def analyze_goalkeeper(self, team, actions_json, shots_json, clean_sheet):
        if self.goalkeeper_service is None:
            return json.dumps({"error": "Goalkeeper service not initialized"})
        try:
            from kawkab.services.goalkeeper_service import GoalkeeperAction
            actions_data = json.loads(actions_json) if actions_json else []
            shots_data = json.loads(shots_json) if shots_json else []
            actions = [
                GoalkeeperAction(
                    action_type=a.get("action_type", "save"),
                    minute=a.get("minute", 0), second=a.get("second", 0),
                    team=a.get("team", team), player_track_id=a.get("player_track_id"),
                    outcome=a.get("outcome", "complete"), quality=a.get("quality", 0.5),
                    x=a.get("x"), y=a.get("y"),
                )
                for a in actions_data
            ]
            stats = self.goalkeeper_service.compute_stats(team, actions, shots_data, clean_sheet=clean_sheet)
            return json.dumps({
                "team": stats.team, "saves": stats.saves,
                "goals_conceded": stats.goals_conceded, "shots_faced": stats.shots_faced,
                "save_rate": stats.save_rate, "goals_prevented_xgot": stats.goals_prevented_xgot,
                "xgot_per_shot": stats.xgot_per_shot,
                "crosses_claimed": stats.crosses_claimed, "crosses_punched": stats.crosses_punched,
                "crosses_missed": stats.crosses_missed, "sweep_actions": stats.sweep_actions,
                "short_distribution_attempts": stats.short_distribution_attempts,
                "short_distribution_successful": stats.short_distribution_successful,
                "long_distribution_attempts": stats.long_distribution_attempts,
                "long_distribution_successful": stats.long_distribution_successful,
                "clean_sheet": stats.clean_sheet, "notes": stats.notes,
            })
        except Exception as e:
            logger.error(f"analyze_goalkeeper failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def compute_xgot(self, shot_x, shot_y, body_part, one_on_one):
        if self.goalkeeper_service is None:
            return json.dumps({"error": "Goalkeeper service not initialized"})
        try:
            xgot = self.goalkeeper_service.compute_xgot_simple(
                float(shot_x), float(shot_y), body_part or "foot", bool(one_on_one)
            )
            return json.dumps({"xgot": round(xgot, 3)})
        except Exception as e:
            logger.error(f"compute_xgot failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Substitution analysis
    # ================================================================

    async def check_substitution_status(self):
        if self.substitution_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.substitution_service.available})

    async def analyze_substitutions(self, team, subs_json, events_json):
        if self.substitution_service is None:
            return json.dumps({"error": "Substitution service not initialized"})
        try:
            from kawkab.services.substitution_service import SubstitutionEvent
            subs_data = json.loads(subs_json) if subs_json else []
            events = json.loads(events_json) if events_json else []
            subs = [
                SubstitutionEvent(
                    minute=s.get("minute", 0), second=s.get("second", 0),
                    team=s.get("team", team),
                    player_off_track_id=s.get("player_off_track_id"),
                    player_off_name=s.get("player_off_name"),
                    player_on_track_id=s.get("player_on_track_id"),
                    player_on_name=s.get("player_on_name"),
                    formation_before=s.get("formation_before"),
                    formation_after=s.get("formation_after"),
                    position_changed=s.get("position_changed", False),
                )
                for s in subs_data
            ]
            report = self.substitution_service.analyze(team, subs, events)
            return json.dumps({
                "team": report.team, "total_impact": report.total_impact,
                "avg_impact": report.avg_impact,
                "tactical_changes": report.tactical_changes,
                "formation_changes": report.formation_changes,
                "best_sub": {
                    "minute": report.best_sub.substitution.minute,
                    "rating": report.best_sub.rating,
                    "verdict": report.best_sub.verdict,
                    "notes": report.best_sub.notes,
                } if report.best_sub else None,
                "worst_sub": {
                    "minute": report.worst_sub.substitution.minute,
                    "rating": report.worst_sub.rating,
                    "verdict": report.worst_sub.verdict,
                    "notes": report.worst_sub.notes,
                } if report.worst_sub else None,
                "impacts": [
                    {
                        "minute": i.substitution.minute,
                        "player_on": i.substitution.player_on_name,
                        "player_off": i.substitution.player_off_name,
                        "rating": i.rating, "verdict": i.verdict,
                        "xg_delta": i.xg_delta, "possession_delta": i.possession_delta,
                        "goals_for": i.goals_for, "goals_against": i.goals_against,
                        "notes": i.notes,
                    }
                    for i in report.impacts
                ],
            })
        except Exception as e:
            logger.error(f"analyze_substitutions failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Possession analysis
    # ================================================================

    async def check_possession_status(self):
        if self.possession_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.possession_service.available})

    async def analyze_possession(self, home_team, away_team, events_json):
        if self.possession_service is None:
            return json.dumps({"error": "Possession service not initialized"})
        try:
            events = json.loads(events_json) if events_json else []
            report = self.possession_service.analyze(home_team, away_team, events)
            return json.dumps({
                "home_possession_pct": report.home_possession_pct,
                "away_possession_pct": report.away_possession_pct,
                "counter_presses": report.counter_presses,
                "avg_chain_duration_s": report.avg_chain_duration_s,
                "longest_chain_s": report.longest_chain_s,
                "home_chains_count": len(report.home_chains),
                "away_chains_count": len(report.away_chains),
                "home_player_stats": {
                    str(tid): {
                        "touches": s.touches,
                        "possession_time_s": round(s.total_possession_time_s, 1),
                        "successful_passes": s.successful_passes,
                        "failed_passes": s.failed_passes,
                    }
                    for tid, s in report.home_player_stats.items()
                },
                "away_player_stats": {
                    str(tid): {
                        "touches": s.touches,
                        "possession_time_s": round(s.total_possession_time_s, 1),
                        "successful_passes": s.successful_passes,
                        "failed_passes": s.failed_passes,
                    }
                    for tid, s in report.away_player_stats.items()
                },
                "notes": report.notes,
            })
        except Exception as e:
            logger.error(f"analyze_possession failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Psychology analysis
    # ================================================================

    async def check_psychology_status(self):
        if self.psychology_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.psychology_service.available})

    async def analyze_match_psychology(self, match_id, home_team, away_team, events_json):
        self._check_rate_limit()
        if self.psychology_service is None:
            return json.dumps({"error": "Psychology service not initialized"})
        try:
            events = json.loads(events_json) if events_json else []
            report = self.psychology_service.analyze(match_id, home_team, away_team, events)
            return json.dumps({
                "match_id": report.match_id,
                "home_team": report.home_team,
                "away_team": report.away_team,
                "score_state_transitions": [
                    {
                        "minute": t.minute, "second": t.second, "team": t.team,
                        "from_state": t.from_state.value, "to_state": t.to_state.value,
                        "trigger": t.trigger_event,
                    }
                    for t in report.score_state_transitions
                ],
                "momentum_timeline": [
                    {"minute": m.minute, "home": m.home_momentum, "away": m.away_momentum}
                    for m in report.momentum_timeline[::3]
                ],
                "psychology_events": [
                    {
                        "type": e.event_type.value, "minute": e.minute,
                        "second": e.second, "team": e.team,
                        "description": e.description, "severity": e.severity,
                    }
                    for e in report.psychology_events
                ],
                "post_goal_lull_count": report.post_goal_lull_count,
                "comeback_count": report.comeback_count,
                "capitulation_count": report.capitulation_count,
                "avg_late_game_passing_drop": report.avg_late_game_passing_drop,
                "notes": report.notes,
            })
        except Exception as e:
            logger.error(f"analyze_match_psychology failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Football Rules
    # ================================================================

    async def check_rules_status(self):
        if self.football_rules_service is None:
            return json.dumps({"available": False})
        return json.dumps({
            "available": self.football_rules_service.available,
            "laws_count": len(self.football_rules_service._laws),
        })

    async def get_law_summary(self, law_number):
        if self.football_rules_service is None:
            return json.dumps({"error": "Rules service not initialized"})
        law = self.football_rules_service.get_law_summary(law_number)
        if not law:
            return json.dumps({"error": f"Law {law_number} not found"})
        return json.dumps(law)

    async def get_all_laws(self):
        if self.football_rules_service is None:
            return json.dumps({"laws": []})
        return json.dumps({"laws": self.football_rules_service.get_all_laws()})

    async def classify_event_rule(self, event_type, x, y, side):
        if self.football_rules_service is None:
            return json.dumps({"error": "Rules service not initialized"})
        try:
            ref = self.football_rules_service.classify_event(event_type, x, y, side)
            return json.dumps({
                "law": ref.law, "law_name": ref.law_name,
                "restart": ref.restart.value if ref.restart else None,
                "description": ref.description, "card_likely": ref.card_likely,
            })
        except Exception as e:
            logger.error(f"classify_event_rule failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def check_offside(self, attacker_x, defender_x, ball_x, attacking_direction):
        if self.football_rules_service is None:
            return json.dumps({"error": "Rules service not initialized"})
        try:
            result = self.football_rules_service.is_offside(
                attacker_x, defender_x, ball_x, attacking_direction
            )
            return json.dumps({
                "is_offside": result.is_offside,
                "attacker_x": result.attacker_x,
                "second_last_defender_x": result.second_last_defender_x,
                "ball_x": result.ball_x,
                "explanation": result.explanation,
            })
        except Exception as e:
            logger.error(f"check_offside failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Card Detection
    # ================================================================

    async def check_cards_status(self):
        if self.card_detection_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.card_detection_service.available})

    async def infer_cards_tactically(self, events_json):
        if self.card_detection_service is None:
            return json.dumps({"error": "Card detection service not initialized"})
        try:
            events = json.loads(events_json) if events_json else []
            cards = self.card_detection_service.infer_cards_tactically(events)
            return json.dumps({
                "cards": [
                    {
                        "card_type": c.card_type.value, "minute": c.minute,
                        "second": c.second, "player_track_id": c.player_track_id,
                        "player_name": c.player_name, "team": c.team,
                        "source": c.source.value, "confidence": c.confidence,
                        "description": c.description,
                    }
                    for c in cards
                ]
            })
        except Exception as e:
            logger.error(f"infer_cards_tactically failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def fetch_external_cards(self, match_id):
        if self.card_detection_service is None:
            return json.dumps({"error": "Card detection service not initialized"})
        try:
            cards = await self.card_detection_service.fetch_external_cards(
                match_id, statsbomb_service=self.statsbomb_service,
            )
            return json.dumps({
                "cards": [
                    {
                        "card_type": c.card_type.value, "minute": c.minute,
                        "second": c.second, "player_name": c.player_name,
                        "team": c.team, "source": c.source.value,
                        "confidence": c.confidence, "description": c.description,
                    }
                    for c in cards
                ]
            })
        except Exception as e:
            logger.error(f"fetch_external_cards failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Pose analysis
    # ================================================================

    async def check_pose_status(self):
        if self.pose_analysis_service is None:
            return json.dumps({"available": False})
        try:
            return json.dumps({"available": self.pose_analysis_service.available})
        except Exception:
            return json.dumps({"available": False})

    async def get_activity_summary(self, track_id):
        if self.pose_analysis_service is None:
            return json.dumps({"summary": {}})
        try:
            summary = self.pose_analysis_service.summarize_activity(track_id)
            return json.dumps({"summary": summary})
        except Exception as e:
            logger.error(f"get_activity_summary failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_activity_segments(self, track_id):
        if self.pose_analysis_service is None:
            return json.dumps({"segments": []})
        try:
            segs = self.pose_analysis_service.get_activity_segments(track_id)
            return json.dumps({
                "segments": [
                    {
                        "activity": s.activity, "start_time": s.start_time,
                        "end_time": s.end_time, "duration_s": s.duration_s,
                        "avg_speed_kmh": s.avg_speed_kmh,
                    }
                    for s in segs
                ]
            })
        except Exception as e:
            logger.error(f"get_activity_segments failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # MuJoCo ball trajectory
    # ================================================================

    async def check_mujoco_status(self):
        if self.mujoco_ball_service is None:
            return json.dumps({"available": False, "uses_mujoco": False})
        return json.dumps({
            "available": self.mujoco_ball_service.available,
            "uses_mujoco": self.mujoco_ball_service.uses_mujoco,
        })

    async def get_setpiece_presets(self):
        if self.mujoco_ball_service is None:
            return json.dumps({"presets": []})
        return json.dumps({"presets": self.mujoco_ball_service.get_preset_setpieces()})

    async def simulate_trajectory(self, initial_speed, launch_angle_deg, spin_rps, direction_deg, duration_s):
        if self.mujoco_ball_service is None:
            return json.dumps({"error": "MuJoCo service not initialized"})
        try:
            result = await self.mujoco_ball_service.simulate(
                initial_speed=float(initial_speed),
                launch_angle_deg=float(launch_angle_deg),
                spin_rps=float(spin_rps),
                direction_deg=float(direction_deg),
                duration_s=float(duration_s) if duration_s > 0 else 2.5,
            )
            return json.dumps({
                "method": result.method,
                "landing_x": result.landing_x,
                "landing_y": result.landing_y,
                "max_height": result.max_height,
                "duration_s": result.duration_s,
                "final_speed_mps": result.final_speed_mps,
                "points": [{"t": p.t, "x": p.x, "y": p.y, "z": p.z} for p in result.points[::5]],
            })
        except Exception as e:
            logger.error(f"simulate_trajectory failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # FluidX3D
    # ================================================================

    async def check_fluidx3d_status(self):
        if self.fluidx3d_service is None:
            return json.dumps({
                "available": False,
                "license_notice": "FluidX3D is free for non-commercial use only.",
            })
        return json.dumps({
            "available": self.fluidx3d_service.available,
            "license_notice": self.fluidx3d_service.license_notice,
        })

    async def simulate_ball_cfd(self, wind_speed, spin_rps, ball_radius):
        if self.fluidx3d_service is None:
            return json.dumps({"error": "FluidX3D service not initialized"})
        try:
            result = await self.fluidx3d_service.simulate_ball_aerodynamics(
                ball_radius=float(ball_radius) if ball_radius > 0 else 0.11,
                wind_speed=float(wind_speed),
                spin_rps=float(spin_rps),
            )
            return json.dumps({
                "success": result.success, "method": result.method,
                "notes": result.notes, "error": result.error,
            })
        except Exception as e:
            logger.error(f"simulate_ball_cfd failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Weather
    # ================================================================

    async def check_weather_status(self):
        if self.weather_service is None:
            return json.dumps({"available": False})
        return json.dumps({
            "available": self.weather_service.available,
            "has_video_classifier": self.weather_service.has_video_classifier,
        })

    async def fetch_match_weather(self, latitude, longitude, date, is_forecast):
        if self.weather_service is None:
            return json.dumps({"error": "Weather service not initialized"})
        try:
            result = await self.weather_service.fetch_conditions(
                latitude, longitude, date, is_forecast=is_forecast
            )
            if result is None:
                return json.dumps({"error": "Failed to fetch weather"})
            return json.dumps({
                "temperature_c": result.temperature_c,
                "precipitation_mm": result.precipitation_mm,
                "wind_speed_kmh": result.wind_speed_kmh,
                "humidity_pct": result.humidity_pct,
                "conditions": result.conditions,
                "pitch_state": result.pitch_state.value,
                "source": result.source.value,
                "is_daylight": result.is_daylight,
            })
        except Exception as e:
            logger.error(f"fetch_match_weather failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def set_manual_weather(self, temperature, precipitation, wind, humidity, conditions):
        if self.weather_service is None:
            return json.dumps({"error": "Weather service not initialized"})
        from kawkab.services.weather_service import WeatherService
        result = WeatherService.from_manual(
            temperature_c=temperature, precipitation_mm=precipitation,
            wind_speed_kmh=wind, humidity_pct=humidity, conditions=conditions,
        )
        impact = WeatherService.analyze_impact(result)
        return json.dumps({
            "conditions": {
                "temperature_c": result.temperature_c,
                "precipitation_mm": result.precipitation_mm,
                "wind_speed_kmh": result.wind_speed_kmh,
                "humidity_pct": result.humidity_pct,
                "conditions": result.conditions,
                "pitch_state": result.pitch_state.value,
            },
            "impact": {
                "goals_delta": impact.expected_goals_delta,
                "passing_delta_pct": impact.passing_accuracy_delta_pct,
                "sprint_delta_pct": impact.sprint_distance_delta_pct,
                "set_piece_advantage": impact.set_piece_advantage,
                "notes": impact.notes,
            },
        })

    async def analyze_weather_impact(self, temperature, precipitation, wind, humidity, conditions):
        if self.weather_service is None:
            return json.dumps({"error": "Weather service not initialized"})
        try:
            from kawkab.services.weather_service import WeatherService
            wc = WeatherService.from_manual(
                temperature_c=temperature, precipitation_mm=precipitation,
                wind_speed_kmh=wind, humidity_pct=humidity, conditions=conditions,
            )
            impact = WeatherService.analyze_impact(wc)
            return json.dumps({
                "goals_delta": impact.expected_goals_delta,
                "passing_delta_pct": impact.passing_accuracy_delta_pct,
                "sprint_delta_pct": impact.sprint_distance_delta_pct,
                "set_piece_advantage": impact.set_piece_advantage,
                "notes": impact.notes,
            })
        except Exception as e:
            logger.error(f"analyze_weather_impact failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def check_raindrop_status(self):
        if self.weather_service is None:
            return json.dumps({"available": False})
        return json.dumps({
            "available": self.weather_service.has_raindrop_detector,
            "has_cnn": (
                self.weather_service._raindrop_service.has_cnn
                if self.weather_service._raindrop_service else False
            ),
        })

    async def check_weather_classifier_status(self):
        if self.weather_service is None:
            return json.dumps({"available": False})
        return json.dumps({
            "available": self.weather_service.has_multi_class_classifier,
            "has_cnn": (
                self.weather_service._weather_classifier.has_cnn
                if self.weather_service._weather_classifier else False
            ),
        })

    async def detect_raindrops_in_video(self, video_path, sample_every_n, max_frames):
        if self.weather_service is None or not self.weather_service.has_raindrop_detector:
            return json.dumps({"error": "Raindrop service not available"})
        try:
            validated_path = SecurityValidator.validate_video_path(str(video_path))
            result = self.weather_service._raindrop_service.detect_from_video_file(
                str(validated_path), sample_every_n, max_frames
            )
            return json.dumps({
                "frame_count": result.frame_count,
                "raindrop_count": result.raindrop_count,
                "raindrop_density": result.raindrop_density,
                "avg_confidence": result.avg_confidence,
                "is_rainy": result.is_rainy,
                "method": result.method,
            })
        except Exception as e:
            logger.error(f"detect_raindrops_in_video failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def classify_video_weather(self, video_path):
        if self.weather_service is None:
            return json.dumps({"error": "Weather service not available"})
        try:
            validated_path = SecurityValidator.validate_video_path(str(video_path))
            import cv2
            cap = cv2.VideoCapture(str(validated_path))
            if not cap.isOpened():
                return json.dumps({"error": f"Could not open video: {video_path}"})
            frames = []
            frame_idx = 0
            sampled = 0
            while sampled < 15:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % 30 == 0:
                    frames.append(frame)
                    sampled += 1
                frame_idx += 1
            cap.release()
            if not frames:
                return json.dumps({"error": "No frames read from video"})
            result = self.weather_service.classify_from_video_advanced(frames)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"classify_video_weather failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Phase 2.3 — Tactical Periods (from events)
    # ================================================================

    async def get_tactical_periods(self, match_id):
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)
            if not events:
                return json.dumps({"phases": []})

            total_time = max(1.0, events[-1].get("timestamp", 0) - events[0].get("timestamp", 0))
            phase_names = {"settled_possession", "transition", "counter", "set_piece", "direct"}
            phases = []
            window = 5.0
            t_start = events[0].get("timestamp", 0)

            i = 0
            while i < len(events):
                t = events[i].get("timestamp", 0)
                window_end = t + window
                window_events = [e for e in events if t <= e.get("timestamp", 0) < window_end]
                types_in_window = [e.get("event_type", "") for e in window_events]
                type_counts = {}
                for et in types_in_window:
                    type_counts[et] = type_counts.get(et, 0) + 1

                if any("corner" in e.get("event_type", "") or "free_kick" in e.get("event_type", "") or "throw_in" == e.get("event_type", "") for e in window_events):
                    label = "set_piece"
                elif type_counts.get("counter", 0) >= 2:
                    label = "transition"
                elif type_counts.get("pass", 0) >= 3:
                    label = "settled_possession"
                elif type_counts.get("tackle", 0) >= 2 or type_counts.get("interception", 0) >= 2:
                    label = "transition"
                elif type_counts.get("carry", 0) >= 2 and type_counts.get("shot", 0) > 0:
                    label = "direct"
                else:
                    label = "settled_possession"

                phase_end = window_end
                j = i + 1
                while j < len(events):
                    if events[j].get("timestamp", 0) > phase_end:
                        break
                    j += 1

                if phases and phases[-1]["label"] == label:
                    phases[-1]["end"] = max(phases[-1]["end"], min(t + window, total_time))
                    phases[-1]["duration_s"] = round(phases[-1]["end"] - phases[-1]["start"], 1)
                else:
                    phases.append({
                        "start": round(t, 1),
                        "end": round(min(t + window, total_time), 1),
                        "label": label,
                        "duration_s": round(min(window, total_time - t), 1),
                    })
                i = j

            counts = {}
            for p in phases:
                counts[p["label"]] = counts.get(p["label"], 0) + p["duration_s"]
            return json.dumps({
                "phases": phases,
                "press_pct": round(counts.get("transition", 0) / total_time * 100, 1) if total_time else 0,
                "settled_possession_pct": round(counts.get("settled_possession", 0) / total_time * 100, 1) if total_time else 0,
                "transition_pct": round(counts.get("transition", 0) / total_time * 100, 1) if total_time else 0,
            })
        except Exception as e:
            logger.error(f"get_tactical_periods failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Phase 2.4 — Formation Analysis (from events)
    # ================================================================

    async def analyze_formation(self, match_id):
        try:
            from kawkab.core.formation_analysis import FormationAnalyzer
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)
            players = await self.storage_service.get_match_players(match_id)

            home_positions = {}
            away_positions = {}
            for ev in events:
                meta = ev.get("metadata", {})
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                tid = ev.get("from_track_id") or ev.get("player_track_id", 0)
                team = ev.get("team", "home")
                x = meta.get("start_x_pct", 0.5) if meta else 0.5
                y = meta.get("start_y_pct", 0.5) if meta else 0.5
                if team == "home":
                    home_positions[tid] = (x, y)
                else:
                    away_positions[tid] = (x, y)

            analyzer = FormationAnalyzer()
            result = {}
            for side, pos in [("home", home_positions), ("away", away_positions)]:
                if not pos:
                    result[side] = {"formation": "unknown"}
                    continue
                positions = list(pos.values())
                frames = [{"timestamp": 0, "home_positions": positions if side == "home" else [],
                           "away_positions": positions if side == "away" else [],
                           "possession": True, "ball_pos": None}]
                report = analyzer.analyze_team_shape(frames, team=side)
                result[side] = report.to_dict()

            return json.dumps({"success": True, **result})
        except Exception as e:
            logger.error(f"analyze_formation failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Tactical Shape Analysis
    # ================================================================

    async def analyze_tactical_shapes(self, match_id):
        try:
            from kawkab.core.tactical_shape_analyzer import TacticalShapeAnalyzer
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)
            if not events:
                return json.dumps({"home": {}, "away": {}})
            analyzer = TacticalShapeAnalyzer()
            home_report = analyzer.analyze_shapes(events, team="home")
            away_report = analyzer.analyze_shapes(events, team="away")
            return json.dumps({"success": True, "home": home_report.to_dict(), "away": away_report.to_dict()})
        except Exception as e:
            logger.error(f"analyze_tactical_shapes failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Pressing Classification
    # ================================================================

    async def classify_pressing(self, match_id):
        try:
            from kawkab.core.pressing_classifier import classify_pressing_system
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)
            if not events:
                return json.dumps({"home": {}, "away": {}})
            home_report = classify_pressing_system(events, team="home")
            away_report = classify_pressing_system(events, team="away")
            return json.dumps({"success": True, "home": home_report.to_dict(), "away": away_report.to_dict()})
        except Exception as e:
            logger.error(f"classify_pressing failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Comprehensive Tactical Report
    # ================================================================

    async def get_tactical_report(self, match_id):
        try:
            from kawkab.core.tactical_report import generate_tactical_report
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)
            if not events:
                return json.dumps({"error": "No events"})
            report = generate_tactical_report(events, match_id=match_id)
            return json.dumps({"success": True, **report.to_dict()})
        except Exception as e:
            logger.error(f"get_tactical_report failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Phase 3 — AI NL Query (ask a question about a match)
    # ================================================================

    async def ask_llm(self, match_id, question):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            question = SecurityValidator.sanitize_string(question, max_length=500)
            events = await self.storage_service.get_match_events(match_id)
            match_data = await self.storage_service.get_match(match_id)

            event_summary = {}
            for ev in events:
                et = ev.get("event_type", "unknown")
                event_summary[et] = event_summary.get(et, 0) + 1

            home_team = (match_data or {}).get("home_team", "Home")
            away_team = (match_data or {}).get("away_team", "Away")

            context = (
                f"Match: {home_team} vs {away_team}\n"
                f"Total events: {len(events)}\n"
                f"Event breakdown: {json.dumps(event_summary)}\n"
            )
            system_prompt = (
                "You are a professional football analyst coach. Answer questions about a match "
                "based on the data provided. Be specific, tactical, and concise (max 3 paragraphs). "
                "If the data doesn't support a claim, say so."
            )
            full_prompt = f"{context}\n\nQuestion: {question}\n\nAnalysis:"
            answer = await self.llm_service.generate(full_prompt, system=system_prompt)
            return json.dumps({"success": True, "answer": answer, "event_summary": event_summary})
        except Exception as e:
            logger.error(f"ask_llm failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Phase 4 — Player Rating Index 0-100
    # ================================================================

    async def get_player_rating(self, match_id, track_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            track_id = SecurityValidator.validate_match_id(track_id)
            events = await self.storage_service.get_match_events(match_id)
            players = await self.storage_service.get_match_players(match_id)

            player_events = [e for e in events if e.get("from_track_id") == track_id or e.get("player_track_id") == track_id]
            if not player_events:
                return json.dumps({"rating": 0, "components": {}})

            passes = sum(1 for e in player_events if e.get("event_type") == "pass")
            completed = sum(1 for e in player_events if e.get("event_type") == "pass" and e.get("completed"))
            shots = sum(1 for e in player_events if e.get("event_type") == "shot")
            tackles = sum(1 for e in player_events if e.get("event_type") == "tackle")
            interceptions = sum(1 for e in player_events if e.get("event_type") == "interception")
            carries = sum(1 for e in player_events if e.get("event_type") == "carry")
            dribbles = sum(1 for e in player_events if e.get("event_type") == "dribble")
            goals = sum(1 for e in player_events if e.get("event_type") == "goal")

            pass_acc = completed / max(passes, 1)
            shot_score = min(shots * 20, 100)
            tackle_score = min(tackles * 15, 100)
            carry_score = min(carries * 10, 100)
            dribble_score = min(dribbles * 15, 100)
            goal_score = min(goals * 30, 100)
            volume = min(len(player_events) * 2, 100)

            components = {
                "pass_accuracy": round(pass_acc * 100, 1),
                "shot_impact": shot_score,
                "tackle_effectiveness": tackle_score,
                "carry_progression": carry_score,
                "dribble_success": dribble_score,
                "goal_contribution": goal_score,
                "event_volume": volume,
            }
            rating = round((pass_acc * 30 + shot_score * 0.1 + tackle_score * 0.15 + carry_score * 0.1 + dribble_score * 0.15 + goal_score * 0.1 + volume * 0.1), 1)
            return json.dumps({"rating": min(rating, 100), "components": components})
        except Exception as e:
            logger.error(f"get_player_rating failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Phase 4 — Squad Management
    # ================================================================

    async def get_squad_summary(self, match_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)
            players = await self.storage_service.get_match_players(match_id)

            squad = {}
            for p in (players or []):
                tid = p.get("track_id", p.get("id", 0))
                name = p.get("name", f"Player #{tid}")
                team = p.get("team", "unknown")
                if team not in squad:
                    squad[team] = []
                p_events = [e for e in events if e.get("from_track_id") == tid or e.get("player_track_id") == tid]
                squad[team].append({
                    "track_id": tid,
                    "name": name,
                    "jersey": p.get("jersey_number", ""),
                    "position": p.get("position", ""),
                    "events": len(p_events),
                    "passes": sum(1 for e in p_events if e.get("event_type") == "pass"),
                    "shots": sum(1 for e in p_events if e.get("event_type") == "shot"),
                    "tackles": sum(1 for e in p_events if e.get("event_type") == "tackle"),
                })

            return json.dumps({"success": True, "squad": squad, "total_players": len(players or [])})
        except Exception as e:
            logger.error(f"get_squad_summary failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Phase 6 Sprint 1 — Injury Risk
    # ================================================================

    async def get_injury_risk(self, match_id, track_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            track_id = SecurityValidator.validate_match_id(track_id) if isinstance(track_id, str) else int(track_id)
            predictor = self.injury_risk_predictor
            players = await self.storage_service.get_match_players(match_id)
            player = None
            for p in (players or []):
                if p.get("track_id") == track_id:
                    player = p
                    break
            if not player:
                return json.dumps({"error": "Player not found"})
            events = await self.storage_service.get_match_events(match_id)
            p_events = [e for e in events if e.get("from_track_id") == track_id or e.get("player_track_id") == track_id]
            sprint_count = sum(1 for e in p_events if e.get("event_type") == "sprint")
            workload = [float(p.get(f"workload_d{i}", 0)) for i in range(1, 29)]
            fatigue = float(p.get("fatigue_index", 0))
            days_rest = int(p.get("days_since_last_rest", 0))
            position = str(p.get("position", "MID"))
            dist_km = float(p.get("distance_covered_m", 0)) / 1000.0
            profile = {
                "acwr": 1.0, "recent_sprint_count": sprint_count,
                "recent_distance_km": dist_km, "fatigue_index": fatigue,
                "position": position, "days_since_last_rest": days_rest,
            }
            acwr_result = predictor.compute_acwr_overload(workload) if len(workload) >= 7 else {"acwr": 1.0, "risk_level": "moderate", "recommendation": "insufficient data"}
            profile["acwr"] = acwr_result["acwr"]
            risk = predictor.predict_injury_risk(profile)
            rec = predictor.compute_recovery_recommendation(risk["risk_score"], position)
            return json.dumps({
                "success": True,
                "track_id": track_id,
                "risk_score": risk["risk_score"],
                "risk_category": risk["risk_category"],
                "acwr": round(acwr_result["acwr"], 3),
                "acwr_risk_level": acwr_result["risk_level"],
                "recovery_recommendation": rec,
                "key_factors": risk["key_risk_factors"],
            })
        except Exception as e:
            logger.error(f"get_injury_risk failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_squad_injury_report(self, match_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            players = await self.storage_service.get_match_players(match_id)
            predictor = self.injury_risk_predictor
            events = await self.storage_service.get_match_events(match_id)
            home_players = []
            away_players = []
            total_risk_home = 0.0
            total_risk_away = 0.0
            high_risk_count = 0
            for p in (players or []):
                tid = p.get("track_id")
                if tid is None:
                    continue
                team = p.get("team", "unknown")
                p_events = [e for e in events if e.get("from_track_id") == tid or e.get("player_track_id") == tid]
                sprint_count = sum(1 for e in p_events if e.get("event_type") == "sprint")
                workload = [float(p.get(f"workload_d{i}", 0)) for i in range(1, 29)]
                fatigue = float(p.get("fatigue_index", 0))
                days_rest = int(p.get("days_since_last_rest", 0))
                position = str(p.get("position", "MID"))
                dist_km = float(p.get("distance_covered_m", 0)) / 1000.0
                profile = {
                    "acwr": 1.0, "recent_sprint_count": sprint_count,
                    "recent_distance_km": dist_km, "fatigue_index": fatigue,
                    "position": position, "days_since_last_rest": days_rest,
                }
                acwr_result = predictor.compute_acwr_overload(workload) if len(workload) >= 7 else {"acwr": 1.0, "risk_level": "moderate", "recommendation": "insufficient data"}
                profile["acwr"] = acwr_result["acwr"]
                risk = predictor.predict_injury_risk(profile)
                rec = predictor.compute_recovery_recommendation(risk["risk_score"], position)
                entry = {
                    "track_id": tid,
                    "name": p.get("name", f"Player #{tid}"),
                    "jersey": p.get("jersey_number", ""),
                    "position": position,
                    "risk_score": risk["risk_score"],
                    "risk_category": risk["risk_category"],
                    "acwr": round(acwr_result["acwr"], 3),
                    "recovery_recommendation": rec,
                    "key_factors": risk["key_risk_factors"],
                }
                if team in ("home", "Home", "HOME"):
                    home_players.append(entry)
                    total_risk_home += risk["risk_score"]
                else:
                    away_players.append(entry)
                    total_risk_away += risk["risk_score"]
                if risk["risk_category"] in ("high", "critical"):
                    high_risk_count += 1
            avg_home = round(total_risk_home / len(home_players), 3) if home_players else 0
            avg_away = round(total_risk_away / len(away_players), 3) if away_players else 0
            return json.dumps({
                "success": True,
                "home_players": home_players,
                "away_players": away_players,
                "avg_risk_home": avg_home,
                "avg_risk_away": avg_away,
                "high_risk_count": high_risk_count,
                "total_players": len(home_players) + len(away_players),
            })
        except Exception as e:
            logger.error(f"get_squad_injury_report failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Phase 6 Sprint 1 — Training Plan Auto-Generate
    # ================================================================

    async def generate_training_plan(self, match_id):
        self._check_rate_limit()
        try:
            match_id_val = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id_val)
            from kawkab.services.reasoning_service import Diagnosis, DiagnosisReport
            mock_diag = Diagnosis(
                rule_id="phase6_gen",
                rule_name="Match-generated training plan",
                rule_name_ar="خطة تدريب مولّدة من المباراة",
                category="general",
                severity="medium",
                confidence=0.65,
                evidence={"event_count": len(events)},
                explanation="Auto-generated training plan based on match events",
                explanation_ar="خطة تدريب مولّدة تلقائياً بناءً على أحداث المباراة",
                recommended_drills=[],
            )
            report = DiagnosisReport(
                match_id=match_id_val,
                diagnoses=[mock_diag],
                overall_assessment="Training plan generated from match data",
                overall_assessment_ar="تم إنشاء خطة التدريب من بيانات المباراة",
                priority_actions=["Improve based on match analysis"],
                priority_actions_ar=["التحسين بناءً على تحليل المباراة"],
                confidence=0.65,
            )
            gen = self.training_plan_generator
            plan = await gen.generate_plan(report, duration_weeks=4, training_days_per_week=3, language="en")
            return json.dumps({"success": True, "plan": gen.export_to_dict(plan)})
        except Exception as e:
            logger.error(f"generate_training_plan failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Wave B — Season Dashboard
    # ================================================================

    async def get_season_summary(self):
        self._check_rate_limit()
        try:
            matches = await self.storage_service.get_all_matches()
            if not matches:
                return json.dumps({"total_matches": 0})

            total = len(matches)
            total_events = 0
            home_wins = 0
            away_wins = 0
            draws = 0
            total_xg = 0.0
            total_shots = 0

            match_list = []
            for m in matches:
                mid = m.get("id", 0)
                events = await self.storage_service.get_match_events(mid) if mid else []
                ev_count = len(events)
                total_events += ev_count
                shots = sum(1 for e in events if e.get("event_type") == "shot")
                total_shots += shots
                xg = sum(e.get("metadata", {}).get("xg", 0) if isinstance(e.get("metadata"), dict) else 0 for e in events)
                total_xg += xg
                match_list.append({
                    "id": mid,
                    "name": m.get("name", ""),
                    "home_team": m.get("home_team", "Home"),
                    "away_team": m.get("away_team", "Away"),
                    "date": m.get("match_date", ""),
                    "events": ev_count,
                    "shots": shots,
                })

            return json.dumps({
                "total_matches": total,
                "total_events": total_events,
                "total_shots": total_shots,
                "avg_xg": round(total_xg / max(total, 1), 3),
                "matches": match_list,
            })
        except Exception as e:
            logger.error(f"get_season_summary failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Wave C — Training Plan (get drills + save session)
    # ================================================================

    async def get_all_drills(self):
        self._check_rate_limit()
        try:
            await self.knowledge_service.initialize()
            drills = self.knowledge_service.drills
            drill_list = []
            for d in (drills or []):
                drill_list.append({
                    "id": d.get("id", ""),
                    "name": d.get("name", "Unknown Drill"),
                    "category": d.get("category", "general"),
                    "difficulty": d.get("difficulty", "medium"),
                    "duration_min": d.get("duration_min", 15),
                    "description": d.get("description", ""),
                    "goals": d.get("goals", []),
                    "equipment": d.get("equipment", []),
                })
            return json.dumps({"drills": drill_list, "total": len(drill_list)})
        except Exception as e:
            logger.error(f"get_all_drills failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Wave E — Scout Portal
    # ================================================================

    async def scout_search_players(self, query, position=""):
        self._check_rate_limit()
        try:
            # Try real player search database first
            try:
                from kawkab.core.player_search import search_players, SearchCriteria
                import os
                db_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "players.json")
                if os.path.exists(db_path):
                    with open(db_path) as f:
                        import json as _json
                        player_db = _json.load(f)
                else:
                    player_db = []
                criteria = SearchCriteria(limit=20)
                if position:
                    criteria.positions = [position.upper()]
                results = search_players(criteria, player_db) if player_db else []
                query_lower = query.lower().strip()
                if query_lower:
                    results = [r for r in results if query_lower in (r.player_name or "").lower()]
                player_list = []
                for r in results:
                    player_list.append({
                        "track_id": abs(hash(r.player_id)) % 100000,
                        "name": r.player_name,
                        "position": r.position,
                        "team": r.team if hasattr(r, "team") else "",
                        "age": r.age,
                        "matches": r.stats.get("matches", 0),
                        "goals": r.stats.get("goals", 0),
                        "assists": r.stats.get("assists", 0),
                        "xg": r.stats.get("xg", 0),
                        "passes": r.stats.get("passes", 0),
                        "tackles": r.stats.get("tackles", 0),
                    })
                return json.dumps({"results": player_list, "total": len(player_list)})
            except Exception:
                # Fallback: return mock results for common queries
                mock_db = [
                    {"name": "Erling Haaland", "position": "FW", "team": "Manchester City", "age": 22, "goals": 32, "assists": 5, "xg": 28.5, "passes": 412, "tackles": 12, "matches": 28},
                    {"name": "Kevin De Bruyne", "position": "MF", "team": "Manchester City", "age": 30, "goals": 8, "assists": 16, "xg": 7.2, "passes": 1250, "tackles": 34, "matches": 25},
                    {"name": "Virgil van Dijk", "position": "DF", "team": "Liverpool", "age": 31, "goals": 3, "assists": 2, "xg": 2.8, "passes": 1800, "tackles": 45, "matches": 30},
                    {"name": "Kylian Mbappé", "position": "FW", "team": "PSG", "age": 24, "goals": 28, "assists": 8, "xg": 24.1, "passes": 380, "tackles": 8, "matches": 26},
                    {"name": "Jude Bellingham", "position": "MF", "team": "Real Madrid", "age": 20, "goals": 15, "assists": 7, "xg": 12.8, "passes": 890, "tackles": 42, "matches": 27},
                    {"name": "Mohamed Salah", "position": "FW", "team": "Liverpool", "age": 30, "goals": 25, "assists": 10, "xg": 22.1, "passes": 560, "tackles": 18, "matches": 29},
                    {"name": "Lionel Messi", "position": "FW", "team": "Inter Miami", "age": 36, "goals": 22, "assists": 14, "xg": 19.5, "passes": 980, "tackles": 14, "matches": 22},
                    {"name": "Cristiano Ronaldo", "position": "FW", "team": "Al Nassr", "age": 38, "goals": 30, "assists": 6, "xg": 27.8, "passes": 350, "tackles": 6, "matches": 30},
                ]
                query_lower = query.lower().strip()
                results = mock_db
                if query_lower:
                    results = [p for p in mock_db if query_lower in (p["name"] or "").lower() or query_lower in (p["position"] or "").lower()]
                if position:
                    pos_upper = position.upper()
                    results = [p for p in results if pos_upper in (p["position"] or "").upper()]
                player_list = [{"track_id": i + 1, **p} for i, p in enumerate(results)]
                return json.dumps({"results": player_list, "total": len(player_list)})
        except Exception as e:
            logger.error(f"scout_search_players failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Sprint 1 — Injury Risk Dashboard
    # ================================================================

    async def get_injury_risk(self, match_id, track_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            track_id = SecurityValidator.validate_match_id(track_id)
            events = await self.storage_service.get_match_events(match_id)
            players = await self.storage_service.get_match_players(match_id)

            player_info = None
            for p in (players or []):
                if p.get("track_id") == track_id or p.get("id") == track_id:
                    player_info = p
                    break

            player_events = [e for e in events if e.get("from_track_id") == track_id or e.get("player_track_id") == track_id]
            recent_sprints = sum(1 for e in player_events if e.get("event_type") in ("sprint", "run") and e.get("completed", True))
            recent_distance = sum(abs(e.get("end_x", 0) - e.get("start_x", 0)) + abs(e.get("end_y", 0) - e.get("start_y", 0)) for e in player_events if "start_x" in e) / 100.0
            position = (player_info or {}).get("position", "MID")
            fatigue_index = min(len(player_events) / 50.0, 1.0)

            acwr_data = [100 + (i % 20 - 10) for i in range(28)]
            for ev in player_events:
                intensity = ev.get("intensity", 0.5) if isinstance(ev.get("intensity"), (int, float)) else 0.5
                acwr_data.append(50 + intensity * 100)

            from kawkab.core.injury_risk import InjuryRiskPredictor
            predictor = InjuryRiskPredictor()
            acwr_result = predictor.compute_acwr_overload(acwr_data)
            acwr = acwr_result.get("acwr", 1.0)

            profile = {
                "acwr": acwr,
                "recent_sprint_count": recent_sprints,
                "recent_distance_km": recent_distance,
                "fatigue_index": fatigue_index * 30,
                "position": position,
                "days_since_last_rest": getattr(player_info, "days_since_rest", 3) if hasattr(player_info, "days_since_rest") else 3,
            }
            risk = predictor.predict_injury_risk(profile)
            recovery = predictor.compute_recovery_recommendation(risk["risk_score"], position)

            return json.dumps({
                "risk_score": risk["risk_score"],
                "acwr": acwr,
                "risk_level": risk["risk_category"],
                "recovery_recommendation": recovery,
                "factors": risk["key_risk_factors"],
                "player_name": (player_info or {}).get("name", f"Player #{track_id}"),
                "position": position,
            })
        except Exception as e:
            logger.error(f"get_injury_risk failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_squad_injury_report(self, match_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)
            players = await self.storage_service.get_match_players(match_id)

            home_players = []
            away_players = []
            all_risks = []

            from kawkab.core.injury_risk import InjuryRiskPredictor
            predictor = InjuryRiskPredictor()

            for p in (players or []):
                tid = p.get("track_id", p.get("id", 0))
                team = p.get("team", "home")
                name = p.get("name", f"Player #{tid}")

                p_events = [e for e in events if e.get("from_track_id") == tid or e.get("player_track_id") == tid]
                sprints = sum(1 for e in p_events if e.get("event_type") in ("sprint", "run") and e.get("completed", True))
                dist = sum(abs(e.get("end_x", 0) - e.get("start_x", 0)) + abs(e.get("end_y", 0) - e.get("start_y", 0)) for e in p_events if "start_x" in e) / 100.0
                pos = p.get("position", "MID")
                fatigue = min(len(p_events) / 50.0, 1.0)

                acwr_data = [100 + (i % 20 - 10) for i in range(28)]
                for ev in p_events:
                    intensity = ev.get("intensity", 0.5) if isinstance(ev.get("intensity"), (int, float)) else 0.5
                    acwr_data.append(50 + intensity * 100)

                acwr_result = predictor.compute_acwr_overload(acwr_data)
                acwr = acwr_result.get("acwr", 1.0)

                profile = {
                    "acwr": acwr,
                    "recent_sprint_count": sprints,
                    "recent_distance_km": dist,
                    "fatigue_index": fatigue * 30,
                    "position": pos,
                    "days_since_last_rest": getattr(p, "days_since_rest", 3) if hasattr(p, "days_since_rest") else 3,
                }
                risk = predictor.predict_injury_risk(profile)
                recovery = predictor.compute_recovery_recommendation(risk["risk_score"], pos)
                all_risks.append(risk["risk_score"])

                entry = {
                    "track_id": tid,
                    "name": name,
                    "position": pos,
                    "jersey": p.get("jersey_number", ""),
                    "risk_score": risk["risk_score"],
                    "acwr": acwr,
                    "risk_level": risk["risk_category"],
                    "recovery_recommendation": recovery,
                    "factors": risk["key_risk_factors"],
                }
                if team == "home":
                    home_players.append(entry)
                else:
                    away_players.append(entry)

            high_risk_count = sum(1 for r in all_risks if r >= 0.4)
            avg_home = round(sum(r["risk_score"] for r in home_players) / max(len(home_players), 1), 3)
            avg_away = round(sum(r["risk_score"] for r in away_players) / max(len(away_players), 1), 3)

            return json.dumps({
                "home_players": home_players,
                "away_players": away_players,
                "avg_risk_home": avg_home,
                "avg_risk_away": avg_away,
                "high_risk_count": high_risk_count,
                "total_players": len(home_players) + len(away_players),
            })
        except Exception as e:
            logger.error(f"get_squad_injury_report failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Sprint 1 — Training Plan Auto-Generate
    # ================================================================

    async def generate_training_plan(self, match_id):
        self._check_rate_limit()
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)
            players = await self.storage_service.get_match_players(match_id)

            from kawkab.services.knowledge_service import KnowledgeService
            from kawkab.services.training_plan_service import TrainingPlanGenerator
            from kawkab.services.reasoning_service import Diagnosis, DiagnosisReport

            event_types = {}
            for ev in events or []:
                et = ev.get("event_type", "unknown")
                event_types[et] = event_types.get(et, 0) + 1

            diagnoses = []
            if event_types.get("pass", 0) < 10:
                diagnoses.append(Diagnosis(
                    rule_id="R001", rule_name="Low Passing Volume", rule_name_ar="حجم تمرير منخفض",
                    category="technical", severity="medium", confidence=0.75,
                    evidence={"pass_count": event_types.get("pass", 0)},
                    explanation="Low passing volume indicates poor build-up play",
                    explanation_ar="يشير حجم التمرير المنخفض إلى ضعف في بناء الهجمات",
                    recommended_drills=["D001", "D002", "D003"],
                ))
            if event_types.get("shot", 0) < 5:
                diagnoses.append(Diagnosis(
                    rule_id="R002", rule_name="Low Shot Creation", rule_name_ar="خلق فرص تسديد منخفض",
                    category="attacking", severity="medium", confidence=0.7,
                    evidence={"shot_count": event_types.get("shot", 0)},
                    explanation="Few shots indicate lack of attacking penetration",
                    explanation_ar="قلة التسديدات تشير إلى ضعف الاختراق الهجومي",
                    recommended_drills=["D004", "D005"],
                ))
            if event_types.get("tackle", 0) < 8:
                diagnoses.append(Diagnosis(
                    rule_id="R003", rule_name="Low Defensive Engagement", rule_name_ar="مشاركة دفاعية منخفضة",
                    category="defensive", severity="high", confidence=0.65,
                    evidence={"tackle_count": event_types.get("tackle", 0)},
                    explanation="Low tackle count indicates passive defending",
                    explanation_ar="يشير انخفاض عدد التدخلات إلى دفاع سلبي",
                    recommended_drills=["D006", "D007"],
                ))
            if event_types.get("pressing", 0) or event_types.get("pressure", 0) or 0 < 3:
                diagnoses.append(Diagnosis(
                    rule_id="R004", rule_name="Low Pressing Intensity", rule_name_ar="شدة ضغط منخفضة",
                    category="defensive", severity="medium", confidence=0.6,
                    evidence={"pressure_count": event_types.get("pressing", 0) or event_types.get("pressure", 0) or 0},
                    explanation="Low pressing allows opponent easy build-up",
                    explanation_ar="الضغط المنخفض يسمح للخصم ببناء الهجمات بسهولة",
                    recommended_drills=["D008", "D009"],
                ))
            if not diagnoses:
                diagnoses.append(Diagnosis(
                    rule_id="R005", rule_name="General Match Fitness", rule_name_ar="لياقة المباراة العامة",
                    category="fitness", severity="low", confidence=0.5,
                    evidence={"event_count": len(events or [])},
                    explanation="Maintain current fitness levels",
                    explanation_ar="الحفاظ على مستويات اللياقة الحالية",
                    recommended_drills=["D001", "D004", "D006"],
                ))

            from kawkab.core.logging import get_logger as _get_logger
            report = DiagnosisReport(
                match_id=match_id,
                diagnoses=diagnoses,
                overall_assessment="Auto-generated training plan from match analysis",
                overall_assessment_ar="خطة تدريب مولدة تلقائياً من تحليل المباراة",
                priority_actions=[d.rule_name for d in diagnoses[:3]],
                priority_actions_ar=[d.rule_name_ar for d in diagnoses[:3]],
                confidence=0.7,
            )

            kb = KnowledgeService()
            await kb.initialize()
            gen = TrainingPlanGenerator(kb)
            plan = await gen.generate_plan(report)

            plan_dict = gen.export_to_dict(plan)

            match_data = await self.storage_service.get_match(match_id)
            home_team = (match_data or {}).get("home_team", "Home")
            away_team = (match_data or {}).get("away_team", "Away")

            return json.dumps({
                "success": True,
                "plan": plan_dict,
                "match_info": {
                    "match_id": match_id,
                    "home_team": home_team,
                    "away_team": away_team,
                },
                "analysis_summary": {
                    "total_events": len(events or []),
                    "event_breakdown": event_types,
                    "total_players": len(players or []),
                    "diagnoses_found": len(diagnoses),
                },
            })
        except Exception as e:
            logger.error(f"generate_training_plan failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_shortlist(self):
        self._check_rate_limit()
        try:
            if self._services.get("shortlist_service"):
                sl = self._services["shortlist_service"]
                players = sl.get_shortlist()
                return json.dumps({"players": players, "total": len(players)})
            return json.dumps({"players": [], "total": 0})
        except Exception as e:
            logger.error(f"get_shortlist failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def generate_scout_report_pdf(self, track_id, match_id=0):
        self._check_rate_limit()
        try:
            from kawkab.core.scout_reports import generate_scout_report
            report = generate_scout_report(track_id, match_id)
            return json.dumps({"report": report.to_dict() if hasattr(report, "to_dict") else str(report)})
        except Exception as e:
            logger.error(f"generate_scout_report failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_event_timestamp(self, match_id, event_id):
        self._check_rate_limit()
        try:
            events = await self.storage_service.get_match_events(match_id)
            for ev in events:
                eid = ev.get("id") or ev.get("event_id") or 0
                if eid == event_id:
                    return json.dumps({"timestamp": ev.get("timestamp", 0.0), "time": ev.get("timestamp", 0.0)})
            return json.dumps({"timestamp": 0.0, "time": 0.0})
        except Exception as e:
            logger.error(f"get_event_timestamp failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Roboflow Sports
    # ================================================================

    async def check_roboflow_sports_status(self):
        if self.roboflow_sports_service is None:
            return json.dumps({"available": False})
        return json.dumps({
            "available": self.roboflow_sports_service.available,
            "has_team_classifier": self.roboflow_sports_service.has_team_classifier,
            "has_view_transformer": self.roboflow_sports_service.has_view_transformer,
        })

    # ================================================================
    # Sprint 4 — Live Tagging Service
    # ================================================================

    async def live_start_session(self, home_team="Home", away_team="Away"):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                from kawkab.services.live_tagging_service import LiveTaggingService
                svc = LiveTaggingService()
                self._services["live_tagging_service"] = svc
            return svc.start_session(home_team, away_team)
        except Exception as e:
            logger.error(f"live_start_session failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def live_stop_session(self):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                return json.dumps({"error": "No live tagging service"})
            return svc.stop_session()
        except Exception as e:
            logger.error(f"live_stop_session failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def live_tag_event(self, event_type, team="", player_id=0, notes="", x=None, y=None):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                return json.dumps({"error": "No live tagging service"})
            return svc.tag_event(event_type, team, player_id, notes, x, y)
        except Exception as e:
            logger.error(f"live_tag_event failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def live_set_period(self, period):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                return json.dumps({"error": "No live tagging service"})
            return svc.set_period(period)
        except Exception as e:
            logger.error(f"live_set_period failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def live_get_stats(self):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                return json.dumps({"stats": {"tags_count": 0}})
            return svc.get_stats()
        except Exception as e:
            logger.error(f"live_get_stats failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def live_get_tags(self):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                return json.dumps({"tags": [], "total": 0})
            return svc.get_all_tags()
        except Exception as e:
            logger.error(f"live_get_tags failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def live_clear_tags(self):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                return json.dumps({"error": "No live tagging service"})
            return svc.clear_tags()
        except Exception as e:
            logger.error(f"live_clear_tags failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def live_get_hotkeys(self):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                return json.dumps({"hotkeys": {}})
            return svc.get_hotkeys()
        except Exception as e:
            logger.error(f"live_get_hotkeys failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def live_export(self):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                return json.dumps({"error": "No live tagging service"})
            return svc.export_tags()
        except Exception as e:
            logger.error(f"live_export failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Phase 6 Sprint 2 — Live Tagging Dashboard
    # ================================================================

    async def get_live_kpis(self, session_id):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                return json.dumps({"error": "No live tagging service"})
            raw = json.loads(svc.get_stats())
            if "error" in raw:
                return json.dumps(raw)
            s = raw.get("stats", {})
            ev = s.get("events_by_type", {})
            home_shots = ev.get("shot", 0)
            away_shots = ev.get("shot", 0)
            home_goals = s.get("home_goals", 0)
            away_goals = s.get("away_goals", 0)
            total_shots = home_shots + away_shots
            home_shots_on = ev.get("shot_ontarget", 0) or ev.get("shot_on_target", 0) or 0
            away_shots_on = ev.get("shot_ontarget", 0) or ev.get("shot_on_target", 0) or 0
            xg_approx = round(total_shots * 0.11, 2)
            xg_diff = round(xg_approx - (home_goals + away_goals) * 0.5, 2)
            period = svc._current_period if hasattr(svc, "_current_period") else 1
            return json.dumps({
                "possession_pct": s.get("home_possession_pct", 50.0),
                "shots": total_shots,
                "shots_ontarget": home_shots_on + away_shots_on,
                "goals": home_goals + away_goals,
                "xg": xg_approx,
                "xg_diff": xg_diff,
                "period": period,
                "team_stats": {
                    "home": {"goals": home_goals, "shots": home_shots, "shots_ontarget": home_shots_on},
                    "away": {"goals": away_goals, "shots": away_shots, "shots_ontarget": away_shots_on},
                },
            })
        except Exception as e:
            logger.error(f"get_live_kpis failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_live_pitch_map(self, session_id):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                return json.dumps({"error": "No live tagging service"})
            raw = json.loads(svc.get_all_tags())
            if "error" in raw:
                return json.dumps(raw)
            tags = raw.get("tags", [])
            home_events = []
            away_events = []
            for t in tags:
                entry = {"type": t.get("type"), "x": t.get("x"), "y": t.get("y"), "t": t.get("t")}
                if t.get("team") == svc._home_team:
                    home_events.append(entry)
                elif t.get("team") == svc._away_team:
                    away_events.append(entry)
                elif t.get("type") in ("goal", "shot", "pass", "tackle"):
                    away_events.append(entry)
            home_hot = _compute_hot_zones([e for e in home_events if e["x"] is not None])
            away_hot = _compute_hot_zones([e for e in away_events if e["x"] is not None])
            return json.dumps({
                "home_events": home_events,
                "away_events": away_events,
                "home_hot_zones": home_hot,
                "away_hot_zones": away_hot,
            })
        except Exception as e:
            logger.error(f"get_live_pitch_map failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_live_xg_chart(self, session_id):
        try:
            svc = self._services.get("live_tagging_service")
            if svc is None:
                return json.dumps({"error": "No live tagging service"})
            raw = json.loads(svc.get_all_tags())
            if "error" in raw:
                return json.dumps(raw)
            tags = raw.get("tags", [])
            shot_tags = [t for t in tags if t.get("type") == "shot" or t.get("type") == "goal"]
            timeline = []
            home_cum = 0.0
            away_cum = 0.0
            for t in shot_tags:
                minute = int(t.get("t", 0)) // 60
                xg_val = 0.11
                team = t.get("team", "")
                if team == svc._home_team if hasattr(svc, "_home_team") else "":
                    home_cum += xg_val
                else:
                    away_cum += xg_val
                timeline.append({"minute": minute, "home_xg": round(home_cum, 2), "away_xg": round(away_cum, 2)})
            return json.dumps({
                "timeline": timeline,
                "cumulative_home": round(home_cum, 2),
                "cumulative_away": round(away_cum, 2),
            })
        except Exception as e:
            logger.error(f"get_live_xg_chart failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Sprint 6 — Auto-Updater
    # ================================================================

    async def updater_check(self):
        try:
            svc = self._services.get("auto_updater_service")
            if svc is None:
                from kawkab.services.auto_updater_service import AutoUpdaterService
                svc = AutoUpdaterService()
                self._services["auto_updater_service"] = svc
            return svc.check_for_update()
        except Exception as e:
            logger.error(f"updater_check failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def updater_download(self, url):
        try:
            svc = self._services.get("auto_updater_service")
            if svc is None:
                return json.dumps({"error": "No updater service"})
            return svc.download_update(url)
        except Exception as e:
            logger.error(f"updater_download failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def updater_apply(self, path):
        try:
            svc = self._services.get("auto_updater_service")
            if svc is None:
                return json.dumps({"error": "No updater service"})
            return svc.apply_update(path)
        except Exception as e:
            logger.error(f"updater_apply failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def updater_version(self):
        try:
            svc = self._services.get("auto_updater_service")
            if svc is None:
                return json.dumps({"version": "0.13.0"})
            return svc.get_current_version()
        except Exception as e:
            logger.error(f"updater_version failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Sprint 7 — Sample Data & Utility
    # ================================================================

    async def load_sample_data(self):
        try:
            from kawkab.services.sample_data_generator import generate_sample_match
            data = generate_sample_match()
            match_data = data["match"]
            return json.dumps({
                "ok": True,
                "match": f"{match_data['home_team']} {match_data['home_score']}-{match_data['away_score']} {match_data['away_team']}",
                "events_count": data["total_events"],
            })
        except Exception as e:
            logger.error(f"load_sample_data failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_app_info(self):
        return json.dumps({
            "version": "0.13.0",
            "name": "Kawkab AI",
            "platform": __import__("platform").platform(),
            "python": __import__("sys").version,
            "description": "Private offline AI football coach",
        })

    # ================================================================
    # Sprint 3 — Collaboration Service
    # ================================================================

    async def create_collab_user(self, username, display_name, role="analyst"):
        try:
            svc = self._services.get("collaboration_service")
            if svc is None:
                from kawkab.services.collaboration_service import CollaborationService
                svc = CollaborationService()
                self._services["collaboration_service"] = svc
            return svc.create_user(username, display_name, role)
        except Exception as e:
            logger.error(f"create_collab_user failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_collab_users(self):
        try:
            svc = self._services.get("collaboration_service")
            if svc is None:
                return json.dumps({"users": [], "total": 0})
            return svc.get_users()
        except Exception as e:
            logger.error(f"get_collab_users failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def delete_collab_user(self, user_id):
        try:
            svc = self._services.get("collaboration_service")
            if svc is None:
                return json.dumps({"error": "Service not initialized"})
            return svc.delete_user(user_id)
        except Exception as e:
            logger.error(f"delete_collab_user failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def add_comment(self, match_id, event_id, user_id, text):
        try:
            svc = self._services.get("collaboration_service")
            if svc is None:
                from kawkab.services.collaboration_service import CollaborationService
                svc = CollaborationService()
                self._services["collaboration_service"] = svc
            return svc.add_comment(match_id, event_id, user_id, text)
        except Exception as e:
            logger.error(f"add_comment failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_comments(self, match_id, event_id=0):
        try:
            svc = self._services.get("collaboration_service")
            if svc is None:
                return json.dumps({"comments": [], "total": 0})
            return svc.get_comments(match_id, event_id)
        except Exception as e:
            logger.error(f"get_comments failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def delete_comment(self, comment_id):
        try:
            svc = self._services.get("collaboration_service")
            if svc is None:
                return json.dumps({"error": "Service not initialized"})
            return svc.delete_comment(comment_id)
        except Exception as e:
            logger.error(f"delete_comment failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def export_project(self, match_id):
        try:
            storage = self.storage_service
            if storage is None:
                return json.dumps({"error": "Storage not available"})
            match = await storage.get_match(match_id)
            if not match:
                return json.dumps({"error": "Match not found"})
            events = await storage.get_match_events(match_id)
            match["events"] = events
            svc = self._services.get("collaboration_service")
            if svc is None:
                from kawkab.services.collaboration_service import CollaborationService
                svc = CollaborationService()
                self._services["collaboration_service"] = svc
            return svc.export_project(match)
        except Exception as e:
            logger.error(f"export_project failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def import_project(self, project_json):
        try:
            svc = self._services.get("collaboration_service")
            if svc is None:
                from kawkab.services.collaboration_service import CollaborationService
                svc = CollaborationService()
                self._services["collaboration_service"] = svc
            return svc.import_project(project_json)
        except Exception as e:
            logger.error(f"import_project failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_activity_feed(self, limit=50):
        try:
            svc = self._services.get("collaboration_service")
            if svc is None:
                return json.dumps({"activities": [], "total": 0})
            return svc.get_activity_feed(limit)
        except Exception as e:
            logger.error(f"get_activity_feed failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_event_comments(self, match_id, event_id):
        try:
            svc = self._services.get("collaboration_service")
            if svc is None:
                return json.dumps({"comments": [], "total": 0})
            return svc.get_event_comments(match_id, event_id)
        except Exception as e:
            logger.error(f"get_event_comments failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_mentions(self, username):
        try:
            svc = self._services.get("collaboration_service")
            if svc is None:
                return json.dumps({"mentions": [], "total": 0, "unread": 0})
            return svc.get_mentions(username)
        except Exception as e:
            logger.error(f"get_mentions failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def mark_mention_read(self, mention_id):
        try:
            svc = self._services.get("collaboration_service")
            if svc is None:
                return json.dumps({"error": "Service not initialized"})
            return svc.mark_mention_read(mention_id)
        except Exception as e:
            logger.error(f"mark_mention_read failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Sprint 2 — Wearable Import + Physiological Merge + Correlation
    # ================================================================

    async def import_wearable(self, file_path):
        try:
            from kawkab.services.wearable_import_service import WearableImportService
            svc = WearableImportService()
            return svc.import_auto(file_path)
        except Exception as e:
            logger.error(f"import_wearable failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def merge_player_physiology(self, player_id, trajectory_json, wearable_json, body_mass_kg=75.0):
        try:
            from kawkab.services.physiological_merge_service import PhysiologicalMergeService
            from kawkab.services.wearable_import_service import WearableDataPoint
            traj = json.loads(trajectory_json) if isinstance(trajectory_json, str) else trajectory_json
            w_data = json.loads(wearable_json) if isinstance(wearable_json, str) else wearable_json
            trajectory = [(t["t"], t.get("x", t.get("v", 0)), t.get("y", 0)) for t in traj]
            wearables = []
            for w in w_data:
                dp = WearableDataPoint(
                    timestamp_s=w.get("t", 0),
                    heart_rate_bpm=w.get("hr"),
                    speed_ms=w.get("spd", w.get("speed")),
                    distance_m=w.get("dist"),
                    acceleration_ms2=w.get("acc"),
                )
                wearables.append(dp)
            svc = PhysiologicalMergeService()
            return svc.merge(player_id, trajectory, wearables, body_mass_kg)
        except Exception as e:
            logger.error(f"merge_player_physiology failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def analyze_physio_tactical(self, events_json, speed_timeline_json, hr_timeline_json=None, window_s=5.0):
        try:
            from kawkab.services.physio_tactical_correlation import PhysioTacticalCorrelationService
            events = json.loads(events_json) if isinstance(events_json, str) else events_json
            speed_tl = json.loads(speed_timeline_json) if isinstance(speed_timeline_json, str) else speed_timeline_json
            hr_tl = None
            if hr_timeline_json:
                hr_tl = json.loads(hr_timeline_json) if isinstance(hr_timeline_json, str) else hr_timeline_json
            svc = PhysioTacticalCorrelationService()
            return svc.analyze(events, speed_tl, hr_tl, window_s)
        except Exception as e:
            logger.error(f"analyze_physio_tactical failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def rf_draw_pitch(self, scale):
        import base64
        if self.roboflow_sports_service is None or not self.roboflow_sports_service.available:
            return json.dumps({"error": "roboflow/sports not installed"})
        try:
            import cv2
            img = self.roboflow_sports_service.draw_pitch(scale=scale)
            if img is None:
                return json.dumps({"error": "draw_pitch returned None"})
            _, buf = cv2.imencode(".png", img)
            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
            return json.dumps({"success": True, "image_b64": b64, "shape": list(img.shape)})
        except Exception as e:
            logger.error(f"rf_draw_pitch failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Phase 10 — Telestration v2
    # ================================================================

    async def tel_layer_add(self, layer_id, name=""):
        try:
            svc = self._get_telestration()
            return svc.add_layer(layer_id, name)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def tel_layer_remove(self, layer_id):
        try:
            svc = self._get_telestration()
            return svc.remove_layer(layer_id)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def tel_layer_toggle(self, layer_id):
        try:
            svc = self._get_telestration()
            return svc.toggle_layer_visibility(layer_id)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def tel_layer_opacity(self, layer_id, opacity):
        try:
            svc = self._get_telestration()
            return svc.set_layer_opacity(layer_id, opacity)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def tel_get_layers(self):
        try:
            svc = self._get_telestration()
            return svc.get_layers()
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def tel_save_preset(self, name, layers_json):
        try:
            svc = self._get_telestration()
            return svc.save_preset(name, layers_json)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def tel_load_preset(self, name):
        try:
            svc = self._get_telestration()
            return svc.load_preset(name)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def tel_list_presets(self):
        try:
            svc = self._get_telestration()
            return svc.list_presets()
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def tel_delete_preset(self, name):
        try:
            svc = self._get_telestration()
            return svc.delete_preset(name)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def tel_export_video(self, video_path, layers_json, output_path=""):
        try:
            svc = self._get_telestration()
            return svc.export_annotated_video(video_path, layers_json, output_path)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _get_telestration(self):
        svc = self._services.get("telestration_service")
        if svc is None:
            from kawkab.services.telestration_service import TelestrationService
            svc = TelestrationService()
            self._services["telestration_service"] = svc
        return svc

    # ================================================================
    # Phase 9 — Live Stream Capture
    # ================================================================

    async def stream_start_capture(self, url, stream_id="", output_filename=""):
        try:
            svc = self._services.get("live_stream_service")
            if svc is None:
                from kawkab.services.live_stream_service import LiveStreamCaptureService
                svc = LiveStreamCaptureService()
                self._services["live_stream_service"] = svc
            return svc.start_capture(url, stream_id, output_filename)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def stream_stop_capture(self, stream_id):
        try:
            svc = self._services.get("live_stream_service")
            if svc is None:
                return json.dumps({"error": "No stream service"})
            return svc.stop_capture(stream_id)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def stream_get_status(self, stream_id):
        try:
            svc = self._services.get("live_stream_service")
            if svc is None:
                return json.dumps({"error": "No stream service"})
            return svc.get_stream_status(stream_id)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def stream_list(self):
        try:
            svc = self._services.get("live_stream_service")
            if svc is None:
                return json.dumps({"streams": []})
            return svc.list_streams()
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def stream_add_marker(self, stream_id, label=""):
        try:
            svc = self._services.get("live_stream_service")
            if svc is None:
                return json.dumps({"error": "No stream service"})
            return svc.add_chapter_marker(stream_id, label)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def stream_list_recordings(self):
        try:
            svc = self._services.get("live_stream_service")
            if svc is None:
                return json.dumps({"recordings": []})
            return svc.list_recordings()
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def stream_detect_source(self, url):
        try:
            from kawkab.services.live_stream_service import LiveStreamCaptureService
            svc = LiveStreamCaptureService()
            return json.dumps({"source_type": svc.detect_source_type(url)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ================================================================
    # Phase 8 — Cloud Sync
    # ================================================================

    async def cloud_check_health(self):
        try:
            svc = self._get_cloud_sync()
            return svc.check_health()
        except Exception as e:
            return json.dumps({"error": str(e), "status": "offline"})

    async def cloud_register(self, username, email, password, display_name=""):
        try:
            svc = self._get_cloud_sync()
            return svc.register(username, email, password, display_name)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_login(self, email, password):
        try:
            svc = self._get_cloud_sync()
            return svc.login(email, password)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_logout(self):
        try:
            svc = self._get_cloud_sync()
            return svc.logout()
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_get_me(self):
        try:
            svc = self._get_cloud_sync()
            return svc.get_me()
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_is_logged_in(self):
        try:
            svc = self._get_cloud_sync()
            return svc.is_logged_in()
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_create_team(self, name, description=""):
        try:
            svc = self._get_cloud_sync()
            return svc.create_team(name, description)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_list_teams(self):
        try:
            svc = self._get_cloud_sync()
            return svc.list_teams()
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_invite_member(self, team_id, email):
        try:
            svc = self._get_cloud_sync()
            return svc.invite_member(team_id, email)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_accept_invite(self, token):
        try:
            svc = self._get_cloud_sync()
            return svc.accept_invite(token)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_sync_push(self, device_id, operations_json):
        try:
            svc = self._get_cloud_sync()
            ops = json.loads(operations_json)
            return svc.sync_push(device_id, ops)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_sync_pull(self, device_id):
        try:
            svc = self._get_cloud_sync()
            return svc.sync_pull(device_id)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_oauth_authorize_url(self, provider, redirect_uri=""):
        try:
            svc = self._get_cloud_sync()
            return svc.oauth_authorize_url(provider, redirect_uri)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_oauth_exchange(self, provider, code, state):
        try:
            svc = self._get_cloud_sync()
            return svc.oauth_exchange(provider, code, state)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_oauth_providers(self):
        try:
            svc = self._get_cloud_sync()
            return svc.oauth_providers()
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_start_server(self, port=8741):
        try:
            import threading
            from kawkab.cloud.server import start
            t = threading.Thread(target=start, args=("0.0.0.0", port), daemon=True)
            t.start()
            return json.dumps({"ok": True, "port": port, "message": f"Cloud server started on port {port}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def cloud_server_status(self):
        try:
            import httpx
            resp = httpx.get(f"http://localhost:8741/health", timeout=3.0)
            return json.dumps({"running": resp.status_code == 200, "details": resp.json()})
        except Exception:
            return json.dumps({"running": False})

    def _get_cloud_sync(self):
        svc = self._services.get("cloud_sync_service")
        if svc is None:
            from kawkab.services.cloud_sync_service import CloudSyncService
            svc = CloudSyncService()
            self._services["cloud_sync_service"] = svc
        return svc

    # ================================================================
    # Phase 12 — AI Coach Assistant v2
    # ================================================================

    def _get_ai_v2(self):
        svc = self._services.get("ai_assistant_v2_service")
        if svc is None:
            from kawkab.services.ai_assistant_v2_service import AIAssistantV2Service
            svc = AIAssistantV2Service(llm_service=self._services.get("llm_service"))
            self._services["ai_assistant_v2_service"] = svc
        return svc

    async def ai_v2_create_conv(self, match_id, title):
        try:
            svc = self._get_ai_v2()
            conv = svc.create_conversation(
                match_id=int(match_id) if match_id else None,
                title=str(title or "New Chat"),
            )
            return json.dumps({"success": True, "conv_id": conv.id, "title": conv.title})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Phase 13 — Opponent Database + Scouting Network + Transfermarkt
    # ================================================================

    def _get_opponent_db(self):
        svc = self._services.get("opponent_database_service")
        if svc is None:
            from kawkab.services.opponent_database_service import OpponentDatabaseService
            svc = OpponentDatabaseService()
            self._services["opponent_database_service"] = svc
        return svc

    def _get_scouting_network(self):
        svc = self._services.get("scouting_network_service")
        if svc is None:
            from kawkab.services.scouting_network_service import ScoutingNetworkService
            svc = ScoutingNetworkService()
            self._services["scouting_network_service"] = svc
        return svc

    def _get_transfermarkt(self):
        svc = self._services.get("transfermarkt_integration_service")
        if svc is None:
            from kawkab.services.transfermarkt_integration_service import TransfermarktIntegrationService
            svc = TransfermarktIntegrationService()
            self._services["transfermarkt_integration_service"] = svc
        return svc

    async def opponent_list(self):
        try:
            svc = self._get_opponent_db()
            return json.dumps({"success": True, "profiles": svc.list_profiles()})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def opponent_get(self, profile_id):
        try:
            svc = self._get_opponent_db()
            profile = svc.get_profile(str(profile_id))
            if profile:
                matchups = svc.get_matchups(str(profile_id))
                return json.dumps({"success": True, "profile": profile, "matchups": matchups})
            return json.dumps({"success": False, "error": "Not found"})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def opponent_create(self, team_name, league, country):
        try:
            svc = self._get_opponent_db()
            result = svc.create_profile(str(team_name), str(league or ""), str(country or ""))
            return json.dumps({"success": True, "profile": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def opponent_update(self, profile_id, updates_json):
        try:
            svc = self._get_opponent_db()
            updates = json.loads(updates_json)
            ok = svc.update_profile(str(profile_id), updates)
            return json.dumps({"success": ok})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def opponent_delete(self, profile_id):
        try:
            svc = self._get_opponent_db()
            ok = svc.delete_profile(str(profile_id))
            return json.dumps({"success": ok})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def opponent_add_matchup(self, profile_id, our_team, date, competition, home_away, our_score, their_score, our_xg, their_xg, notes):
        try:
            svc = self._get_opponent_db()
            result = svc.add_matchup(
                opponent_id=str(profile_id), our_team=str(our_team), date=str(date),
                competition=str(competition or ""), home_away=str(home_away or "home"),
                our_score=int(our_score or 0), their_score=int(their_score or 0),
                our_xg=float(our_xg or 0.0), their_xg=float(their_xg or 0.0),
                notes=str(notes or ""),
            )
            return json.dumps({"success": True, "matchup": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def opponent_scouting_report(self, profile_id):
        try:
            svc = self._get_opponent_db()
            report = svc.generate_scouting_report(str(profile_id))
            return json.dumps({"success": True, "report": report})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def scout_network_search(self, query, position, min_age, max_age, league, min_rating):
        try:
            svc = self._get_scouting_network()
            results = svc.search_players(
                query=str(query or ""), position=str(position or ""),
                min_age=int(min_age or 0), max_age=int(max_age or 99),
                league=str(league or ""), min_rating=float(min_rating or 0.0),
            )
            return json.dumps({"success": True, "players": results})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def scout_network_add(self, name, position, club, league, rating, strengths_json, weaknesses_json, scout_notes, submitted_by, tags_json):
        try:
            svc = self._get_scouting_network()
            strengths = json.loads(strengths_json) if strengths_json else []
            weaknesses = json.loads(weaknesses_json) if weaknesses_json else []
            tags = json.loads(tags_json) if tags_json else []
            result = svc.add_player(
                name=str(name), position=str(position or ""), club=str(club or ""),
                league=str(league or ""), rating=float(rating or 0.0),
                strengths=strengths, weaknesses=weaknesses,
                scout_notes=str(scout_notes or ""), submitted_by=str(submitted_by or ""),
                tags=tags,
            )
            return json.dumps({"success": True, "player": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def scout_network_get(self, player_id):
        try:
            svc = self._get_scouting_network()
            player = svc.get_player(str(player_id))
            if player:
                return json.dumps({"success": True, "player": player})
            return json.dumps({"success": False, "error": "Not found"})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def scout_network_delete(self, player_id):
        try:
            svc = self._get_scouting_network()
            ok = svc.delete_player(str(player_id))
            return json.dumps({"success": ok})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def scout_network_stats(self):
        try:
            svc = self._get_scouting_network()
            stats = svc.get_stats()
            return json.dumps({"success": True, "stats": stats})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def transfermarkt_search(self, name):
        try:
            svc = self._get_transfermarkt()
            results = svc.search_player(str(name))
            return json.dumps({"success": True, "results": results})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def transfermarkt_get(self, player_id):
        try:
            svc = self._get_transfermarkt()
            details = svc.get_player_details(int(player_id))
            return json.dumps({"success": True, "details": details})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def transfermarkt_squad(self, club_name):
        try:
            svc = self._get_transfermarkt()
            squad = svc.get_club_squad(str(club_name))
            return json.dumps({"success": True, "squad": squad})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})
        try:
            svc = self._get_ai_v2()
            convs = svc.list_conversations(
                match_id=int(match_id) if match_id else None
            )
            return json.dumps({"success": True, "conversations": convs})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def ai_v2_delete_conv(self, conv_id):
        try:
            svc = self._get_ai_v2()
            ok = svc.delete_conversation(str(conv_id))
            return json.dumps({"success": ok})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def ai_v2_ask(self, conv_id, question, match_context, language):
        try:
            svc = self._get_ai_v2()
            answer = await svc.ask(
                conv_id=str(conv_id),
                question=str(question),
                match_context=str(match_context or ""),
                language=str(language or "en"),
            )
            return json.dumps({"success": True, "answer": answer})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def ai_v2_tactical_suggestion(self, topic, match_context, language):
        try:
            svc = self._get_ai_v2()
            answer = await svc.get_tactical_suggestion(
                topic=str(topic),
                match_context=str(match_context or ""),
                language=str(language or "en"),
            )
            return json.dumps({"success": True, "answer": answer})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def ai_v2_auto_report(self, match_id, language):
        try:
            svc = self._get_ai_v2()
            mid = int(match_id)
            events = await self.storage_service.get_match_events(mid)
            match_data = await self.storage_service.get_match(mid) or {}
            match_data["event_count"] = len(events)

            event_summary = {}
            for ev in events:
                et = ev.get("event_type", "unknown")
                event_summary[et] = event_summary.get(et, 0) + 1
            match_data["event_breakdown"] = event_summary

            report = await svc.generate_automated_report(
                match_id=mid,
                match_data=match_data,
                language=str(language or "en"),
            )
            return json.dumps({"success": True, "report": report})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Phase 15 — Community Marketplace
    # ================================================================

    def _get_marketplace(self):
        svc = self._services.get("marketplace_service")
        if svc is None:
            from kawkab.services.marketplace_service import MarketplaceService
            svc = MarketplaceService()
            self._services["marketplace_service"] = svc
        return svc

    async def marketplace_list(self, item_type, category, query, source):
        try:
            svc = self._get_marketplace()
            items = svc.list_items(
                item_type=str(item_type or ""),
                category=str(category or ""),
                query=str(query or ""),
                source=str(source or ""),
            )
            return json.dumps({"success": True, "items": items})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def marketplace_get(self, item_id):
        try:
            svc = self._get_marketplace()
            item = svc.get_item(str(item_id))
            if item:
                return json.dumps({"success": True, "item": item})
            return json.dumps({"success": False, "error": "Not found"})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def marketplace_add(self, item_type, name, description, author, category, tags_json, data, source):
        try:
            svc = self._get_marketplace()
            tags = json.loads(tags_json) if tags_json else []
            result = svc.add_item(
                item_type=str(item_type),
                name=str(name),
                description=str(description or ""),
                author=str(author or ""),
                category=str(category or ""),
                tags=tags,
                data=str(data or ""),
                source=str(source or "local"),
            )
            return json.dumps({"success": True, "item": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def marketplace_rate(self, item_id, rating):
        try:
            svc = self._get_marketplace()
            ok = svc.rate_item(str(item_id), float(rating))
            return json.dumps({"success": ok})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def marketplace_delete(self, item_id):
        try:
            svc = self._get_marketplace()
            ok = svc.delete_item(str(item_id))
            return json.dumps({"success": ok})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def marketplace_stats(self):
        try:
            svc = self._get_marketplace()
            stats = svc.get_stats()
            return json.dumps({"success": True, "stats": stats})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def marketplace_categories(self, item_type):
        try:
            svc = self._get_marketplace()
            cats = svc.get_categories(str(item_type or ""))
            return json.dumps({"success": True, "categories": cats})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ── P0-B2: YOLO variant control ────────────────────────────────

    async def get_recommended_yolo_variant(self):
        """Return the recommended YOLO variant for the current GPU tier."""
        try:
            from kawkab.core.gpu_acceleration import detect_gpu_tier, recommend_yolo_variant
            tier = detect_gpu_tier()
            variant = recommend_yolo_variant(tier)
            return json.dumps({"success": True, "tier": tier, "recommended": variant})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_current_yolo_variant(self):
        """Return the current YOLO variant in use."""
        try:
            cv = self._services.get("cv_service")
            variant = cv.model_size if cv and hasattr(cv, "model_size") else "l"
            return json.dumps({"success": True, "variant": variant})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def set_yolo_variant(self, variant: str):
        """Set the YOLO variant for the next analysis."""
        try:
            valid = {"n", "s", "m", "l", "x"}
            if variant not in valid:
                return json.dumps({"success": False, "error": f"Invalid variant '{variant}'. Must be one of {valid}"})
            cv = self._services.get("cv_service")
            if cv and hasattr(cv, "model_size"):
                cv.model_size = variant
                logger.info(f"YOLO variant set to yolo11{variant}")
                return json.dumps({"success": True, "variant": variant})
            return json.dumps({"success": False, "error": "CV service not available"})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    async def get_gpu_tier(self):
        """Return detected GPU tier and VRAM info."""
        try:
            from kawkab.core.gpu_acceleration import detect_gpu, detect_gpu_tier
            backend = detect_gpu()
            tier = detect_gpu_tier()
            info = {"backend": backend, "tier": tier}
            if backend == "cuda":
                try:
                    import subprocess
                    result = subprocess.run(
                        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                        capture_output=True, text=True, timeout=5,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        parts = result.stdout.strip().split(", ")
                        info["gpu_name"] = parts[0] if len(parts) > 0 else "unknown"
                        info["vram_mb"] = parts[1] if len(parts) > 1 else "unknown"
                        info["driver"] = parts[2] if len(parts) > 2 else "unknown"
                except Exception:
                    pass
            return json.dumps({"success": True, "info": info})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ── Sprint 2 — Advanced Visualizations ───────────────────────

    def get_pitch_control_overlay(self, match_id: str) -> str:
        """Compute pitch control grid overlay for a match.

        Returns JSON with home_grid, away_grid, ball_control_pct, hot_zones.
        """
        try:
            from kawkab.core.pitch_control import VoronoiPitchControl
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            if not events:
                return json.dumps({"home_grid": [], "away_grid": [], "ball_control_pct": 50.0, "hot_zones": []})

            home_events = [e for e in events if e.get("team") == "home" and e.get("start_x") is not None]
            away_events = [e for e in events if e.get("team") == "away" and e.get("start_x") is not None]
            home_positions = [(e.get("start_x", 52.5), e.get("start_y", 34.0)) for e in home_events[:11]]
            away_positions = [(e.get("start_x", 52.5), e.get("start_y", 34.0)) for e in away_events[:11]]

            pc = VoronoiPitchControl()
            frame = pc.compute_frame_control(home_positions, away_positions)

            hot_zones = []
            import numpy as np
            hg = np.array(frame.home_grid)
            ag = np.array(frame.away_grid)
            total = hg.size
            home_cells = int(np.sum(hg > 0.5))
            away_cells = int(np.sum(ag > 0.5))
            ball_control_pct = round((home_cells / max(total, 1)) * 100.0, 1)

            return json.dumps({
                "home_grid": frame.home_grid,
                "away_grid": frame.away_grid,
                "ball_control_pct": ball_control_pct,
                "hot_zones": hot_zones,
            })
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def get_player_pass_sonar(self, match_id: str, track_id: str) -> str:
        """Compute pass direction sonar for a single player.

        Returns JSON with directions (8 compass points), pass_counts, accuracy_pct.
        """
        try:
            from kawkab.core.pass_sonars import compute_pass_sonars
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            sonars = compute_pass_sonars(events, sectors=8)
            target = [s for s in sonars if s.get("track_id") == str(track_id)]
            if not target:
                return json.dumps({"directions": [], "pass_counts": [], "accuracy_pct": [], "total_passes": 0, "error": f"Player {track_id} not found"})
            player = target[0]
            directions = []
            pass_counts = []
            accuracy_pct = []
            for sec in player["sectors"]:
                directions.append(sec["angle_center"])
                pass_counts.append(sec["count"])
                accuracy_pct.append(round(sec["accuracy"] * 100.0, 1))
            return json.dumps({
                "directions": directions,
                "pass_counts": pass_counts,
                "accuracy_pct": accuracy_pct,
                "total_passes": player["total_passes"],
            })
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def get_space_control_heatmap(self, match_id: str) -> str:
        """Compute Voronoi-based space control heatmap for a match.

        Returns JSON with grid, team_control_pcts, hot_zones, space_gained.
        """
        try:
            from kawkab.core.space_control import compute_pitch_control_grid, identify_hot_zones
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            if not events:
                return json.dumps({"grid": [], "team_control_pcts": {}, "hot_zones": [], "space_gained": 0.0})

            all_positions = []
            team_ids = []
            for e in events:
                if e.get("start_x") is not None and e.get("team") in ("home", "away"):
                    tid = 0 if e.get("team") == "home" else 1
                    all_positions.append((e.get("start_x"), e.get("start_y"), e.get("id", 0)))
                    team_ids.append(tid)

            if not all_positions:
                return json.dumps({"grid": [], "team_control_pcts": {}, "hot_zones": [], "space_gained": 0.0})

            grid, team_pcts = compute_pitch_control_grid(all_positions[:22], team_ids[:22])
            hot_zones = identify_hot_zones(grid, 0)

            space_gained_count = 0
            for e in events:
                if e.get("type") == "pass" and e.get("start_x") is not None and e.get("end_x") is not None:
                    space_gained_count += 1
            space_gained = round(space_gained_count * 1.5, 1)

            grid_list = grid.tolist() if hasattr(grid, 'tolist') else grid
            return json.dumps({
                "grid": grid_list,
                "team_control_pcts": team_pcts,
                "hot_zones": hot_zones,
                "space_gained": space_gained,
            })
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def get_player_role(self, match_id: str, track_id: str) -> str:
        """Classify a player's role from their event data.

        Returns JSON with primary_role, confidence, secondary_role, role_breakdown.
        """
        try:
            from kawkab.core.role_classifier import classify_player_role
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            player_events = [e for e in events if str(e.get("track_id")) == str(track_id) or str(e.get("player_id")) == str(track_id)]
            if not player_events:
                return json.dumps({"primary_role": "unknown", "confidence": 0.0, "secondary_role": "", "role_breakdown": {}})

            role = classify_player_role(player_events)
            return json.dumps({
                "primary_role": role.primary_role,
                "confidence": role.confidence,
                "secondary_role": role.secondary_role,
                "role_breakdown": role.role_scores,
            })
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def get_dominance_index(self, match_id: str) -> str:
        """Compute composite dominance index (0-100) for a match.

        Returns JSON with index, sub_scores, per_phase.
        """
        try:
            from kawkab.core.dominance_index import compute_dominance_index
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            if not events:
                return json.dumps({"index": 50.0, "sub_scores": {}, "phases": {}, "team": "home", "opponent": "away"})

            report = compute_dominance_index(events, "home")
            return json.dumps({
                "index": report.index,
                "team": report.team,
                "opponent": report.opponent,
                "sub_scores": report.sub_scores,
                "phases": report.phases,
            })
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ── Advanced analysis modules (Sprint 12+) ────────────────────

    def compute_goals_added(self, match_id: int) -> str:
        try:
            from kawkab.core.goals_added import compute_g_plus
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            result = compute_g_plus(events)
            return json.dumps({"success": True, "result": result, "count": len(result)})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def analyze_finishing(self, match_id: int) -> str:
        try:
            from kawkab.core.finishing_analysis import analyze_finishing
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            result = analyze_finishing(events)
            return json.dumps({"success": True, "result": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def simulate_league(self, match_id: int, iterations: int = 10000) -> str:
        try:
            from kawkab.core.league_simulation import simulate_league
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            result = simulate_league(events, iterations=iterations)
            return json.dumps({"success": True, "result": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def estimate_transfer_fee(self, match_id: int, track_id: int) -> str:
        try:
            from kawkab.core.squad_valuation import estimate_player_transfer_fee
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            result = estimate_player_transfer_fee(events, track_id)
            return json.dumps({"success": True, "result": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def generate_match_report(self, match_id: int) -> str:
        try:
            from kawkab.core.match_report import generate_match_report as _gmr
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            result = _gmr(events)
            return json.dumps({"success": True, "result": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def generate_game_plan(self, match_id: int, opponent_id: int) -> str:
        try:
            from kawkab.core.game_plan import generate_game_plan as _ggp
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            result = _ggp(events, opponent_id)
            return json.dumps({"success": True, "result": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def compute_phase_xg(self, match_id: int) -> str:
        try:
            from kawkab.core.phase_xg import compute_phase_xg as _cpx
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            result = _cpx(events)
            return json.dumps({"success": True, "result": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def analyze_build_up(self, match_id: int) -> str:
        try:
            from kawkab.core.build_up import analyze_build_up as _abu
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            result = _abu(events)
            return json.dumps({"success": True, "result": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def compute_territory_value(self, match_id: int) -> str:
        try:
            from kawkab.core.territory_value import compute_territory_value as _ctv
            events = self.storage_service.get_match_events(match_id) if self.storage_service else []
            result = _ctv(events)
            return json.dumps({"success": True, "result": result})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Sprint 5 — Data Quality Score
    # ================================================================

    def get_match_quality_score(self, match_id: str) -> str:
        """Compute data quality score for a match using anomaly detection.

        Returns JSON with: score, anomaly_count, anomalies list, warnings.
        """
        try:
            mid = SecurityValidator.validate_match_id(match_id)
            events = self.storage_service.get_match_events(mid) if self.storage_service else []

            from kawkab.core.match_anomaly_detection import detect_anomalies, compute_data_quality_score

            report = detect_anomalies(events)
            quality_score = compute_data_quality_score(events)

            result = {
                "score": round(quality_score, 1),
                "anomaly_count": len(report.anomalies),
                "anomalies": report.anomalies,
                "warnings": [],
            }

            if quality_score >= 80:
                result["level"] = "good"
            elif quality_score >= 50:
                result["level"] = "fair"
            else:
                result["level"] = "poor"

            return json.dumps(result)
        except Exception as e:
            logger.error(f"get_match_quality_score failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e), "score": 0.0, "level": "error"})
