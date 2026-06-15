"""QWebChannel bridge - exposes Python services to JavaScript frontend.

The frontend calls these methods directly via QWebChannel.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from kawkab.core.logging import get_logger

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

        logger.info("Bridge initialized")

    @Slot(int, result=str)
    async def get_first_frame(self, match_id: int) -> str:
        """Return path to a frame image for calibration UI.

        Args:
            match_id: Database ID of the match

        Returns:
            JSON with frame path or error
        """
        try:
            match = await self.storage_service.get_match(match_id)
            if not match or not match.get("video_path"):
                return json.dumps({"error": "No video found"})
            return json.dumps({
                "path": match["video_path"],
                "match_id": match_id,
            })
        except Exception as e:
            logger.error(f"get_first_frame failed: {e}")
            return json.dumps({"error": str(e)})

    @Slot(int, str, float, float, result=str)
    async def save_homography(
        self,
        match_id: int,
        corners_json: str,
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
    ) -> str:
        """Save homography calibration for a match.

        Args:
            match_id: Database ID of the match
            corners_json: JSON string with 4 corner points, or "auto" for estimated
            pitch_length_m: Real pitch length
            pitch_width_m: Real pitch width

        Returns:
            JSON with success status and confidence
        """
        try:
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
            return json.dumps({"success": False, "error": str(e)})

    @Slot(int, result=str)
    async def get_homography(self, match_id: int) -> str:
        """Get saved homography for a match."""
        try:
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
            return json.dumps({"error": str(e)})

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
            video_path_obj = Path(video_path)
            if not video_path_obj.exists():
                raise FileNotFoundError(f"Video not found: {video_path}")

            self.analysisProgress.emit(0.0, "Starting analysis...")

            self.analysisProgress.emit(0.05, "Enhancing video...")
            preprocessed_path = (
                self.enhancement_service._cache_dir
                / f"{video_path_obj.stem}_preprocessed.mp4"
            )
            await self.enhancement_service.preprocess_video(
                video_path_obj, preprocessed_path
            )

            self.analysisProgress.emit(0.15, "Detecting players and ball...")

            async def progress_cb(progress: float, msg: str) -> None:
                total = 0.15 + progress * 0.55
                self.analysisProgress.emit(total, msg)

            track_data = await self.cv_service.process_video(
                preprocessed_path, progress_callback=progress_cb
            )

            await self.storage_service.update_match_analysis(
                match_id=match_id,
                duration=track_data.duration_seconds,
                fps=track_data.fps,
                total_frames=track_data.total_frames,
            )

            self.analysisProgress.emit(0.75, "Computing statistics...")
            analysis = await self.analysis_service.analyze_match(
                track_data, match_id=match_id
            )

            self.analysisProgress.emit(0.85, "Saving results...")
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
                "confidence": analysis.confidence_overall,
            }

            self.analysisComplete.emit(result)
            return json.dumps(result)
        except Exception as e:
            logger.exception(f"Analysis failed: {e}")
            self.analysisError.emit(str(e))
            return json.dumps({"error": str(e)})

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
            return f"Error generating report: {e}"

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
            events = await self.storage_service.get_match_events(match_id)
            return json.dumps(events)
        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return json.dumps([])

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
