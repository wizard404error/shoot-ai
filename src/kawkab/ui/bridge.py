"""QWebChannel bridge - exposes Python services to JavaScript frontend.

The frontend calls these methods directly via QWebChannel.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from kawkab.core.logging import get_logger
from kawkab.core.paths import get_paths
from kawkab.core.security import SecurityValidator, ErrorSanitizer

logger = get_logger(__name__)


class Bridge(QObject):
    """Bridge between Python services and JavaScript frontend.

    Exposed methods are called from JS via QWebChannel.
    Signals are emitted from Python and received by JS.
    """

    analysisProgress = Signal(float, str)
    analysisComplete = Signal(dict)
    analysisError = Signal(str)
    matchSaved = Signal(int)
    calibrationSaved = Signal(int, dict)

    def __init__(
        self,
        cv_service,
        enhancement_service,
        analysis_service,
        llm_service,
        knowledge_service,
        storage_service,
        audio_service,
        homography_service=None,
        lightglue_homography_service=None,
        player_profile_service=None,
        multi_match_service=None,
        data_export_service=None,
        visualization_service=None,
        anomaly_detection_service=None,
        quality_scoring_service=None,
        advanced_event_detection_service=None,
        physical_load_service=None,
        pressure_metrics_service=None,
        benchmark_service=None,
        feedback_service=None,
        clip_service=None,
        face_recognition_service=None,
        football_data_service=None,
        bzzoiro_service=None,
        easy_soccer_service=None,
        api_football_service=None,
        thesportsdb_service=None,
        statsbomb_service=None,
        openfootball_service=None,
        roboflow_sports_service=None,
        pose_analysis_service=None,
        mujoco_ball_service=None,
        fluidx3d_service=None,
        weather_service=None,
        psychology_service=None,
        football_rules_service=None,
        card_detection_service=None,
        setpiece_service=None,
        goalkeeper_service=None,
        substitution_service=None,
        possession_service=None,
        frame_skip=3,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.cv_service = cv_service
        self.enhancement_service = enhancement_service
        self.analysis_service = analysis_service
        self.llm_service = llm_service
        self.knowledge_service = knowledge_service
        self.storage_service = storage_service
        self.audio_service = audio_service
        self.homography_service = homography_service
        self.lightglue_homography_service = lightglue_homography_service
        self.player_profile_service = player_profile_service
        self.multi_match_service = multi_match_service
        self.data_export_service = data_export_service
        self.visualization_service = visualization_service
        self.anomaly_detection_service = anomaly_detection_service
        self.quality_scoring_service = quality_scoring_service
        self.advanced_event_detection_service = advanced_event_detection_service
        self.physical_load_service = physical_load_service
        self.pressure_metrics_service = pressure_metrics_service
        self.benchmark_service = benchmark_service
        self.feedback_service = feedback_service
        self.clip_service = clip_service
        self.face_recognition_service = face_recognition_service
        self.football_data_service = football_data_service
        self.bzzoiro_service = bzzoiro_service
        self.easy_soccer_service = easy_soccer_service
        self.api_football_service = api_football_service
        self.thesportsdb_service = thesportsdb_service
        self.statsbomb_service = statsbomb_service
        self.openfootball_service = openfootball_service
        self.roboflow_sports_service = roboflow_sports_service
        self.pose_analysis_service = pose_analysis_service
        self.mujoco_ball_service = mujoco_ball_service
        self.fluidx3d_service = fluidx3d_service
        self.weather_service = weather_service
        self.psychology_service = psychology_service
        self.football_rules_service = football_rules_service
        self.card_detection_service = card_detection_service
        self.setpiece_service = setpiece_service
        self.goalkeeper_service = goalkeeper_service
        self.substitution_service = substitution_service
        self.possession_service = possession_service
        self.frame_skip = frame_skip
        self._overlay_cache: dict[int, list[dict]] = {}
        self._tracking_cache: dict[int, Any] = {}

        logger.info("Bridge initialized")

    @Slot(int, result=str)
    async def get_first_frame(self, match_id: int) -> str:
        """Return path to a frame image for calibration UI."""
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            match = await self.storage_service.get_match(match_id)
            if not match or not match.get("video_path"):
                return json.dumps({"error": "No video found"})
            return json.dumps({
                "path": match["video_path"],
                "match_id": match_id,
            })
        except Exception as e:
            logger.error(f"get_first_frame failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, str, float, float, result=str)
    async def save_homography(
        self,
        match_id: int,
        corners_json: str,
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
    ) -> str:
        """Save homography calibration for a match."""
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            if self.homography_service is None:
                return json.dumps({
                    "success": False,
                    "error": "HomographyService not initialized",
                })

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

            self.homography_service.save_calibration(match_id, matrix)

            self.calibrationSaved.emit(match_id, {
                "confidence": matrix.confidence,
                "error_px": matrix.error_px,
            })

            return json.dumps({
                "success": True,
                "confidence": matrix.confidence,
                "error_px": matrix.error_px,
            })
        except Exception as e:
            logger.error(f"save_homography failed: {e}")
            return json.dumps({"success": False, "error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def get_homography(self, match_id: int) -> str:
        """Get saved homography for a match."""
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

    @Slot(str, str, result=int)
    async def save_match(self, name: str, video_path: str) -> int:
        """Save a new match to the database.

        Args:
            name: Match name (e.g., "Team A vs Team B")
            video_path: Absolute path to the video file

        Returns:
            Match ID
        """
        try:
            name = SecurityValidator.validate_team_name(name)
            video_path = str(SecurityValidator.validate_video_path(video_path))
            match_id = await self.storage_service.save_match(
                name=name, video_path=video_path
            )
            self.matchSaved.emit(match_id)
            return match_id
        except Exception as e:
            logger.error(f"Failed to save match: {e}")
            return 0

    @Slot(int, str, result=str)
    async def analyze_match(self, match_id: int, video_path: str) -> str:
        """Run full analysis pipeline on a match video.

        Args:
            match_id: Database ID of the match
            video_path: Path to the video file

        Returns:
            JSON string with analysis results
        """
        import json

        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            video_path_obj = SecurityValidator.validate_video_path(video_path)
            if not video_path_obj.exists():
                raise FileNotFoundError(f"Video not found: {video_path}")

            self.analysisProgress.emit(0.0, "Starting analysis...")
            if self.benchmark_service is not None:
                self.benchmark_service.reset()

            self.analysisProgress.emit(0.05, "Enhancing video...")
            if self.benchmark_service is not None:
                self.benchmark_service.start_stage("enhancement")
            preprocessed_path = (
                get_paths().cache
                / f"{video_path_obj.stem}_preprocessed.mp4"
            )
            await self.enhancement_service.preprocess_video(
                video_path_obj, preprocessed_path
            )
            if self.benchmark_service is not None:
                self.benchmark_service.end_stage("enhancement")

            self.analysisProgress.emit(0.15, "Detecting players and ball...")
            if self.benchmark_service is not None:
                self.benchmark_service.start_stage("detection")
                self.benchmark_service.start_stage("tracking")

            async def progress_cb(progress: float, msg: str) -> None:
                total = 0.15 + progress * 0.55
                self.analysisProgress.emit(total, msg)

            track_data = await self.cv_service.process_video(
                preprocessed_path,
                progress_callback=progress_cb,
                frame_skip=self.frame_skip,
                enable_team_detection=True,
            )
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

            # Load homography if available for meter-based analysis
            homography_matrix = None
            if self.homography_service is not None:
                homography_matrix = self.homography_service.load_calibration(match_id)

            self.analysisProgress.emit(0.75, "Computing statistics...")
            if self.benchmark_service is not None:
                self.benchmark_service.start_stage("analysis")
            analysis = await self.analysis_service.analyze_match(
                track_data, match_id=match_id, homography_matrix=homography_matrix
            )
            if self.benchmark_service is not None:
                self.benchmark_service.end_stage("analysis")

            self.analysisProgress.emit(0.85, "Saving results...")
            if self.benchmark_service is not None:
                self.benchmark_service.start_stage("save")
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
                await self.storage_service.save_event(
                    match_id=match_id, event=event
                )
            if self.benchmark_service is not None:
                self.benchmark_service.end_stage("save")

            # --- Advanced Metrics (v0.6.2) ---
            self.analysisProgress.emit(0.88, "Computing advanced metrics...")
            if self.benchmark_service is not None:
                self.benchmark_service.start_stage("advanced_metrics")

            advanced_events: list[dict] = []
            physical_loads: dict = {}
            pressure_metrics: dict = {}

            try:
                if self.advanced_event_detection_service is not None:
                    advanced_events = await self.advanced_event_detection_service.detect_all_advanced_events(
                        track_data, analysis.events, homography_matrix
                    )
                    for event in advanced_events:
                        await self.storage_service.save_event(
                            match_id=match_id, event=event
                        )
            except Exception as e:
                logger.warning(f"Advanced event detection failed: {e}")

            try:
                if self.physical_load_service is not None:
                    physical_loads = await self.physical_load_service.compute_physical_load(
                        track_data, homography_matrix
                    )
                    for track_id, metrics in physical_loads.items():
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id,
                            metric_name="sprint_count",
                            metric_value=metrics.sprint_count,
                            metric_category="physical",
                            player_id=None,
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id,
                            metric_name="sprint_distance_m",
                            metric_value=metrics.sprint_distance_m,
                            metric_category="physical",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id,
                            metric_name="hi_distance_m",
                            metric_value=metrics.high_intensity_distance_m,
                            metric_category="physical",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id,
                            metric_name="acceleration_count",
                            metric_value=metrics.acceleration_count,
                            metric_category="physical",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id,
                            metric_name="deceleration_count",
                            metric_value=metrics.deceleration_count,
                            metric_category="physical",
                        )
            except Exception as e:
                logger.warning(f"Physical load computation failed: {e}")

            try:
                if self.pressure_metrics_service is not None:
                    all_events = analysis.events + advanced_events
                    pressure_metrics = await self.pressure_metrics_service.compute_pressure_metrics(
                        track_data, all_events, homography_matrix
                    )
                    for team, metrics in pressure_metrics.items():
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id,
                            metric_name="ppda",
                            metric_value=metrics.ppda_overall,
                            metric_category="pressure",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id,
                            metric_name="passes_under_pressure_pct",
                            metric_value=metrics.passes_under_pressure_pct,
                            metric_category="pressure",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id,
                            metric_name="pressure_events",
                            metric_value=metrics.pressure_events,
                            metric_category="pressure",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id,
                            metric_name="counter_press_success_rate",
                            metric_value=metrics.counter_press_success_rate,
                            metric_category="pressure",
                        )
                        await self.storage_service.save_advanced_metrics(
                            match_id=match_id,
                            metric_name="defensive_line_height_m",
                            metric_value=metrics.defensive_line_height_m,
                            metric_category="pressure",
                        )
            except Exception as e:
                logger.warning(f"Pressure metrics computation failed: {e}")

            if self.benchmark_service is not None:
                self.benchmark_service.end_stage("advanced_metrics")

            self.analysisProgress.emit(1.0, "Analysis complete!")

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

            # --- Save benchmark ---
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

            self.analysisComplete.emit(result)
            return json.dumps(result)
        except Exception as e:
            logger.exception(f"Analysis failed: {e}")
            self.analysisError.emit(ErrorSanitizer.sanitize_error(e))
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def _compute_overlay_data(self, track_data) -> list[dict]:
        data = []
        w = track_data.frames[0].image_width if track_data.frames else 1
        h = track_data.frames[0].image_height if track_data.frames else 1
        for frame in track_data.frames:
            if frame.image_width:
                w, h = frame.image_width, frame.image_height
            entry = {
                "f": frame.frame_number,
                "t": frame.timestamp,
                "p": [],
                "b": None,
            }
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

    @Slot(int, float, result=str)
    def get_overlay_data(self, match_id: int, timestamp: float) -> str:
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

    @Slot(int, str, str, result=str)
    async def generate_report(
        self, match_id: int, language: str, summary: str
    ) -> str:
        """Generate a coach-friendly report.

        Args:
            match_id: Database ID of the match
            language: "en" or "ar"
            summary: Summary of match analysis

        Returns:
            Generated report text
        """
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            language = SecurityValidator.sanitize_string(language, max_length=10)
            if language not in ("en", "ar"):
                language = "en"
            report = await self.llm_service.generate_coach_report(
                match_analysis_summary=summary, language=language
            )
            await self.storage_service.save_report(
                match_id=match_id,
                language=language,
                report_text=report,
                llm_provider=self.llm_service.config.provider,
            )
            return report
        except Exception as e:
            logger.exception(f"Report generation failed: {e}")
            return f"Error generating report: {ErrorSanitizer.sanitize_error(e)}"

    @Slot(result=str)
    async def get_all_matches(self) -> str:
        """Get all saved matches.

        Returns:
            JSON string with list of matches
        """
        import json

        try:
            matches = await self.storage_service.get_all_matches()
            return json.dumps(matches)
        except Exception as e:
            logger.error(f"Failed to get matches: {e}")
            return json.dumps([])

    @Slot(int, result=str)
    async def get_match_events(self, match_id: int) -> str:
        """Get events for a match.

        Args:
            match_id: Database ID of the match

        Returns:
            JSON string with list of events
        """
        import json

        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            events = await self.storage_service.get_match_events(match_id)
            return json.dumps(events)
        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def get_video_path(self, match_id: int) -> str:
        """Get the video file path for a match.

        Args:
            match_id: Database ID of the match

        Returns:
            JSON with path or error
        """
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            match = await self.storage_service.get_match(match_id)
            if not match or not match.get("video_path"):
                return json.dumps({"error": "No video found"})
            return json.dumps({"path": match["video_path"]})
        except Exception as e:
            logger.error(f"get_video_path failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(result=str)
    async def get_knowledge_base_stats(self) -> str:
        """Get knowledge base statistics.

        Returns:
            JSON string with KB stats
        """
        import json

        await self.knowledge_service.initialize()
        return json.dumps(self.knowledge_service.stats)

    @Slot(result=str)
    async def check_llm_availability(self) -> str:
        """Check which LLM providers are available.

        Returns:
            JSON string with provider status
        """
        import json

        try:
            ollama_available = False
            for provider in self.llm_service.providers:
                if hasattr(provider, "is_available"):
                    if await provider.is_available():
                        ollama_available = True
                        break

            return json.dumps(
                {
                    "ollama": ollama_available,
                    "provider": self.llm_service.config.provider,
                    "model": (
                        self.llm_service.config.ollama_model
                        if self.llm_service.config.provider == "ollama"
                        else "external"
                    ),
                }
            )
        except Exception as e:
            logger.error(f"LLM check failed: {e}")
            return json.dumps({"ollama": False, "error": str(e)})

    # --- Professional Analytics Methods (v0.6.0+) ---

    @Slot(str, result=str)
    async def export_match_csv(self, match_id_str: str) -> str:
        """Export match data as CSV."""
        import json
        try:
            match_id = SecurityValidator.validate_match_id(match_id_str)
            if self.data_export_service is None:
                return json.dumps({"error": "DataExportService not available"})
            path = await self.data_export_service.export_match_csv(match_id)
            return json.dumps({"success": True, "path": str(path)})
        except Exception as e:
            logger.error(f"Export CSV failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def export_match_json(self, match_id_str: str) -> str:
        """Export match data as JSON."""
        import json
        try:
            match_id = SecurityValidator.validate_match_id(match_id_str)
            if self.data_export_service is None:
                return json.dumps({"error": "DataExportService not available"})
            path = await self.data_export_service.export_match_json(match_id)
            return json.dumps({"success": True, "path": str(path)})
        except Exception as e:
            logger.error(f"Export JSON failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, str, int, str, result=str)
    async def create_player_profile(self, name: str, jersey: str, number: int, position: str) -> str:
        """Create a new player profile."""
        import json
        try:
            name = SecurityValidator.sanitize_string(name, max_length=100)
            number = SecurityValidator.validate_jersey_number(number)
            position = SecurityValidator.sanitize_string(position, max_length=50)
            if self.player_profile_service is None:
                return json.dumps({"error": "PlayerProfileService not available"})
            profile = await self.player_profile_service.create_profile(
                display_name=name,
                jersey_number=number,
                preferred_position=position,
            )
            return json.dumps({"success": True, "profile_id": profile.id, "global_id": profile.global_id})
        except Exception as e:
            logger.error(f"Create profile failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(result=str)
    async def get_all_player_profiles(self) -> str:
        """Get all player profiles."""
        import json
        try:
            if self.player_profile_service is None:
                return json.dumps({"profiles": []})
            profiles = await self.player_profile_service.get_all_profiles()
            return json.dumps({"profiles": [
                {"id": p.id, "name": p.display_name, "jersey": p.jersey_number, "position": p.preferred_position}
                for p in profiles
            ]})
        except Exception as e:
            logger.error(f"Get profiles failed: {e}")
            return json.dumps({"profiles": []})

    @Slot(str, str, str, result=str)
    async def compare_matches(self, match_id_1: str, match_id_2: str, focus: str) -> str:
        """Compare two matches side-by-side."""
        import json
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

    @Slot(str, result=str)
    async def get_match_quality_report(self, match_id_str: str) -> str:
        """Get quality report for a match."""
        import json
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

    @Slot(result=str)
    def get_gpu_info(self) -> str:
        """Get GPU information and recommended settings.

        Returns:
            JSON with gpu_name, tier, recommendations, and current_settings
        """
        import json
        from kawkab.services.benchmark_service import BenchmarkService

        try:
            model_size = getattr(self.cv_service, 'model_size', 'l') if self.cv_service else 'l'
            if self.benchmark_service is None:
                return json.dumps({
                    "gpu_name": "unknown",
                    "tier": "unknown",
                    "recommendations": BenchmarkService.recommend_settings("unknown"),
                    "current_settings": {
                        "model_size": model_size,
                        "frame_skip": self.frame_skip,
                    },
                })
            info = self.benchmark_service._system_info
            gpu_name = info.get("gpu_name", "unknown")
            tier = BenchmarkService.classify_gpu_tier(gpu_name)
            recommendations = BenchmarkService.recommend_settings(tier)
            return json.dumps({
                "gpu_name": gpu_name,
                "tier": tier,
                "recommendations": recommendations,
                "current_settings": {
                    "model_size": model_size,
                    "frame_skip": self.frame_skip,
                },
            })
        except Exception as e:
            logger.error(f"get_gpu_info failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def submit_feedback(self, feedback_json: str) -> str:
        """Submit coach feedback.

        Args:
            feedback_json: JSON string with CoachFeedback fields

        Returns:
            JSON with feedback_id or error
        """
        import json
        from kawkab.services.feedback_service import CoachFeedback

        if self.feedback_service is None:
            return json.dumps({"error": "Feedback service not available"})

        try:
            data = json.loads(feedback_json)
            feedback = CoachFeedback(
                coach_id=data.get("coach_id", "anonymous"),
                match_id=data.get("match_id", 0),
                overall_rating=data.get("overall_rating", 3),
                tracking_rating=data.get("tracking_rating"),
                events_rating=data.get("events_rating"),
                report_rating=data.get("report_rating"),
                ui_rating=data.get("ui_rating"),
                comments=data.get("comments", ""),
                issues=data.get("issues"),
            )
            fid = await self.feedback_service.submit_feedback(feedback)
            return json.dumps({"feedback_id": fid, "status": "saved"})
        except Exception as e:
            logger.error(f"submit_feedback failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def submit_issue(self, issue_json: str) -> str:
        """Submit an issue report.

        Args:
            issue_json: JSON string with IssueReport fields

        Returns:
            JSON with issue_id or error
        """
        import json
        from kawkab.services.feedback_service import IssueReport

        if self.feedback_service is None:
            return json.dumps({"error": "Feedback service not available"})

        try:
            data = json.loads(issue_json)
            issue = IssueReport(
                category=data.get("category", "other"),
                severity=data.get("severity", "medium"),
                description=data.get("description", ""),
                match_id=data.get("match_id"),
            )
            iid = await self.feedback_service.submit_issue(issue)
            return json.dumps({"issue_id": iid, "status": "saved"})
        except Exception as e:
            logger.error(f"submit_issue failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(result=str)
    async def get_feedback_stats(self) -> str:
        """Get feedback summary statistics.

        Returns:
            JSON with summary stats
        """
        import json

        if self.feedback_service is None:
            return json.dumps({"error": "Feedback service not available"})

        try:
            stats = await self.feedback_service.get_summary_stats()
            return json.dumps(stats)
        except Exception as e:
            logger.error(f"get_feedback_stats failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # --- v0.8.3: PDF Report Export ---

    @Slot(int, str, result=str)
    async def export_report_pdf(self, match_id: int, language: str) -> str:
        """Export a match report as a standalone HTML file (open in browser → Print to PDF).

        Args:
            match_id: Database ID of the match
            language: "en" or "ar"

        Returns:
            JSON with path to the HTML file or error
        """
        import json
        import html as html_mod
        from datetime import datetime

        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            language = SecurityValidator.sanitize_string(language, max_length=10)
            if language not in ("en", "ar"):
                language = "en"

            match = await self.storage_service.get_match(match_id)
            if not match:
                return json.dumps({"error": "Match not found"})

            events = await self.storage_service.get_match_events(match_id)
            report_text = ""
            try:
                stored_reports = await self.storage_service.get_reports(match_id, language)
                if stored_reports and len(stored_reports) > 0:
                    report_text = stored_reports[0].get("report_text", "")
            except Exception:
                report_text = ""

            shot_events = [e for e in events if e.get("type") == "shot"]
            pass_events = [e for e in events if e.get("type") == "pass"]

            home_shots = sum(1 for e in shot_events if e.get("team") == "home")
            away_shots = sum(1 for e in shot_events if e.get("team") == "away")
            home_passes = sum(1 for e in pass_events if e.get("team") == "home")
            away_passes = sum(1 for e in pass_events if e.get("team") == "away")
            home_on_target = sum(1 for e in shot_events if e.get("team") == "home" and e.get("on_target"))
            away_on_target = sum(1 for e in shot_events if e.get("team") == "away" and e.get("on_target"))

            match_name = html_mod.escape(match.get("name", "Unnamed Match"))
            match_date = match.get("match_date", datetime.now().strftime("%Y-%m-%d"))

            is_rtl = language == "ar"
            doc_dir = "rtl" if is_rtl else "ltr"
            body_dir = "right" if is_rtl else "left"
            title = "تقرير المباراة" if is_rtl else "Match Report"

            html_content = f"""<!DOCTYPE html>
<html lang="{language}" dir="{doc_dir}">
<head><meta charset="UTF-8"><title>{title} - {match_name}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1e293b; background: #fff; padding: 2rem; max-width: 900px; margin: 0 auto; line-height: 1.6; }}
h1 {{ font-size: 1.75rem; color: #2563eb; margin-bottom: 0.25rem; }}
h2 {{ font-size: 1.25rem; color: #334155; margin: 1.5rem 0 0.75rem; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.25rem; }}
h3 {{ font-size: 1rem; color: #475569; margin: 1rem 0 0.5rem; }}
.meta {{ color: #64748b; font-size: 0.875rem; margin-bottom: 1.5rem; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }}
.card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; }}
.card h3 {{ color: #2563eb; margin-top: 0; }}
.stat-row {{ display: flex; justify-content: space-between; padding: 0.35rem 0; border-bottom: 1px solid #f1f5f9; font-size: 0.9rem; }}
.stat-label {{ color: #64748b; }}
.stat-value {{ font-weight: 600; }}
.report {{ white-space: pre-wrap; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; font-size: 0.9rem; line-height: 1.7; }}
.footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; font-size: 0.75rem; color: #94a3b8; text-align: center; }}
</style></head>
<body>
<h1>{title}</h1>
<p class="meta">{html_mod.escape(match_name)} &middot; {match_date}</p>

<div class="grid">
  <div class="card">
    <h3>{"الفريق المضيف" if is_rtl else "Home Team"}</h3>
    <div class="stat-row"><span class="stat-label">{"التسديدات" if is_rtl else "Shots"}</span><span class="stat-value">{home_shots}</span></div>
    <div class="stat-row"><span class="stat-label">{"على المرمى" if is_rtl else "On Target"}</span><span class="stat-value">{home_on_target}</span></div>
    <div class="stat-row"><span class="stat-label">{"التمريرات" if is_rtl else "Passes"}</span><span class="stat-value">{home_passes}</span></div>
  </div>
  <div class="card">
    <h3>{"الفريق الضيف" if is_rtl else "Away Team"}</h3>
    <div class="stat-row"><span class="stat-label">{"التسديدات" if is_rtl else "Shots"}</span><span class="stat-value">{away_shots}</span></div>
    <div class="stat-row"><span class="stat-label">{"على المرمى" if is_rtl else "On Target"}</span><span class="stat-value">{away_on_target}</span></div>
    <div class="stat-row"><span class="stat-label">{"التمريرات" if is_rtl else "Passes"}</span><span class="stat-value">{away_passes}</span></div>
  </div>
</div>

<h2>{"تقرير المدرب" if is_rtl else "Coach Report"}</h2>
<div class="report">{html_mod.escape(report_text) if report_text else ("لم يتم إنشاء تقرير بعد" if is_rtl else "No report generated yet")}</div>

<div class="footer">{"تم الإنشاء بواسطة" if is_rtl else "Generated by"} Kawkab AI &middot; {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
</body></html>"""

            output_dir = get_paths().exports
            output_path = output_dir / f"report_{match_id}_{language}.html"
            output_path.write_text(html_content, encoding="utf-8")
            return json.dumps({"success": True, "path": str(output_path)})
        except Exception as e:
            logger.error(f"export_report_pdf failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # --- v0.8.3: Video Clip Export ---

    @Slot(int, result=str)
    async def extract_event_clips(self, match_id: int) -> str:
        """Extract video clips for all shot events in a match.

        Args:
            match_id: Database ID of the match

        Returns:
            JSON with list of clip paths or error
        """
        import json

        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            if self.clip_service is None:
                return json.dumps({"error": "ClipExtractionService not available"})
            match = await self.storage_service.get_match(match_id)
            if not match or not match.get("video_path"):
                return json.dumps({"error": "No video found for match"})
            events = await self.storage_service.get_match_events(match_id)
            shot_events = [e for e in events if e.get("type") == "shot"]
            if not shot_events:
                return json.dumps({"error": "No shot events to extract"})
            clip_events = [{"timestamp": e["timestamp"], "type": "shot", "team": e.get("team", "unknown")} for e in shot_events]
            clips = await self.clip_service.extract_event_clips(
                video_path=Path(match["video_path"]),
                events=clip_events,
                context_seconds=3.0,
            )
            return json.dumps({"success": True, "clips": clips})
        except Exception as e:
            logger.error(f"extract_event_clips failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # --- v0.8.3: Team Swap Correction ---

    @Slot(int, result=str)
    async def swap_teams(self, match_id: int) -> str:
        """Swap home/away team assignment for a match.

        Args:
            match_id: Database ID of the match

        Returns:
            JSON with success status
        """
        import json

        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            match = await self.storage_service.get_match(match_id)
            if not match:
                return json.dumps({"error": "Match not found"})
            home = match.get("home_team", "Home")
            away = match.get("away_team", "Away")
            await self.storage_service.update_match_teams(
                match_id=match_id, home_team=away, away_team=home
            )
            logger.info(f"Swapped teams for match {match_id}: {home} ↔ {away}")
            return json.dumps({"success": True, "home": away, "away": home})
        except Exception as e:
            logger.error(f"swap_teams failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # --- v0.8.3: Visualization Generation ---

    @Slot(int, result=str)
    async def generate_visualizations(self, match_id: int) -> str:
        """Generate pass network and heatmap visualizations for a match.

        Args:
            match_id: Database ID of the match

        Returns:
            JSON with paths to generated images or error
        """
        import json

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
                    pass_events=pass_events,
                    player_positions=player_positions,
                    output_name=f"pass_network_{match_id}.png",
                )
                positions_list = list(player_positions.values())
                if positions_list:
                    heatmap_path = await self.visualization_service.generate_heatmap(
                        positions=positions_list,
                        output_name=f"heatmap_{match_id}.png",
                    )
            return json.dumps({
                "success": True,
                "pass_network": str(pass_network_path) if pass_network_path else None,
                "heatmap": str(heatmap_path) if heatmap_path else None,
            })
        except Exception as e:
            logger.error(f"generate_visualizations failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, str, result=str)
    async def update_event(self, event_id: int, updates_json: str) -> str:
        try:
            updates = json.loads(updates_json)
            ok = await self.storage_service.update_event(event_id, updates)
            return json.dumps({"success": ok})
        except Exception as e:
            logger.error(f"update_event failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def delete_event(self, event_id: int) -> str:
        try:
            ok = await self.storage_service.delete_event(event_id)
            return json.dumps({"success": ok})
        except Exception as e:
            logger.error(f"delete_event failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(result=str)
    async def get_face_gallery(self) -> str:
        """Get all player profiles with face data."""
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

    @Slot(str, str, int, result=str)
    async def upload_face_photo(
        self, photo_path: str, display_name: str, jersey_number: int
    ) -> str:
        """Upload a player photo, detect face, and store embedding."""
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
                "success": True,
                "profile_id": profile,
                "display_name": display_name,
                "confidence": best["confidence"],
            })
        except Exception as e:
            logger.error(f"upload_face_photo failed: {e}")
            return json.dumps({"success": False, "error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def match_faces_in_match(self, match_id: int) -> str:
        """Run face recognition for all players in a match."""
        try:
            if self.face_recognition_service is None:
                return json.dumps({"success": False, "error": "FaceRecognitionService not available (install insightface)"})

            track_data = self._tracking_cache.get(match_id)
            if not track_data:
                return json.dumps({"success": False, "error": "No tracking data cached. Run analysis first."})

            profiles = await self.storage_service.get_all_player_profiles()
            identified = self.face_recognition_service.identify_players_in_match(
                profiles, track_data
            )

            count = len(identified)
            return json.dumps({"success": True, "identified_count": count})
        except Exception as e:
            logger.error(f"match_faces_in_match failed: {e}")
            return json.dumps({"success": False, "error": ErrorSanitizer.sanitize_error(e)})

    # --- v0.8.4: football-data.org Integration ---

    @Slot(result=str)
    async def check_football_data_status(self) -> str:
        """Check if football-data.org API is available with configured key."""
        if self.football_data_service is None:
            return json.dumps({"available": False, "error": "Service not initialized"})
        try:
            status = await self.football_data_service.check_status()
            return json.dumps(status)
        except Exception as e:
            logger.error(f"check_football_data_status failed: {e}")
            return json.dumps({"available": False, "error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def search_football_team(self, query: str) -> str:
        """Search for teams on football-data.org."""
        if self.football_data_service is None:
            return json.dumps({"teams": []})
        try:
            query = SecurityValidator.sanitize_string(query, max_length=100)
            teams = await self.football_data_service.search_team(query)
            return json.dumps({"teams": teams})
        except Exception as e:
            logger.error(f"search_football_team failed: {e}")
            return json.dumps({"teams": []})

    @Slot(int, str, str, result=str)
    async def import_football_team_squad(self, match_id: int, api_team_id: str, side: str) -> str:
        """Import a team's squad as player profiles for a match.

        Args:
            match_id: Kawkab match ID
            api_team_id: football-data.org team ID
            side: "home" or "away"

        Returns:
            JSON with list of created/updated profiles
        """
        import json

        if self.football_data_service is None or self.player_profile_service is None:
            return json.dumps({"success": False, "error": "Required service not available"})
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            team_id = int(api_team_id)
            side = SecurityValidator.sanitize_string(side, max_length=10)
            if side not in ("home", "away"):
                return json.dumps({"success": False, "error": "side must be 'home' or 'away'"})

            squad = await self.football_data_service.import_team_squad(team_id, side)
            created = []
            skipped = 0

            existing = await self.player_profile_service.get_all_profiles(team=side)
            existing_nums = {p.jersey_number for p in existing if p.jersey_number is not None}

            for player_data in squad:
                if player_data["jersey_number"] in existing_nums:
                    skipped += 1
                    continue
                try:
                    profile = await self.player_profile_service.create_profile(**player_data)
                    created.append({
                        "profile_id": profile.id,
                        "name": player_data["display_name"],
                        "jersey": player_data["jersey_number"],
                        "position": player_data["preferred_position"],
                    })
                except Exception as e:
                    logger.warning(f"Failed to create profile for {player_data['display_name']}: {e}")

            if side == "home":
                await self.storage_service.update_match_football_data(
                    match_id, football_data_home_team_id=team_id
                )
            else:
                await self.storage_service.update_match_football_data(
                    match_id, football_data_away_team_id=team_id
                )

            return json.dumps({
                "success": True,
                "created": created,
                "skipped": skipped,
            })
        except Exception as e:
            logger.error(f"import_football_team_squad failed: {e}")
            return json.dumps({"success": False, "error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, int, int, result=str)
    async def verify_match_with_api(self, match_id: int, api_match_id: int) -> str:
        """Compare detected match score with football-data.org API.

        Args:
            match_id: Kawkab match ID
            api_match_id: football-data.org match ID

        Returns:
            JSON with verification result
        """
        import json

        if self.football_data_service is None:
            return json.dumps({"error": "FootballDataService not available"})
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            match = await self.storage_service.get_match(match_id)
            if not match:
                return json.dumps({"error": "Match not found"})

            events = await self.storage_service.get_match_events(match_id)
            shot_events = [e for e in events if e.get("type") == "goal"]
            detected_home = sum(1 for e in shot_events if e.get("team") == "home")
            detected_away = sum(1 for e in shot_events if e.get("team") == "away")

            result = await self.football_data_service.verify_match(
                api_match_id, detected_home, detected_away
            )
            if result is None:
                return json.dumps({"error": "Could not fetch match data from API"})

            # Store the api_match_id for future reference
            await self.storage_service.update_match_football_data(
                match_id, api_match_id=api_match_id
            )

            return json.dumps({"success": True, **result})
        except Exception as e:
            logger.error(f"verify_match_with_api failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def get_football_standings(self, competition_code: str) -> str:
        """Get standings for a competition.

        Args:
            competition_code: e.g. "PL", "BL1", "SA", "PD", "FL1"

        Returns:
            JSON with standings data or error
        """
        import json

        if self.football_data_service is None:
            return json.dumps({"error": "FootballDataService not available"})
        try:
            code = SecurityValidator.sanitize_string(competition_code, max_length=10)
            standings = await self.football_data_service.get_standings(code)
            if standings is None:
                return json.dumps({"error": "Could not fetch standings"})
            return json.dumps({"success": True, "standings": standings})
        except Exception as e:
            logger.error(f"get_football_standings failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def get_football_competitions(self) -> str:
        """Get list of available competitions from football-data.org."""
        import json

        if self.football_data_service is None:
            return json.dumps({"competitions": []})
        try:
            comps = await self.football_data_service.get_competitions()
            return json.dumps({"competitions": comps})
        except Exception as e:
            logger.error(f"get_football_competitions failed: {e}")
            return json.dumps({"competitions": []})

    @Slot(result=str)
    async def check_bzzoiro_status(self) -> str:
        """Check if Bzzoiro API is available."""
        if self.bzzoiro_service is None:
            return json.dumps({"available": False, "error": "Service not initialized"})
        try:
            status = await self.bzzoiro_service.check_status()
            return json.dumps(status)
        except Exception as e:
            logger.error(f"check_bzzoiro_status failed: {e}")
            return json.dumps({"available": False, "error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def search_bzzoiro_team(self, query: str) -> str:
        """Search teams on Bzzoiro."""
        if self.bzzoiro_service is None:
            return json.dumps({"teams": []})
        try:
            query = SecurityValidator.sanitize_string(query, max_length=100)
            teams = await self.bzzoiro_service.search_team(query)
            return json.dumps({"teams": teams})
        except Exception as e:
            logger.error(f"search_bzzoiro_team failed: {e}")
            return json.dumps({"teams": []})

    @Slot(int, result=str)
    async def get_bzzoiro_team_squad(self, team_id: int) -> str:
        """Get squad from Bzzoiro."""
        if self.bzzoiro_service is None:
            return json.dumps({"players": []})
        try:
            squad = await self.bzzoiro_service.get_team_squad(team_id)
            return json.dumps({"players": squad})
        except Exception as e:
            logger.error(f"get_bzzoiro_team_squad failed: {e}")
            return json.dumps({"players": []})

    @Slot(int, int, str, result=str)
    async def import_bzzoiro_team_squad(self, match_id: int, team_id: int, side: str) -> str:
        """Import Bzzoiro team squad as player profiles."""
        if self.bzzoiro_service is None or self.player_profile_service is None:
            return json.dumps({"success": False, "error": "Required service not available"})
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            side = SecurityValidator.sanitize_string(side, max_length=10)
            if side not in ("home", "away"):
                return json.dumps({"success": False, "error": "side must be 'home' or 'away'"})
            squad = await self.bzzoiro_service.get_team_squad(team_id)
            created = []
            skipped = 0
            existing = await self.player_profile_service.get_all_profiles(team=side)
            existing_nums = {p.jersey_number for p in existing if p.jersey_number is not None}
            for p in squad:
                jersey = p.get("jersey_number")
                if jersey is not None and jersey in existing_nums:
                    skipped += 1
                    continue
                try:
                    profile = await self.player_profile_service.create_profile(
                        display_name=p.get("name"),
                        jersey_number=jersey,
                        preferred_position=p.get("position"),
                        nationality=p.get("nationality"),
                        date_of_birth=p.get("date_of_birth"),
                        team=side,
                        bzzoiro_person_id=p.get("id"),
                        bzzoiro_team_id=team_id,
                    )
                    created.append({
                        "profile_id": profile.id,
                        "name": p.get("name"),
                        "jersey": jersey,
                        "position": p.get("position"),
                    })
                except Exception as e:
                    logger.warning(f"Failed to create profile: {e}")
            if side == "home":
                await self.storage_service.update_match_bzzoiro(match_id, bzzoiro_home_team_id=team_id)
            else:
                await self.storage_service.update_match_bzzoiro(match_id, bzzoiro_away_team_id=team_id)
            return json.dumps({"success": True, "created": created, "skipped": skipped})
        except Exception as e:
            logger.error(f"import_bzzoiro_team_squad failed: {e}")
            return json.dumps({"success": False, "error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, int, result=str)
    async def verify_match_bzzoiro(self, match_id: int, bzzoiro_event_id: int) -> str:
        """Compare detected score vs Bzzoiro API."""
        if self.bzzoiro_service is None:
            return json.dumps({"error": "BzzoiroService not available"})
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            match = await self.storage_service.get_match(match_id)
            if not match:
                return json.dumps({"error": "Match not found"})
            detail = await self.bzzoiro_service.get_match_detail(bzzoiro_event_id)
            if detail is None:
                return json.dumps({"error": "Could not fetch match from Bzzoiro"})
            events = await self.storage_service.get_match_events(match_id)
            shot_events = [e for e in events if e.get("type") == "goal"]
            detected_home = sum(1 for e in shot_events if e.get("team") == "home")
            detected_away = sum(1 for e in shot_events if e.get("team") == "away")
            api_home = detail.get("home_score") or 0
            api_away = detail.get("away_score") or 0
            match_name = detail.get("home_team", "") + " vs " + detail.get("away_team", "")
            match_ok = (detected_home == api_home) and (detected_away == api_away)
            await self.storage_service.update_match_bzzoiro(match_id, bzzoiro_event_id=bzzoiro_event_id)
            return json.dumps({
                "success": True,
                "match": match_name,
                "api_score": f"{api_home}-{api_away}",
                "detected_score": f"{detected_home}-{detected_away}",
                "match_ok": match_ok,
            })
        except Exception as e:
            logger.error(f"verify_match_bzzoiro failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def get_bzzoiro_standings(self, league_id: int) -> str:
        """Get league standings from Bzzoiro."""
        if self.bzzoiro_service is None:
            return json.dumps({"standings": []})
        try:
            standings = await self.bzzoiro_service.get_standings(league_id)
            return json.dumps({"standings": standings})
        except Exception as e:
            logger.error(f"get_bzzoiro_standings failed: {e}")
            return json.dumps({"standings": []})

    @Slot(str, result=str)
    async def get_bzzoiro_leagues(self) -> str:
        """Get available leagues from Bzzoiro."""
        if self.bzzoiro_service is None:
            return json.dumps({"leagues": []})
        try:
            leagues = await self.bzzoiro_service.get_leagues()
            return json.dumps({"leagues": leagues})
        except Exception as e:
            logger.error(f"get_bzzoiro_leagues failed: {e}")
            return json.dumps({"leagues": []})

    @Slot(int, str, str, result=str)
    async def get_bzzoiro_team_matches(self, team_id: int, date_from: str, date_to: str) -> str:
        """Get team fixtures from Bzzoiro."""
        if self.bzzoiro_service is None:
            return json.dumps({"matches": []})
        try:
            matches = await self.bzzoiro_service.get_team_matches(
                team_id, date_from=date_from or None, date_to=date_to or None
            )
            return json.dumps({"matches": matches})
        except Exception as e:
            logger.error(f"get_bzzoiro_team_matches failed: {e}")
            return json.dumps({"matches": []})

    @Slot(result=str)
    async def get_bzzoiro_live(self) -> str:
        """Get live matches from Bzzoiro."""
        if self.bzzoiro_service is None:
            return json.dumps({"matches": []})
        try:
            matches = await self.bzzoiro_service.get_live_events()
            return json.dumps({"matches": matches})
        except Exception as e:
            logger.error(f"get_bzzoiro_live failed: {e}")
            return json.dumps({"matches": []})

    @Slot(int, result=str)
    async def get_bzzoiro_predictions(self, event_id: int) -> str:
        """Get AI predictions from Bzzoiro."""
        if self.bzzoiro_service is None:
            return json.dumps({"error": "BzzoiroService not available"})
        try:
            preds = await self.bzzoiro_service.get_predictions(event_id)
            if preds is None:
                return json.dumps({"error": "No predictions available"})
            return json.dumps({"predictions": preds})
        except Exception as e:
            logger.error(f"get_bzzoiro_predictions failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def get_bzzoiro_match_stats(self, event_id: int) -> str:
        """Get per-shot xG stats from Bzzoiro."""
        if self.bzzoiro_service is None:
            return json.dumps({"error": "BzzoiroService not available"})
        try:
            stats = await self.bzzoiro_service.get_match_stats(event_id)
            if stats is None:
                return json.dumps({"error": "No stats available"})
            return json.dumps({"stats": stats})
        except Exception as e:
            logger.error(f"get_bzzoiro_match_stats failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # --- v0.8.5: EasySoccerData Integration (Sofascore) ---

    @Slot(result=str)
    async def check_easy_soccer_status(self) -> str:
        """Check if EasySoccerData is available."""
        if self.easy_soccer_service is None:
            return json.dumps({"available": False, "error": "Service not initialized"})
        try:
            ok = self.easy_soccer_service.check_available()
            return json.dumps({"available": ok})
        except Exception as e:
            logger.error(f"check_easy_soccer_status failed: {e}")
            return json.dumps({"available": False, "error": ErrorSanitizer.sanitize_error(e)})

    @Slot(result=str)
    async def get_easy_soccer_live(self) -> str:
        """Get live events from Sofascore via EasySoccerData."""
        if self.easy_soccer_service is None:
            return json.dumps({"matches": []})
        try:
            events = self.easy_soccer_service.get_live_events()
            return json.dumps({"matches": events})
        except Exception as e:
            logger.error(f"get_easy_soccer_live failed: {e}")
            return json.dumps({"matches": []})

    @Slot(int, result=str)
    async def get_easy_soccer_event(self, event_id: int) -> str:
        """Get match details from Sofascore."""
        if self.easy_soccer_service is None:
            return json.dumps({"error": "EasySoccerData not available"})
        try:
            detail = self.easy_soccer_service.get_event(event_id)
            if detail is None:
                return json.dumps({"error": "Event not found"})
            return json.dumps({"event": detail})
        except Exception as e:
            logger.error(f"get_easy_soccer_event failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def get_easy_soccer_incidents(self, event_id: int) -> str:
        """Get match incidents from Sofascore."""
        if self.easy_soccer_service is None:
            return json.dumps({"incidents": []})
        try:
            incidents = self.easy_soccer_service.get_match_incidents(event_id)
            return json.dumps({"incidents": incidents})
        except Exception as e:
            logger.error(f"get_easy_soccer_incidents failed: {e}")
            return json.dumps({"incidents": []})

    @Slot(int, result=str)
    async def get_easy_soccer_player(self, player_id: int) -> str:
        """Get player info from Sofascore."""
        if self.easy_soccer_service is None:
            return json.dumps({"error": "EasySoccerData not available"})
        try:
            player = self.easy_soccer_service.get_player(player_id)
            if player is None:
                return json.dumps({"error": "Player not found"})
            return json.dumps({"player": player})
        except Exception as e:
            logger.error(f"get_easy_soccer_player failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def search_easy_soccer_events(self, date: str) -> str:
        """Get scheduled events for a date from Sofascore."""
        if self.easy_soccer_service is None:
            return json.dumps({"events": []})
        try:
            events = self.easy_soccer_service.search_events(date)
            return json.dumps({"events": events})
        except Exception as e:
            logger.error(f"search_easy_soccer_events failed: {e}")
            return json.dumps({"events": []})

    # --- v0.8.5: API-Football (api-sports.io) Integration ---

    @Slot(result=str)
    async def check_apifootball_status(self) -> str:
        """Check if API-Football is available."""
        if self.api_football_service is None:
            return json.dumps({"available": False, "error": "Service not initialized"})
        try:
            status = await self.api_football_service.check_status()
            return json.dumps(status)
        except Exception as e:
            logger.error(f"check_apifootball_status failed: {e}")
            return json.dumps({"available": False, "error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def search_apifootball_team(self, query: str) -> str:
        """Search teams on API-Football."""
        if self.api_football_service is None:
            return json.dumps({"teams": []})
        try:
            query = SecurityValidator.sanitize_string(query, max_length=100)
            teams = await self.api_football_service.search_team(query)
            return json.dumps({"teams": teams})
        except Exception as e:
            logger.error(f"search_apifootball_team failed: {e}")
            return json.dumps({"teams": []})

    @Slot(int, str, result=str)
    async def import_apifootball_squad(self, match_id: int, team_id: int, side: str) -> str:
        """Import API-Football team squad as player profiles."""
        if self.api_football_service is None or self.player_profile_service is None:
            return json.dumps({"success": False, "error": "Required service not available"})
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            side = SecurityValidator.sanitize_string(side, max_length=10)
            if side not in ("home", "away"):
                return json.dumps({"success": False, "error": "side must be 'home' or 'away'"})
            squad = await self.api_football_service.get_team_squad(team_id)
            created = []
            skipped = 0
            existing = await self.player_profile_service.get_all_profiles(team=side)
            existing_nums = {p.jersey_number for p in existing if p.jersey_number is not None}
            for p in squad:
                jersey = p.get("jersey_number")
                if jersey is not None and jersey in existing_nums:
                    skipped += 1
                    continue
                try:
                    profile = await self.player_profile_service.create_profile(
                        display_name=p.get("name"),
                        jersey_number=jersey,
                        preferred_position=p.get("position"),
                        team=side,
                        apifb_person_id=p.get("id"),
                        apifb_team_id=team_id,
                    )
                    created.append({
                        "profile_id": profile.id,
                        "name": p.get("name"),
                        "jersey": jersey,
                        "position": p.get("position"),
                    })
                except Exception as e:
                    logger.warning(f"Failed to create profile: {e}")
            if side == "home":
                await self.storage_service.update_match_apifootball(match_id, apifb_home_team_id=team_id)
            else:
                await self.storage_service.update_match_apifootball(match_id, apifb_away_team_id=team_id)
            return json.dumps({"success": True, "created": created, "skipped": skipped})
        except Exception as e:
            logger.error(f"import_apifootball_squad failed: {e}")
            return json.dumps({"success": False, "error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, int, result=str)
    async def get_apifootball_standings(self, league_id: int, season: int = 2024) -> str:
        """Get league standings from API-Football."""
        if self.api_football_service is None:
            return json.dumps({"standings": []})
        try:
            standings = await self.api_football_service.get_standings(league_id, season)
            return json.dumps({"standings": standings})
        except Exception as e:
            logger.error(f"get_apifootball_standings failed: {e}")
            return json.dumps({"standings": []})

    @Slot(int, int, result=str)
    async def get_apifootball_fixtures(self, team_id: int, season: int) -> str:
        """Get team fixtures from API-Football."""
        if self.api_football_service is None:
            return json.dumps({"matches": []})
        try:
            matches = await self.api_football_service.get_fixtures(team_id, season, last=5)
            return json.dumps({"matches": matches})
        except Exception as e:
            logger.error(f"get_apifootball_fixtures failed: {e}")
            return json.dumps({"matches": []})

    @Slot(int, result=str)
    async def get_apifootball_fixture_detail(self, fixture_id: int) -> str:
        """Get detailed fixture info from API-Football."""
        if self.api_football_service is None:
            return json.dumps({"error": "ApiFootballService not available"})
        try:
            detail = await self.api_football_service.get_fixture_detail(fixture_id)
            if detail is None:
                return json.dumps({"error": "Fixture not found"})
            return json.dumps({"fixture": detail})
        except Exception as e:
            logger.error(f"get_apifootball_fixture_detail failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def get_apifootball_predictions(self, fixture_id: int) -> str:
        """Get AI predictions from API-Football."""
        if self.api_football_service is None:
            return json.dumps({"error": "ApiFootballService not available"})
        try:
            preds = await self.api_football_service.get_predictions(fixture_id)
            if preds is None:
                return json.dumps({"error": "No predictions available"})
            return json.dumps({"predictions": preds})
        except Exception as e:
            logger.error(f"get_apifootball_predictions failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(result=str)
    async def get_apifootball_live(self) -> str:
        """Get live fixtures from API-Football."""
        if self.api_football_service is None:
            return json.dumps({"matches": []})
        try:
            matches = await self.api_football_service.get_live_fixtures()
            return json.dumps({"matches": matches})
        except Exception as e:
            logger.error(f"get_apifootball_live failed: {e}")
            return json.dumps({"matches": []})

    @Slot(int, int, int, result=str)
    async def verify_match_apifootball(self, match_id: int, fixture_id: int) -> str:
        """Compare detected score vs API-Football."""
        if self.api_football_service is None:
            return json.dumps({"error": "ApiFootballService not available"})
        try:
            match_id = SecurityValidator.validate_match_id(match_id)
            match = await self.storage_service.get_match(match_id)
            if not match:
                return json.dumps({"error": "Match not found"})
            detail = await self.api_football_service.get_fixture_detail(fixture_id)
            if detail is None:
                return json.dumps({"error": "Could not fetch fixture"})
            events = await self.storage_service.get_match_events(match_id)
            shot_events = [e for e in events if e.get("type") == "goal"]
            detected_home = sum(1 for e in shot_events if e.get("team") == "home")
            detected_away = sum(1 for e in shot_events if e.get("team") == "away")
            api_home = detail.get("home_score") or 0
            api_away = detail.get("away_score") or 0
            match_name = detail.get("home_team", "") + " vs " + detail.get("away_team", "")
            match_ok = (detected_home == api_home) and (detected_away == api_away)
            await self.storage_service.update_match_apifootball(match_id, apifb_fixture_id=fixture_id)
            return json.dumps({
                "success": True,
                "match": match_name,
                "api_score": f"{api_home}-{api_away}",
                "detected_score": f"{detected_home}-{detected_away}",
                "match_ok": match_ok,
            })
        except Exception as e:
            logger.error(f"verify_match_apifootball failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # TheSportsDB slots
    # ================================================================

    @Slot(result=str)
    async def check_thesportsdb_status(self) -> str:
        """Check if TheSportsDB service is available."""
        import json
        if self.thesportsdb_service is None:
            return json.dumps({"available": False})
        try:
            leagues = await self.thesportsdb_service.get_all_leagues()
            available = len(leagues) > 0
            if available:
                self.thesportsdb_service._available = True
            return json.dumps({"available": available})
        except Exception:
            return json.dumps({"available": False})

    @Slot(str, result=str)
    async def search_thesportsdb_team(self, query: str) -> str:
        """Search teams by name via TheSportsDB."""
        import json
        if self.thesportsdb_service is None:
            return json.dumps({"teams": []})
        try:
            teams = await self.thesportsdb_service.search_teams(query)
            return json.dumps({
                "teams": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "league": t.league_name,
                        "league_id": t.league_id,
                        "badge": t.badge_url,
                        "stadium": t.stadium,
                        "location": t.location,
                        "formed_year": t.formed_year,
                        "api_football_id": t.api_football_id,
                    }
                    for t in teams
                ]
            })
        except Exception as e:
            logger.error(f"search_thesportsdb_team failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def get_thesportsdb_standings(self, league_id: str) -> str:
        """Get standings for a league via TheSportsDB."""
        import json
        if self.thesportsdb_service is None:
            return json.dumps({"standings": []})
        try:
            standings = await self.thesportsdb_service.get_standings(league_id)
            return json.dumps({
                "standings": [
                    {
                        "rank": s.rank,
                        "team": s.team_name,
                        "team_id": s.team_id,
                        "badge": s.badge_url,
                        "played": s.played,
                        "won": s.won,
                        "drawn": s.drawn,
                        "lost": s.lost,
                        "goals_for": s.goals_for,
                        "goals_against": s.goals_against,
                        "goal_diff": s.goal_diff,
                        "points": s.points,
                        "form": s.form,
                        "description": s.description,
                    }
                    for s in standings
                ]
            })
        except Exception as e:
            logger.error(f"get_thesportsdb_standings failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def get_thesportsdb_team_events_last(self, team_id: str) -> str:
        """Get recent events for a team via TheSportsDB."""
        import json
        if self.thesportsdb_service is None:
            return json.dumps({"events": []})
        try:
            events = await self.thesportsdb_service.get_team_events_last(team_id)
            return json.dumps({
                "events": [
                    {
                        "id": e.id,
                        "event": e.event_name,
                        "home": e.home_team,
                        "away": e.away_team,
                        "home_score": e.home_score,
                        "away_score": e.away_score,
                        "round": e.round,
                        "date": e.date,
                        "time": e.time,
                        "league": e.league_name,
                    }
                    for e in events
                ]
            })
        except Exception as e:
            logger.error(f"get_thesportsdb_team_events_last failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def get_thesportsdb_team_events_next(self, team_id: str) -> str:
        """Get upcoming events for a team via TheSportsDB."""
        import json
        if self.thesportsdb_service is None:
            return json.dumps({"events": []})
        try:
            events = await self.thesportsdb_service.get_team_events_next(team_id)
            return json.dumps({
                "events": [
                    {
                        "id": e.id,
                        "event": e.event_name,
                        "home": e.home_team,
                        "away": e.away_team,
                        "home_score": e.home_score,
                        "away_score": e.away_score,
                        "round": e.round,
                        "date": e.date,
                        "time": e.time,
                        "league": e.league_name,
                    }
                    for e in events
                ]
            })
        except Exception as e:
            logger.error(f"get_thesportsdb_team_events_next failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, str, result=str)
    async def get_thesportsdb_team_info(self, team_id: str) -> str:
        """Get team details via TheSportsDB."""
        import json
        if self.thesportsdb_service is None:
            return json.dumps({"team": None})
        try:
            team = await self.thesportsdb_service.get_team(team_id)
            if not team:
                return json.dumps({"team": None})
            return json.dumps({
                "team": {
                    "id": team.id,
                    "name": team.name,
                    "alternate_name": team.alternate_name,
                    "league": team.league_name,
                    "league_id": team.league_id,
                    "badge": team.badge_url,
                    "stadium": team.stadium,
                    "capacity": team.stadium_capacity,
                    "location": team.location,
                    "formed_year": team.formed_year,
                    "description": team.description[:500] if team.description else "",
                    "api_football_id": team.api_football_id,
                }
            })
        except Exception as e:
            logger.error(f"get_thesportsdb_team_info failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, str, str, str, result=str)
    async def get_football_team_matches(self, api_team_id: int, date_from: str, date_to: str) -> str:
        """Get upcoming/recent matches for a team."""
        import json

        if self.football_data_service is None:
            return json.dumps({"matches": []})
        try:
            matches = await self.football_data_service.get_team_matches(
                api_team_id, date_from=date_from or None, date_to=date_to or None
            )
            return json.dumps({"matches": matches})
        except Exception as e:
            logger.error(f"get_football_team_matches failed: {e}")
            return json.dumps({"matches": []})

    # ================================================================
    # StatsBomb slots
    # ================================================================

    @Slot(result=str)
    async def check_statsbomb_status(self) -> str:
        """Check if StatsBomb service is available."""
        import json
        if self.statsbomb_service is None:
            return json.dumps({"available": False})
        try:
            comps = await self.statsbomb_service.get_competitions()
            available = len(comps) > 0
            return json.dumps({
                "available": available,
                "competitions": len(comps),
            })
        except Exception:
            return json.dumps({"available": False})

    @Slot(result=str)
    async def get_statsbomb_competitions(self) -> str:
        """List all StatsBomb competitions/seasons."""
        import json
        if self.statsbomb_service is None:
            return json.dumps({"competitions": []})
        try:
            comps = await self.statsbomb_service.get_competitions()
            return json.dumps({
                "competitions": [
                    {
                        "competition_id": c.competition_id,
                        "season_id": c.season_id,
                        "name": c.competition_name,
                        "country": c.country_name,
                        "season": c.season_name,
                        "gender": c.competition_gender,
                        "international": c.competition_international,
                        "youth": c.competition_youth,
                        "has_360": c.has_360,
                    }
                    for c in comps
                ]
            })
        except Exception as e:
            logger.error(f"get_statsbomb_competitions failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, int, result=str)
    async def get_statsbomb_matches(self, competition_id: int, season_id: int) -> str:
        """List matches in a StatsBomb competition+season."""
        import json
        if self.statsbomb_service is None:
            return json.dumps({"matches": []})
        try:
            matches = await self.statsbomb_service.get_matches(competition_id, season_id)
            return json.dumps({
                "matches": [
                    {
                        "match_id": m.match_id,
                        "home": m.home_team,
                        "away": m.away_team,
                        "home_score": m.home_score,
                        "away_score": m.away_score,
                        "date": m.match_date,
                        "stage": m.competition_stage,
                        "stadium": m.stadium,
                        "has_360": m.has_360,
                    }
                    for m in matches
                ]
            })
        except Exception as e:
            logger.error(f"get_statsbomb_matches failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def get_statsbomb_events(self, match_id: int) -> str:
        """Get all events for a StatsBomb match (summary)."""
        import json
        if self.statsbomb_service is None:
            return json.dumps({"events": [], "summary": {}})
        try:
            events = await self.statsbomb_service.get_events(match_id)
            shots = [e for e in events if e.event_type == "Shot"]
            passes = [e for e in events if e.event_type == "Pass"]
            total_xg = sum(e.xg for e in shots if e.xg is not None)
            teams = {e.team for e in events if e.team}
            return json.dumps({
                "summary": {
                    "total_events": len(events),
                    "shots": len(shots),
                    "passes": len(passes),
                    "total_xg": round(total_xg, 3),
                    "teams": sorted(teams),
                },
                "shots": [
                    {
                        "minute": s.minute,
                        "team": s.team,
                        "player": s.player,
                        "xg": s.xg,
                        "outcome": s.outcome,
                        "body_part": s.shot_body_part,
                        "type": s.shot_type,
                    }
                    for s in shots[:20]
                ],
            })
        except Exception as e:
            logger.error(f"get_statsbomb_events failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def get_statsbomb_lineups(self, match_id: int) -> str:
        """Get lineups for a StatsBomb match."""
        import json
        if self.statsbomb_service is None:
            return json.dumps({"lineups": []})
        try:
            lineups = await self.statsbomb_service.get_lineups(match_id)
            return json.dumps({
                "lineups": [
                    {
                        "team": l.team_name,
                        "team_id": l.team_id,
                        "players": l.players,
                    }
                    for l in lineups
                ]
            })
        except Exception as e:
            logger.error(f"get_statsbomb_lineups failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def search_statsbomb_team(self, team_name: str) -> str:
        """Find matches for a team across StatsBomb data."""
        import json
        if self.statsbomb_service is None or not team_name.strip():
            return json.dumps({"matches": []})
        try:
            matches = await self.statsbomb_service.search_team_matches(team_name)
            return json.dumps({
                "matches": [
                    {
                        "match_id": m.match_id,
                        "competition": m.competition_name,
                        "season": m.season_name,
                        "home": m.home_team,
                        "away": m.away_team,
                        "home_score": m.home_score,
                        "away_score": m.away_score,
                        "date": m.match_date,
                    }
                    for m in matches[:30]
                ]
            })
        except Exception as e:
            logger.error(f"search_statsbomb_team failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # OpenFootball slots
    # ================================================================

    @Slot(result=str)
    async def check_openfootball_status(self) -> str:
        """Check if openfootball service is available."""
        import json
        if self.openfootball_service is None:
            return json.dumps({"available": False})
        try:
            sample = await self.openfootball_service.get_matches("en.1", "2024-25")
            available = len(sample) > 0
            return json.dumps({
                "available": available,
                "competitions": len(self.openfootball_service.get_competitions()),
                "sample_matches": len(sample),
            })
        except Exception:
            return json.dumps({"available": False})

    @Slot(result=str)
    async def get_openfootball_competitions(self) -> str:
        """List available openfootball competitions + seasons."""
        import json
        if self.openfootball_service is None:
            return json.dumps({"competitions": []})
        comps = self.openfootball_service.get_competitions()
        return json.dumps({
            "competitions": [
                {"id": c.id, "name": c.name, "seasons": c.seasons}
                for c in comps
            ]
        })

    @Slot(str, str, result=str)
    async def get_openfootball_matches(self, competition_id: str, season: str) -> str:
        """Fetch matches for a competition + season."""
        import json
        if self.openfootball_service is None:
            return json.dumps({"matches": []})
        try:
            matches = await self.openfootball_service.get_matches(competition_id, season)
            return json.dumps({
                "matches": [
                    {
                        "competition": m.competition,
                        "round": m.round,
                        "date": m.date,
                        "time": m.time,
                        "home": m.home_team,
                        "away": m.away_team,
                        "home_score": m.home_score,
                        "away_score": m.away_score,
                        "ht_home": m.half_time_home,
                        "ht_away": m.half_time_away,
                    }
                    for m in matches
                ]
            })
        except Exception as e:
            logger.error(f"get_openfootball_matches failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(str, result=str)
    async def search_openfootball_team(self, team_name: str) -> str:
        """Search matches by team name across all leagues/seasons."""
        import json
        if self.openfootball_service is None or not team_name.strip():
            return json.dumps({"matches": []})
        try:
            matches = await self.openfootball_service.search_team_matches(team_name)
            return json.dumps({
                "matches": [
                    {
                        "competition": m.competition,
                        "season": m.season,
                        "round": m.round,
                        "date": m.date,
                        "home": m.home_team,
                        "away": m.away_team,
                        "home_score": m.home_score,
                        "away_score": m.away_score,
                    }
                    for m in matches[:40]
                ]
            })
        except Exception as e:
            logger.error(f"search_openfootball_team failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def get_openfootball_worldcup(self, year: int) -> str:
        """Fetch World Cup matches for a year."""
        import json
        if self.openfootball_service is None:
            return json.dumps({"matches": [], "years": []})
        try:
            matches = await self.openfootball_service.get_worldcup_matches(year)
            return json.dumps({
                "years": self.openfootball_service.get_all_worldcup_years(),
                "matches": [
                    {
                        "round": m.round,
                        "date": m.date,
                        "home": m.home_team,
                        "away": m.away_team,
                        "home_score": m.home_score,
                        "away_score": m.away_score,
                    }
                    for m in matches
                ],
            })
        except Exception as e:
            logger.error(f"get_openfootball_worldcup failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Roboflow Sports slots
    # ================================================================

    @Slot(result=str)
    async def check_roboflow_sports_status(self) -> str:
        """Check if roboflow/sports package is available."""
        import json
        if self.roboflow_sports_service is None:
            return json.dumps({"available": False})
        return json.dumps({
            "available": self.roboflow_sports_service.available,
            "has_team_classifier": self.roboflow_sports_service.has_team_classifier,
            "has_view_transformer": self.roboflow_sports_service.has_view_transformer,
        })

    @Slot(float, result=str)
    async def rf_draw_pitch(self, scale: float) -> str:
        """Draw a soccer pitch image and return base64 PNG."""
        import json
        import base64
        if self.roboflow_sports_service is None or not self.roboflow_sports_service.available:
            return json.dumps({"error": "roboflow/sports not installed"})
        try:
            import cv2  # type: ignore
            img = self.roboflow_sports_service.draw_pitch(scale=scale)
            if img is None:
                return json.dumps({"error": "draw_pitch returned None"})
            _, buf = cv2.imencode(".png", img)
            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
            return json.dumps({
                "success": True,
                "image_b64": b64,
                "shape": list(img.shape),
            })
        except Exception as e:
            logger.error(f"rf_draw_pitch failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Pose analysis slots
    # ================================================================

    @Slot(result=str)
    async def check_pose_status(self) -> str:
        """Check if pose model is available."""
        import json
        if self.pose_analysis_service is None:
            return json.dumps({"available": False})
        try:
            available = self.pose_analysis_service.available
            return json.dumps({"available": available})
        except Exception:
            return json.dumps({"available": False})

    @Slot(int, result=str)
    async def get_activity_summary(self, track_id: int) -> str:
        """Get activity summary for a player track."""
        import json
        if self.pose_analysis_service is None:
            return json.dumps({"summary": {}})
        try:
            summary = self.pose_analysis_service.summarize_activity(track_id)
            return json.dumps({"summary": summary})
        except Exception as e:
            logger.error(f"get_activity_summary failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def get_activity_segments(self, track_id: int) -> str:
        """Get activity time segments for a player track."""
        import json
        if self.pose_analysis_service is None:
            return json.dumps({"segments": []})
        try:
            segs = self.pose_analysis_service.get_activity_segments(track_id)
            return json.dumps({
                "segments": [
                    {
                        "activity": s.activity,
                        "start_time": s.start_time,
                        "end_time": s.end_time,
                        "duration_s": s.duration_s,
                        "avg_speed_kmh": s.avg_speed_kmh,
                    }
                    for s in segs
                ]
            })
        except Exception as e:
            logger.error(f"get_activity_segments failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # MuJoCo ball trajectory slots
    # ================================================================

    @Slot(result=str)
    async def check_mujoco_status(self) -> str:
        """Check if MuJoCo is available (true even if using analytical fallback)."""
        import json
        if self.mujoco_ball_service is None:
            return json.dumps({"available": False, "uses_mujoco": False})
        return json.dumps({
            "available": self.mujoco_ball_service.available,
            "uses_mujoco": self.mujoco_ball_service.uses_mujoco,
        })

    @Slot(result=str)
    async def get_setpiece_presets(self) -> str:
        """Return preset set-piece scenarios."""
        import json
        if self.mujoco_ball_service is None:
            return json.dumps({"presets": []})
        return json.dumps({"presets": self.mujoco_ball_service.get_preset_setpieces()})

    @Slot(
        float, float, float, float, float, result=str,
    )
    async def simulate_trajectory(
        self,
        initial_speed: float,
        launch_angle_deg: float,
        spin_rps: float,
        direction_deg: float,
        duration_s: float,
    ) -> str:
        """Simulate a ball trajectory with the given parameters."""
        import json
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
                "points": [
                    {"t": p.t, "x": p.x, "y": p.y, "z": p.z}
                    for p in result.points[::5]
                ],
            })
        except Exception as e:
            logger.error(f"simulate_trajectory failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # FluidX3D slots
    # ================================================================

    @Slot(result=str)
    async def check_fluidx3d_status(self) -> str:
        """Check if FluidX3D binary is configured."""
        import json
        if self.fluidx3d_service is None:
            return json.dumps({
                "available": False,
                "license_notice": "FluidX3D is free for non-commercial use only.",
            })
        return json.dumps({
            "available": self.fluidx3d_service.available,
            "license_notice": self.fluidx3d_service.license_notice,
        })

    @Slot(float, float, float, result=str)
    async def simulate_ball_cfd(
        self, wind_speed: float, spin_rps: float, ball_radius: float
    ) -> str:
        """Run FluidX3D ball aerodynamics simulation (if binary configured)."""
        import json
        if self.fluidx3d_service is None:
            return json.dumps({"error": "FluidX3D service not initialized"})
        try:
            result = await self.fluidx3d_service.simulate_ball_aerodynamics(
                ball_radius=float(ball_radius) if ball_radius > 0 else 0.11,
                wind_speed=float(wind_speed),
                spin_rps=float(spin_rps),
            )
            return json.dumps({
                "success": result.success,
                "method": result.method,
                "notes": result.notes,
                "error": result.error,
            })
        except Exception as e:
            logger.error(f"simulate_ball_cfd failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Weather slots
    # ================================================================

    @Slot(result=str)
    async def check_weather_status(self) -> str:
        """Check weather service availability."""
        import json
        if self.weather_service is None:
            return json.dumps({"available": False})
        return json.dumps({
            "available": self.weather_service.available,
            "has_video_classifier": self.weather_service.has_video_classifier,
        })

    @Slot(float, float, str, bool, result=str)
    async def fetch_match_weather(
        self, latitude: float, longitude: float, date: str, is_forecast: bool
    ) -> str:
        """Fetch weather for a location and date from Open-Meteo."""
        import json
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

    @Slot(float, float, float, float, str, result=str)
    async def set_manual_weather(
        self, temperature: float, precipitation: float, wind: float, humidity: float, conditions: str
    ) -> str:
        """Build WeatherConditions from manual user input."""
        import json
        if self.weather_service is None:
            return json.dumps({"error": "Weather service not initialized"})
        result = WeatherService.from_manual(
            temperature_c=temperature,
            precipitation_mm=precipitation,
            wind_speed_kmh=wind,
            humidity_pct=humidity,
            conditions=conditions,
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

    @Slot(float, float, float, float, str, result=str)
    async def analyze_weather_impact(
        self, temperature: float, precipitation: float, wind: float, humidity: float, conditions: str
    ) -> str:
        """Analyze impact of given conditions on play."""
        import json
        if self.weather_service is None:
            return json.dumps({"error": "Weather service not initialized"})
        try:
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

    # ================================================================
    # Psychology slots
    # ================================================================

    @Slot(result=str)
    async def check_psychology_status(self) -> str:
        """Check psychology service availability."""
        import json
        if self.psychology_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.psychology_service.available})

    @Slot(int, str, str, str, result=str)
    async def analyze_match_psychology(
        self, match_id: int, home_team: str, away_team: str, events_json: str
    ) -> str:
        """Run full psychology analysis on match events.

        events_json: JSON string of list of event dicts.
        """
        import json
        if self.psychology_service is None:
            return json.dumps({"error": "Psychology service not initialized"})
        try:
            events = json.loads(events_json) if events_json else []
            report = self.psychology_service.analyze(
                match_id, home_team, away_team, events
            )
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
    # Football Rules slots
    # ================================================================

    @Slot(result=str)
    async def check_rules_status(self) -> str:
        """Check if football rules service is available."""
        import json
        if self.football_rules_service is None:
            return json.dumps({"available": False})
        return json.dumps({
            "available": self.football_rules_service.available,
            "laws_count": len(self.football_rules_service._laws),
        })

    @Slot(int, result=str)
    async def get_law_summary(self, law_number: int) -> str:
        """Get summary of a specific law of the game."""
        import json
        if self.football_rules_service is None:
            return json.dumps({"error": "Rules service not initialized"})
        law = self.football_rules_service.get_law_summary(law_number)
        if not law:
            return json.dumps({"error": f"Law {law_number} not found"})
        return json.dumps(law)

    @Slot(result=str)
    async def get_all_laws(self) -> str:
        """Return all 17 laws of the game."""
        import json
        if self.football_rules_service is None:
            return json.dumps({"laws": []})
        return json.dumps({"laws": self.football_rules_service.get_all_laws()})

    @Slot(str, float, float, str, result=str)
    async def classify_event_rule(
        self, event_type: str, x: float, y: float, side: str
    ) -> str:
        """Classify an event according to the Laws of the Game."""
        import json
        if self.football_rules_service is None:
            return json.dumps({"error": "Rules service not initialized"})
        try:
            ref = self.football_rules_service.classify_event(event_type, x, y, side)
            return json.dumps({
                "law": ref.law,
                "law_name": ref.law_name,
                "restart": ref.restart.value if ref.restart else None,
                "description": ref.description,
                "card_likely": ref.card_likely,
            })
        except Exception as e:
            logger.error(f"classify_event_rule failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(float, float, float, str, result=str)
    async def check_offside(
        self, attacker_x: float, defender_x: float, ball_x: float, attacking_direction: str
    ) -> str:
        """Check IFAB offside Law 11."""
        import json
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
    # Card Detection slots
    # ================================================================

    @Slot(result=str)
    async def check_cards_status(self) -> str:
        """Check card detection service availability."""
        import json
        if self.card_detection_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.card_detection_service.available})

    @Slot(str, result=str)
    async def infer_cards_tactically(self, events_json: str) -> str:
        """Infer cards from event severity patterns."""
        import json
        if self.card_detection_service is None:
            return json.dumps({"error": "Card detection service not initialized"})
        try:
            events = json.loads(events_json) if events_json else []
            cards = self.card_detection_service.infer_cards_tactically(events)
            return json.dumps({
                "cards": [
                    {
                        "card_type": c.card_type.value,
                        "minute": c.minute, "second": c.second,
                        "player_track_id": c.player_track_id,
                        "player_name": c.player_name, "team": c.team,
                        "source": c.source.value,
                        "confidence": c.confidence,
                        "description": c.description,
                    }
                    for c in cards
                ]
            })
        except Exception as e:
            logger.error(f"infer_cards_tactically failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(int, result=str)
    async def fetch_external_cards(self, match_id: int) -> str:
        """Fetch verified cards from external data (StatsBomb)."""
        import json
        if self.card_detection_service is None:
            return json.dumps({"error": "Card detection service not initialized"})
        try:
            cards = await self.card_detection_service.fetch_external_cards(
                match_id, statsbomb_service=self.statsbomb_service,
            )
            return json.dumps({
                "cards": [
                    {
                        "card_type": c.card_type.value,
                        "minute": c.minute, "second": c.second,
                        "player_name": c.player_name, "team": c.team,
                        "source": c.source.value, "confidence": c.confidence,
                        "description": c.description,
                    }
                    for c in cards
                ]
            })
        except Exception as e:
            logger.error(f"fetch_external_cards failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Raindrop Detection slots (tobybreckon-style)
    # ================================================================

    @Slot(result=str)
    async def check_raindrop_status(self) -> str:
        """Check raindrop detection service availability."""
        import json
        if self.weather_service is None:
            return json.dumps({"available": False})
        return json.dumps({
            "available": self.weather_service.has_raindrop_detector,
            "has_cnn": (
                self.weather_service._raindrop_service.has_cnn
                if self.weather_service._raindrop_service else False
            ),
        })

    @Slot(result=str)
    async def check_weather_classifier_status(self) -> str:
        """Check multi-class weather image classifier status."""
        import json
        if self.weather_service is None:
            return json.dumps({"available": False})
        return json.dumps({
            "available": self.weather_service.has_multi_class_classifier,
            "has_cnn": (
                self.weather_service._weather_classifier.has_cnn
                if self.weather_service._weather_classifier else False
            ),
        })

    @Slot(str, int, int, result=str)
    async def detect_raindrops_in_video(
        self, video_path: str, sample_every_n: int, max_frames: int
    ) -> str:
        """Run raindrop detection on a video file.

        Returns raindrop count, density, and is_rainy classification.
        """
        import json
        if self.weather_service is None or not self.weather_service.has_raindrop_detector:
            return json.dumps({"error": "Raindrop service not available"})
        try:
            result = self.weather_service._raindrop_service.detect_from_video_file(
                video_path, sample_every_n, max_frames
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

    @Slot(str, result=str)
    async def classify_video_weather(
        self, video_path: str
    ) -> str:
        """Classify weather conditions from a video file using combined
        raindrop detection + multi-class CNN.

        Returns a comprehensive weather analysis.
        """
        import json
        if self.weather_service is None:
            return json.dumps({"error": "Weather service not available"})
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
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
    # Set-piece slots
    # ================================================================

    @Slot(result=str)
    async def check_setpiece_status(self) -> str:
        """Check if set-piece service is available."""
        import json
        if self.setpiece_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.setpiece_service.available})

    @Slot(str, str, result=str)
    async def analyze_setpieces(
        self, events_json: str, home_team: str
    ) -> str:
        """Run set-piece analysis on a list of events."""
        import json
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
    # Goalkeeper slots
    # ================================================================

    @Slot(result=str)
    async def check_goalkeeper_status(self) -> str:
        """Check if goalkeeper service is available."""
        import json
        if self.goalkeeper_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.goalkeeper_service.available})

    @Slot(str, str, str, bool, result=str)
    async def analyze_goalkeeper(
        self, team: str, actions_json: str, shots_json: str, clean_sheet: bool
    ) -> str:
        """Run goalkeeper analysis from actions and shots faced."""
        import json
        if self.goalkeeper_service is None:
            return json.dumps({"error": "Goalkeeper service not initialized"})
        try:
            from kawkab.services.goalkeeper_service import GoalkeeperAction
            actions_data = json.loads(actions_json) if actions_json else []
            shots_data = json.loads(shots_json) if shots_json else []
            actions = [
                GoalkeeperAction(
                    action_type=a.get("action_type", "save"),
                    minute=a.get("minute", 0),
                    second=a.get("second", 0),
                    team=a.get("team", team),
                    player_track_id=a.get("player_track_id"),
                    outcome=a.get("outcome", "complete"),
                    quality=a.get("quality", 0.5),
                    x=a.get("x"),
                    y=a.get("y"),
                )
                for a in actions_data
            ]
            stats = self.goalkeeper_service.compute_stats(
                team, actions, shots_data, clean_sheet=clean_sheet
            )
            return json.dumps({
                "team": stats.team,
                "saves": stats.saves,
                "goals_conceded": stats.goals_conceded,
                "shots_faced": stats.shots_faced,
                "save_rate": stats.save_rate,
                "goals_prevented_xgot": stats.goals_prevented_xgot,
                "xgot_per_shot": stats.xgot_per_shot,
                "crosses_claimed": stats.crosses_claimed,
                "crosses_punched": stats.crosses_punched,
                "crosses_missed": stats.crosses_missed,
                "sweep_actions": stats.sweep_actions,
                "short_distribution_attempts": stats.short_distribution_attempts,
                "short_distribution_successful": stats.short_distribution_successful,
                "long_distribution_attempts": stats.long_distribution_attempts,
                "long_distribution_successful": stats.long_distribution_successful,
                "clean_sheet": stats.clean_sheet,
                "notes": stats.notes,
            })
        except Exception as e:
            logger.error(f"analyze_goalkeeper failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    @Slot(float, float, str, bool, result=str)
    async def compute_xgot(
        self, shot_x: float, shot_y: float, body_part: str, one_on_one: bool
    ) -> str:
        """Compute xGOT (expected goals on target) for a shot."""
        import json
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
    # Substitution slots
    # ================================================================

    @Slot(result=str)
    async def check_substitution_status(self) -> str:
        """Check if substitution service is available."""
        import json
        if self.substitution_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.substitution_service.available})

    @Slot(str, str, str, result=str)
    async def analyze_substitutions(
        self, team: str, subs_json: str, events_json: str
    ) -> str:
        """Analyze impact of each substitution."""
        import json
        if self.substitution_service is None:
            return json.dumps({"error": "Substitution service not initialized"})
        try:
            from kawkab.services.substitution_service import SubstitutionEvent
            subs_data = json.loads(subs_json) if subs_json else []
            events = json.loads(events_json) if events_json else []
            subs = [
                SubstitutionEvent(
                    minute=s.get("minute", 0),
                    second=s.get("second", 0),
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
                "team": report.team,
                "total_impact": report.total_impact,
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
                        "rating": i.rating,
                        "verdict": i.verdict,
                        "xg_delta": i.xg_delta,
                        "possession_delta": i.possession_delta,
                        "goals_for": i.goals_for,
                        "goals_against": i.goals_against,
                        "notes": i.notes,
                    }
                    for i in report.impacts
                ],
            })
        except Exception as e:
            logger.error(f"analyze_substitutions failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # ================================================================
    # Possession slots
    # ================================================================

    @Slot(result=str)
    async def check_possession_status(self) -> str:
        """Check if possession service is available."""
        import json
        if self.possession_service is None:
            return json.dumps({"available": False})
        return json.dumps({"available": self.possession_service.available})

    @Slot(str, str, str, result=str)
    async def analyze_possession(
        self, home_team: str, away_team: str, events_json: str
    ) -> str:
        """Run detailed possession analysis with proper attribution."""
        import json
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

