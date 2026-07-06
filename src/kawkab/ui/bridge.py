"""QWebChannel bridge — thin dispatcher delegating to focused handler modules.

The frontend calls these methods directly via QWebChannel (kawkab.methodName()).
Each @Slot method is a 2-line delegator; real implementation lives in
bridge_handlers/ modules.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from kawkab.core.logging import get_logger
from kawkab.core.security import RateLimiter
from kawkab.ui.bridge_handlers import (
    AnalysisHandler,
    CodingHandler,
    ExportHandler,
    ExternalHandler,
    LifecycleHandler,
    StorageHandler,
    VideoHandler,
)

logger = get_logger(__name__)


class Bridge(QObject):
    """Bridge between Python services and JavaScript frontend.

    Thin dispatcher — all @Slot methods delegate to handler classes.
    Exposed as "kawkab" in QWebChannel.
    """

    analysisProgress = Signal(float, str)
    analysisComplete = Signal(dict)
    analysisError = Signal(str)
    matchSaved = Signal(int)
    calibrationSaved = Signal(int, dict)

    def __init__(
        self,
        cv_service=None,
        enhancement_service=None,
        analysis_service=None,
        llm_service=None,
        knowledge_service=None,
        storage_service=None,
        audio_service=None,
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
        realtime_service=None,
        profiler=None,
        frame_skip=3,
        parent=None,
    ) -> None:
        super().__init__(parent)

        # Build services dict for handler injection
        services = {
            "cv_service": cv_service,
            "enhancement_service": enhancement_service,
            "analysis_service": analysis_service,
            "llm_service": llm_service,
            "knowledge_service": knowledge_service,
            "storage_service": storage_service,
            "audio_service": audio_service,
            "homography_service": homography_service,
            "lightglue_homography_service": lightglue_homography_service,
            "player_profile_service": player_profile_service,
            "multi_match_service": multi_match_service,
            "data_export_service": data_export_service,
            "visualization_service": visualization_service,
            "anomaly_detection_service": anomaly_detection_service,
            "quality_scoring_service": quality_scoring_service,
            "advanced_event_detection_service": advanced_event_detection_service,
            "physical_load_service": physical_load_service,
            "pressure_metrics_service": pressure_metrics_service,
            "benchmark_service": benchmark_service,
            "feedback_service": feedback_service,
            "clip_service": clip_service,
            "face_recognition_service": face_recognition_service,
            "football_data_service": football_data_service,
            "bzzoiro_service": bzzoiro_service,
            "easy_soccer_service": easy_soccer_service,
            "api_football_service": api_football_service,
            "thesportsdb_service": thesportsdb_service,
            "statsbomb_service": statsbomb_service,
            "openfootball_service": openfootball_service,
            "roboflow_sports_service": roboflow_sports_service,
            "pose_analysis_service": pose_analysis_service,
            "mujoco_ball_service": mujoco_ball_service,
            "fluidx3d_service": fluidx3d_service,
            "weather_service": weather_service,
            "psychology_service": psychology_service,
            "football_rules_service": football_rules_service,
            "card_detection_service": card_detection_service,
            "setpiece_service": setpiece_service,
            "goalkeeper_service": goalkeeper_service,
            "substitution_service": substitution_service,
            "possession_service": possession_service,
            "realtime_service": realtime_service,
            "profiler": profiler,
            "frame_skip": frame_skip,
        }

        # Create rate limiter for bridge handlers
        self._rate_limiter = RateLimiter()
        self._rate_limiter.configure("analysis", 5)
        self._rate_limiter.configure("export", 10)
        self._rate_limiter.configure("search", 30)
        self._rate_limiter.configure("tracking", 5)
        self._rate_limiter.configure("coding", 20)

        self._analysis = AnalysisHandler(self, services, rate_limiter=self._rate_limiter)
        self._coding = CodingHandler(self, services, rate_limiter=self._rate_limiter)
        self._export = ExportHandler(self, services, rate_limiter=self._rate_limiter)
        self._video = VideoHandler(self, services, rate_limiter=self._rate_limiter)
        self._storage = StorageHandler(self, services, rate_limiter=self._rate_limiter)
        self._external = ExternalHandler(self, services, rate_limiter=self._rate_limiter)
        self._lifecycle = LifecycleHandler(self, services, rate_limiter=self._rate_limiter)

        logger.info("Bridge initialized with handler delegation")

    # ================================================================
    # Core match operations
    # ================================================================

    @Slot(int, result=str)
    async def get_first_frame(self, match_id: int) -> str:
        return await self._analysis.get_first_frame(match_id)

    @Slot(int, str, float, float, result=str)
    async def save_homography(self, match_id: int, corners_json: str, pitch_length_m: float = 105.0, pitch_width_m: float = 68.0) -> str:
        return await self._analysis.save_homography(match_id, corners_json, pitch_length_m, pitch_width_m)

    @Slot(int, result=str)
    async def get_homography(self, match_id: int) -> str:
        return await self._analysis.get_homography(match_id)

    @Slot(str, str, result=int)
    async def save_match(self, name: str, video_path: str) -> int:
        return await self._analysis.save_match(name, video_path)

    @Slot(int, str, result=str)
    async def analyze_match(self, match_id: int, video_path: str) -> str:
        return await self._analysis.analyze_match(match_id, video_path)

    @Slot(int, float, result=str)
    def get_overlay_data(self, match_id: int, timestamp: float) -> str:
        return self._analysis.get_overlay_data(match_id, timestamp)

    @Slot(int, str, str, result=str)
    async def generate_report(self, match_id: int, language: str, summary: str) -> str:
        return await self._analysis.generate_report(match_id, language, summary)

    @Slot(result=str)
    async def get_all_matches(self) -> str:
        return await self._analysis.get_all_matches()

    @Slot(int, result=str)
    async def get_match_events(self, match_id: int) -> str:
        return await self._analysis.get_match_events(match_id)

    @Slot(int, int, result=str)
    async def get_event_timestamp(self, match_id: int, event_id: int) -> str:
        return await self._analysis.get_event_timestamp(match_id, event_id)

    @Slot(int, float, float, result=str)
    async def get_unreviewed_events(self, match_id: int, min_confidence: float = 0.0, max_confidence: float = 0.7) -> str:
        return await self._analysis.get_unreviewed_events(match_id, min_confidence, max_confidence)

    @Slot(int, result=str)
    async def get_detection_summary(self, match_id: int) -> str:
        return await self._analysis.get_detection_summary(match_id)

    @Slot(int, int, str, str, result=str)
    async def submit_event_correction(self, match_id: int, event_id: int, action: str, corrections_json: str = "") -> str:
        return await self._analysis.submit_event_correction(match_id, event_id, action, corrections_json)

    @Slot(int, result=str)
    async def get_video_path(self, match_id: int) -> str:
        return await self._analysis.get_video_path(match_id)

    @Slot(result=str)
    async def get_knowledge_base_stats(self) -> str:
        return await self._analysis.get_knowledge_base_stats()

    @Slot(result=str)
    async def check_llm_availability(self) -> str:
        return await self._analysis.check_llm_availability()

    # ================================================================
    # Exports
    # ================================================================

    @Slot(str, result=str)
    async def export_match_csv(self, match_id_str: str) -> str:
        return await self._export.export_match_csv(match_id_str)

    @Slot(str, result=str)
    async def export_match_json(self, match_id_str: str) -> str:
        return await self._export.export_match_json(match_id_str)

    @Slot(int, str, result=str)
    async def export_report_pdf(self, match_id: int, language: str) -> str:
        return await self._export.export_report_pdf(match_id, language)

    @Slot(int, result=str)
    async def extract_event_clips(self, match_id: int) -> str:
        return await self._export.extract_event_clips(match_id)

    @Slot(str, str, result=str)
    async def export_match_statsbomb(self, match_id_str: str, file_path: str) -> str:
        return await self._export.export_match_statsbomb(match_id_str, file_path)

    # ================================================================
    # Player Profiles
    # ================================================================

    @Slot(str, str, int, str, result=str)
    async def create_player_profile(self, name: str, jersey: str, number: int, position: str) -> str:
        return await self._analysis.create_player_profile(name, jersey, number, position)

    @Slot(result=str)
    async def get_all_player_profiles(self) -> str:
        return await self._analysis.get_all_player_profiles()

    @Slot(result=str)
    async def get_face_gallery(self) -> str:
        return await self._analysis.get_face_gallery()

    @Slot(str, str, int, result=str)
    async def upload_face_photo(self, photo_path: str, display_name: str, jersey_number: int) -> str:
        return await self._analysis.upload_face_photo(photo_path, display_name, jersey_number)

    @Slot(int, result=str)
    async def match_faces_in_match(self, match_id: int) -> str:
        return await self._analysis.match_faces_in_match(match_id)

    # ================================================================
    # Multi-match & quality
    # ================================================================

    @Slot(str, str, str, result=str)
    async def compare_matches(self, match_id_1: str, match_id_2: str, focus: str) -> str:
        return await self._analysis.compare_matches(match_id_1, match_id_2, focus)

    @Slot(str, result=str)
    async def get_match_quality_report(self, match_id_str: str) -> str:
        return await self._analysis.get_match_quality_report(match_id_str)

    # ================================================================
    # Team & visualization
    # ================================================================

    @Slot(int, result=str)
    async def swap_teams(self, match_id: int) -> str:
        return await self._analysis.swap_teams(match_id)

    @Slot(int, result=str)
    async def generate_visualizations(self, match_id: int) -> str:
        return await self._analysis.generate_visualizations(match_id)

    # ================================================================
    # Event CRUD (storage)
    # ================================================================

    @Slot(int, str, result=str)
    async def update_event(self, event_id: int, updates_json: str) -> str:
        return await self._storage.update_event(event_id, updates_json)

    @Slot(int, result=str)
    async def delete_event(self, event_id: int) -> str:
        return await self._storage.delete_event(event_id)

    # ================================================================
    # Feedback
    # ================================================================

    @Slot(str, result=str)
    async def submit_feedback(self, feedback_json: str) -> str:
        return await self._storage.submit_feedback(feedback_json)

    @Slot(str, result=str)
    async def submit_issue(self, issue_json: str) -> str:
        return await self._storage.submit_issue(issue_json)

    @Slot(result=str)
    async def get_feedback_stats(self) -> str:
        return await self._storage.get_feedback_stats()

    # ================================================================
    # GPU & lifecycle
    # ================================================================

    @Slot(result=str)
    def get_gpu_info(self) -> str:
        return self._lifecycle.get_gpu_info()

    # ================================================================
    # External APIs — football-data.org
    # ================================================================

    @Slot(result=str)
    async def check_football_data_status(self) -> str:
        return await self._external.check_football_data_status()

    @Slot(str, result=str)
    async def search_football_team(self, query: str) -> str:
        return await self._external.search_football_team(query)

    @Slot(int, str, str, result=str)
    async def import_football_team_squad(self, match_id: int, api_team_id: str, side: str) -> str:
        return await self._external.import_football_team_squad(match_id, api_team_id, side)

    @Slot(int, int, result=str)
    async def verify_match_with_api(self, match_id: int, api_match_id: int) -> str:
        return await self._external.verify_match_with_api(match_id, api_match_id)

    @Slot(str, result=str)
    async def get_football_standings(self, competition_code: str) -> str:
        return await self._external.get_football_standings(competition_code)

    @Slot(str, result=str)
    async def get_football_competitions(self) -> str:
        return await self._external.get_football_competitions()

    @Slot(int, str, str, result=str)
    async def get_football_team_matches(self, api_team_id: int, date_from: str, date_to: str) -> str:
        return await self._external.get_football_team_matches(api_team_id, date_from, date_to)

    # ================================================================
    # External APIs — Bzzoiro
    # ================================================================

    @Slot(result=str)
    async def check_bzzoiro_status(self) -> str:
        return await self._external.check_bzzoiro_status()

    @Slot(str, result=str)
    async def search_bzzoiro_team(self, query: str) -> str:
        return await self._external.search_bzzoiro_team(query)

    @Slot(int, result=str)
    async def get_bzzoiro_team_squad(self, team_id: int) -> str:
        return await self._external.get_bzzoiro_team_squad(team_id)

    @Slot(int, int, str, result=str)
    async def import_bzzoiro_team_squad(self, match_id: int, team_id: int, side: str) -> str:
        return await self._external.import_bzzoiro_team_squad(match_id, team_id, side)

    @Slot(int, int, result=str)
    async def verify_match_bzzoiro(self, match_id: int, bzzoiro_event_id: int) -> str:
        return await self._external.verify_match_bzzoiro(match_id, bzzoiro_event_id)

    @Slot(int, result=str)
    async def get_bzzoiro_standings(self, league_id: int) -> str:
        return await self._external.get_bzzoiro_standings(league_id)

    @Slot(result=str)
    async def get_bzzoiro_leagues(self) -> str:
        return await self._external.get_bzzoiro_leagues()

    @Slot(int, str, str, result=str)
    async def get_bzzoiro_team_matches(self, team_id: int, date_from: str, date_to: str) -> str:
        return await self._external.get_bzzoiro_team_matches(team_id, date_from, date_to)

    @Slot(result=str)
    async def get_bzzoiro_live(self) -> str:
        return await self._external.get_bzzoiro_live()

    @Slot(int, result=str)
    async def get_bzzoiro_predictions(self, event_id: int) -> str:
        return await self._external.get_bzzoiro_predictions(event_id)

    @Slot(int, result=str)
    async def get_bzzoiro_match_stats(self, event_id: int) -> str:
        return await self._external.get_bzzoiro_match_stats(event_id)

    # ================================================================
    # External APIs — EasySoccerData
    # ================================================================

    @Slot(result=str)
    async def check_easy_soccer_status(self) -> str:
        return await self._external.check_easy_soccer_status()

    @Slot(result=str)
    async def get_easy_soccer_live(self) -> str:
        return await self._external.get_easy_soccer_live()

    @Slot(int, result=str)
    async def get_easy_soccer_event(self, event_id: int) -> str:
        return await self._external.get_easy_soccer_event(event_id)

    @Slot(int, result=str)
    async def get_easy_soccer_incidents(self, event_id: int) -> str:
        return await self._external.get_easy_soccer_incidents(event_id)

    @Slot(int, result=str)
    async def get_easy_soccer_player(self, player_id: int) -> str:
        return await self._external.get_easy_soccer_player(player_id)

    @Slot(str, result=str)
    async def search_easy_soccer_events(self, date: str) -> str:
        return await self._external.search_easy_soccer_events(date)

    # ================================================================
    # External APIs — API-Football
    # ================================================================

    @Slot(result=str)
    async def check_apifootball_status(self) -> str:
        return await self._external.check_apifootball_status()

    @Slot(str, result=str)
    async def search_apifootball_team(self, query: str) -> str:
        return await self._external.search_apifootball_team(query)

    @Slot(int, int, str, result=str)
    async def import_apifootball_squad(self, match_id: int, team_id: int, side: str) -> str:
        return await self._external.import_apifootball_squad(match_id, team_id, side)

    @Slot(int, int, result=str)
    async def get_apifootball_standings(self, league_id: int, season: int = 2024) -> str:
        return await self._external.get_apifootball_standings(league_id, season)

    @Slot(int, int, result=str)
    async def get_apifootball_fixtures(self, team_id: int, season: int) -> str:
        return await self._external.get_apifootball_fixtures(team_id, season)

    @Slot(int, result=str)
    async def get_apifootball_fixture_detail(self, fixture_id: int) -> str:
        return await self._external.get_apifootball_fixture_detail(fixture_id)

    @Slot(int, result=str)
    async def get_apifootball_predictions(self, fixture_id: int) -> str:
        return await self._external.get_apifootball_predictions(fixture_id)

    @Slot(result=str)
    async def get_apifootball_live(self) -> str:
        return await self._external.get_apifootball_live()

    @Slot(int, int, int, result=str)
    async def verify_match_apifootball(self, match_id: int, fixture_id: int) -> str:
        return await self._external.verify_match_apifootball(match_id, fixture_id)

    # ================================================================
    # External APIs — TheSportsDB
    # ================================================================

    @Slot(result=str)
    async def check_thesportsdb_status(self) -> str:
        return await self._external.check_thesportsdb_status()

    @Slot(str, result=str)
    async def search_thesportsdb_team(self, query: str) -> str:
        return await self._external.search_thesportsdb_team(query)

    @Slot(str, result=str)
    async def get_thesportsdb_standings(self, league_id: str) -> str:
        return await self._external.get_thesportsdb_standings(league_id)

    @Slot(str, result=str)
    async def get_thesportsdb_team_events_last(self, team_id: str) -> str:
        return await self._external.get_thesportsdb_team_events_last(team_id)

    @Slot(str, result=str)
    async def get_thesportsdb_team_events_next(self, team_id: str) -> str:
        return await self._external.get_thesportsdb_team_events_next(team_id)

    @Slot(str, str, result=str)
    async def get_thesportsdb_team_info(self, team_id: str) -> str:
        return await self._external.get_thesportsdb_team_info(team_id)

    # ================================================================
    # External APIs — StatsBomb
    # ================================================================

    @Slot(result=str)
    async def check_statsbomb_status(self) -> str:
        return await self._external.check_statsbomb_status()

    @Slot(result=str)
    async def get_statsbomb_competitions(self) -> str:
        return await self._external.get_statsbomb_competitions()

    @Slot(int, int, result=str)
    async def get_statsbomb_matches(self, competition_id: int, season_id: int) -> str:
        return await self._external.get_statsbomb_matches(competition_id, season_id)

    @Slot(int, result=str)
    async def get_statsbomb_events(self, match_id: int) -> str:
        return await self._external.get_statsbomb_events(match_id)

    @Slot(int, result=str)
    async def get_statsbomb_lineups(self, match_id: int) -> str:
        return await self._external.get_statsbomb_lineups(match_id)

    @Slot(str, result=str)
    async def search_statsbomb_team(self, team_name: str) -> str:
        return await self._external.search_statsbomb_team(team_name)

    @Slot(str, result=str)
    async def import_statsbomb_match(self, match_id: str) -> str:
        return await self._external.import_statsbomb_match(match_id)

    # ================================================================
    # External APIs — OpenFootball
    # ================================================================

    @Slot(result=str)
    async def check_openfootball_status(self) -> str:
        return await self._external.check_openfootball_status()

    @Slot(result=str)
    async def get_openfootball_competitions(self) -> str:
        return await self._external.get_openfootball_competitions()

    @Slot(str, str, result=str)
    async def get_openfootball_matches(self, competition_id: str, season: str) -> str:
        return await self._external.get_openfootball_matches(competition_id, season)

    @Slot(str, result=str)
    async def search_openfootball_team(self, team_name: str) -> str:
        return await self._external.search_openfootball_team(team_name)

    @Slot(int, result=str)
    async def get_openfootball_worldcup(self, year: int) -> str:
        return await self._external.get_openfootball_worldcup(year)

    # ================================================================
    # Roboflow Sports
    # ================================================================

    @Slot(result=str)
    async def check_roboflow_sports_status(self) -> str:
        return await self._analysis.check_roboflow_sports_status()

    @Slot(float, result=str)
    async def rf_draw_pitch(self, scale: float) -> str:
        return await self._analysis.rf_draw_pitch(scale)

    # ================================================================
    # Pose analysis
    # ================================================================

    @Slot(result=str)
    async def check_pose_status(self) -> str:
        return await self._analysis.check_pose_status()

    @Slot(int, result=str)
    async def get_activity_summary(self, track_id: int) -> str:
        return await self._analysis.get_activity_summary(track_id)

    @Slot(int, result=str)
    async def get_activity_segments(self, track_id: int) -> str:
        return await self._analysis.get_activity_segments(track_id)

    # ================================================================
    # MuJoCo ball trajectory
    # ================================================================

    @Slot(result=str)
    async def check_mujoco_status(self) -> str:
        return await self._analysis.check_mujoco_status()

    @Slot(result=str)
    async def get_setpiece_presets(self) -> str:
        return await self._analysis.get_setpiece_presets()

    @Slot(float, float, float, float, float, result=str)
    async def simulate_trajectory(self, initial_speed: float, launch_angle_deg: float, spin_rps: float, direction_deg: float, duration_s: float) -> str:
        return await self._analysis.simulate_trajectory(initial_speed, launch_angle_deg, spin_rps, direction_deg, duration_s)

    # ================================================================
    # FluidX3D
    # ================================================================

    @Slot(result=str)
    async def check_fluidx3d_status(self) -> str:
        return await self._analysis.check_fluidx3d_status()

    @Slot(float, float, float, result=str)
    async def simulate_ball_cfd(self, wind_speed: float, spin_rps: float, ball_radius: float) -> str:
        return await self._analysis.simulate_ball_cfd(wind_speed, spin_rps, ball_radius)

    # ================================================================
    # Weather
    # ================================================================

    @Slot(result=str)
    async def check_weather_status(self) -> str:
        return await self._analysis.check_weather_status()

    @Slot(float, float, str, bool, result=str)
    async def fetch_match_weather(self, latitude: float, longitude: float, date: str, is_forecast: bool) -> str:
        return await self._analysis.fetch_match_weather(latitude, longitude, date, is_forecast)

    @Slot(float, float, float, float, str, result=str)
    async def set_manual_weather(self, temperature: float, precipitation: float, wind: float, humidity: float, conditions: str) -> str:
        return await self._analysis.set_manual_weather(temperature, precipitation, wind, humidity, conditions)

    @Slot(float, float, float, float, str, result=str)
    async def analyze_weather_impact(self, temperature: float, precipitation: float, wind: float, humidity: float, conditions: str) -> str:
        return await self._analysis.analyze_weather_impact(temperature, precipitation, wind, humidity, conditions)

    @Slot(result=str)
    async def check_raindrop_status(self) -> str:
        return await self._analysis.check_raindrop_status()

    @Slot(result=str)
    async def check_weather_classifier_status(self) -> str:
        return await self._analysis.check_weather_classifier_status()

    @Slot(str, int, int, result=str)
    async def detect_raindrops_in_video(self, video_path: str, sample_every_n: int, max_frames: int) -> str:
        return await self._analysis.detect_raindrops_in_video(video_path, sample_every_n, max_frames)

    @Slot(str, result=str)
    async def classify_video_weather(self, video_path: str) -> str:
        return await self._analysis.classify_video_weather(video_path)

    # ================================================================
    # Psychology
    # ================================================================

    @Slot(result=str)
    async def check_psychology_status(self) -> str:
        return await self._analysis.check_psychology_status()

    @Slot(int, str, str, str, result=str)
    async def analyze_match_psychology(self, match_id: int, home_team: str, away_team: str, events_json: str) -> str:
        return await self._analysis.analyze_match_psychology(match_id, home_team, away_team, events_json)

    # ================================================================
    # Football Rules
    # ================================================================

    @Slot(result=str)
    async def check_rules_status(self) -> str:
        return await self._analysis.check_rules_status()

    @Slot(int, result=str)
    async def get_law_summary(self, law_number: int) -> str:
        return await self._analysis.get_law_summary(law_number)

    @Slot(result=str)
    async def get_all_laws(self) -> str:
        return await self._analysis.get_all_laws()

    @Slot(str, float, float, str, result=str)
    async def classify_event_rule(self, event_type: str, x: float, y: float, side: str) -> str:
        return await self._analysis.classify_event_rule(event_type, x, y, side)

    @Slot(float, float, float, str, result=str)
    async def check_offside(self, attacker_x: float, defender_x: float, ball_x: float, attacking_direction: str) -> str:
        return await self._analysis.check_offside(attacker_x, defender_x, ball_x, attacking_direction)

    # ================================================================
    # Card Detection
    # ================================================================

    @Slot(result=str)
    async def check_cards_status(self) -> str:
        return await self._analysis.check_cards_status()

    @Slot(str, result=str)
    async def infer_cards_tactically(self, events_json: str) -> str:
        return await self._analysis.infer_cards_tactically(events_json)

    @Slot(int, result=str)
    async def fetch_external_cards(self, match_id: int) -> str:
        return await self._analysis.fetch_external_cards(match_id)

    # ================================================================
    # Set-piece analysis
    # ================================================================

    @Slot(result=str)
    async def check_setpiece_status(self) -> str:
        return await self._analysis.check_setpiece_status()

    @Slot(str, str, result=str)
    async def analyze_setpieces(self, events_json: str, home_team: str) -> str:
        return await self._analysis.analyze_setpieces(events_json, home_team)

    # ================================================================
    # Goalkeeper
    # ================================================================

    @Slot(result=str)
    async def check_goalkeeper_status(self) -> str:
        return await self._analysis.check_goalkeeper_status()

    @Slot(str, str, str, bool, result=str)
    async def analyze_goalkeeper(self, team: str, actions_json: str, shots_json: str, clean_sheet: bool) -> str:
        return await self._analysis.analyze_goalkeeper(team, actions_json, shots_json, clean_sheet)

    @Slot(float, float, str, bool, result=str)
    async def compute_xgot(self, shot_x: float, shot_y: float, body_part: str, one_on_one: bool) -> str:
        return await self._analysis.compute_xgot(shot_x, shot_y, body_part, one_on_one)

    # ================================================================
    # Substitution
    # ================================================================

    @Slot(result=str)
    async def check_substitution_status(self) -> str:
        return await self._analysis.check_substitution_status()

    @Slot(str, str, str, result=str)
    async def analyze_substitutions(self, team: str, subs_json: str, events_json: str) -> str:
        return await self._analysis.analyze_substitutions(team, subs_json, events_json)

    # ================================================================
    # Possession
    # ================================================================

    @Slot(result=str)
    async def check_possession_status(self) -> str:
        return await self._analysis.check_possession_status()

    @Slot(str, str, str, result=str)
    async def analyze_possession(self, home_team: str, away_team: str, events_json: str) -> str:
        return await self._analysis.analyze_possession(home_team, away_team, events_json)

    # ================================================================
    # Realtime video
    # ================================================================

    @Slot(result=str)
    async def realtime_status(self) -> str:
        return await self._video.realtime_status()

    @Slot(result=str)
    async def realtime_cancel(self) -> str:
        return await self._video.realtime_cancel()

    @Slot(result=str)
    async def realtime_subscribe_console(self) -> str:
        return await self._video.realtime_subscribe_console()

    # ================================================================
    # Sprint 1 — Multi-Angle Sync, Trimming, Highlight Reel
    # ================================================================

    @Slot(str, result=str)
    async def sync_load(self, videos_json: str) -> str:
        return self._video.sync_load(videos_json)

    @Slot(int, float, result=str)
    async def sync_set_offset(self, source_index: int, offset_seconds: float) -> str:
        return self._video.sync_set_offset(source_index, offset_seconds)

    @Slot(float, result=str)
    async def sync_positions(self, master_time: float) -> str:
        return self._video.sync_positions(master_time)

    @Slot(result=str)
    async def sync_state(self) -> str:
        return self._video.sync_state()

    @Slot(result=str)
    async def sync_clear(self) -> str:
        return self._video.sync_clear()

    @Slot(str, float, float, str, result=str)
    async def trim_video(self, video_path: str, start_seconds: float, end_seconds: float, output_name: str = "") -> str:
        return self._video.trim_video(video_path, start_seconds, end_seconds, output_name)

    @Slot(str, str, result=str)
    async def reel_compose(self, clips_json: str, output_filename: str) -> str:
        return self._video.reel_compose(clips_json, output_filename)

    @Slot(int, str, str, result=str)
    async def reel_from_events(self, match_id: int, events_json: str, video_path: str) -> str:
        return self._video.reel_from_events(match_id, events_json, video_path)

    @Slot(str, result=str)
    async def reel_status(self, reel_id: str) -> str:
        return self._video.reel_status(reel_id)

    # ================================================================
    # Profiler / metrics (lifecycle)
    # ================================================================

    @Slot(result=str)
    async def profiler_status(self) -> str:
        return self._lifecycle.profiler_status()

    @Slot(result=str)
    async def profiler_reset(self) -> str:
        return self._lifecycle.profiler_reset()

    @Slot(result=str)
    async def metrics_text(self) -> str:
        return self._lifecycle.metrics_text()

    # ================================================================
    # Coding Workspace (Phase 1 — Video Tagging Engine)
    # ================================================================

    @Slot(int, str, result=str)
    async def save_coding_tag(self, match_id: int, tag_json: str) -> str:
        return await self._coding.save_tag(match_id, tag_json)

    @Slot(int, result=str)
    async def get_coding_tags(self, match_id: int) -> str:
        return await self._coding.get_tags(match_id)

    @Slot(int, str, result=str)
    async def update_coding_tag(self, tag_id: int, updates_json: str) -> str:
        return await self._coding.update_tag(tag_id, updates_json)

    @Slot(int, result=str)
    async def delete_coding_tag(self, tag_id: int) -> str:
        return await self._coding.delete_tag(tag_id)

    @Slot(int, result=str)
    async def get_coding_tag_stats(self, match_id: int) -> str:
        return await self._coding.get_tag_stats(match_id)

    @Slot(int, str, result=str)
    async def get_coding_tags_by_type(self, match_id: int, event_type: str) -> str:
        return await self._coding.get_tags_by_type(match_id, event_type)

    @Slot(int, int, result=str)
    async def get_coding_tags_by_player(self, match_id: int, player_track_id: int) -> str:
        return await self._coding.get_tags_by_player(match_id, player_track_id)

    @Slot(int, result=str)
    async def get_coding_players(self, match_id: int) -> str:
        return await self._coding.get_match_players_simple(match_id)

    @Slot(int, int, result=str)
    async def extract_tag_clip(self, match_id: int, tag_id: int) -> str:
        return await self._coding.extract_tag_clip(match_id, tag_id)

    @Slot(int, str, result=str)
    async def extract_tag_clips_batch(self, match_id: int, tag_ids_json: str) -> str:
        return await self._coding.extract_tag_clips_batch(match_id, tag_ids_json)

    @Slot(result=str)
    async def get_coding_templates(self) -> str:
        return await self._coding.get_default_tag_templates()

    # ================================================================
    # Phase 2.3 — Tactical Periods
    # ================================================================

    @Slot(int, result=str)
    async def get_tactical_periods(self, match_id: int) -> str:
        return await self._analysis.get_tactical_periods(match_id)

    # ================================================================
    # Phase 2.4 — Formation Analysis
    # ================================================================

    @Slot(int, result=str)
    async def analyze_formation(self, match_id: int) -> str:
        return await self._analysis.analyze_formation(match_id)

    # ================================================================
    # Tactical Shape Analysis
    # ================================================================

    @Slot(int, result=str)
    async def analyze_tactical_shapes(self, match_id: int) -> str:
        return await self._analysis.analyze_tactical_shapes(match_id)

    # ================================================================
    # Pressing Classification
    # ================================================================

    @Slot(int, result=str)
    async def classify_pressing(self, match_id: int) -> str:
        return await self._analysis.classify_pressing(match_id)

    # ================================================================
    # Comprehensive Tactical Report
    # ================================================================

    @Slot(int, result=str)
    async def get_tactical_report(self, match_id: int) -> str:
        return await self._analysis.get_tactical_report(match_id)

    # ================================================================
    # Phase 3 — AI NL Query
    # ================================================================

    @Slot(int, str, result=str)
    async def ask_llm(self, match_id: int, question: str) -> str:
        return await self._analysis.ask_llm(match_id, question)

    # ================================================================
    # Phase 4 — Player Rating & Squad
    # ================================================================

    # ================================================================
    # Wave B — Season Dashboard
    # ================================================================

    @Slot(result=str)
    async def get_season_summary(self) -> str:
        return await self._analysis.get_season_summary()

    # ================================================================
    # Wave C — Training Drills
    # ================================================================

    @Slot(result=str)
    async def get_all_drills(self) -> str:
        return await self._analysis.get_all_drills()

    # ================================================================
    # Sprint 5 — Data Quality Score
    # ================================================================

    @Slot(str, result=str)
    async def get_match_quality_score(self, match_id: str) -> str:
        return await self._analysis.get_match_quality_score(match_id)

    # ================================================================
    # Wave E — Scout Portal
    # ================================================================

    @Slot(str, str, result=str)
    async def scout_search_players(self, query: str, position: str = "") -> str:
        return await self._analysis.scout_search_players(query, position)

    @Slot(result=str)
    async def get_shortlist(self) -> str:
        return await self._analysis.get_shortlist()

    @Slot(int, int, result=str)
    async def generate_scout_report(self, track_id: int, match_id: int = 0) -> str:
        return await self._analysis.generate_scout_report_pdf(track_id, match_id)

    @Slot(int, int, result=str)
    async def get_player_rating(self, match_id: int, track_id: int) -> str:
        return await self._analysis.get_player_rating(match_id, track_id)

    @Slot(int, result=str)
    async def get_squad_summary(self, match_id: int) -> str:
        return await self._analysis.get_squad_summary(match_id)

    # ================================================================
    # Phase 6 Sprint 1 — Injury Risk
    # ================================================================

    @Slot(str, str, result=str)
    async def get_injury_risk(self, match_id: str, track_id: str) -> str:
        return await self._analysis.get_injury_risk(match_id, track_id)

    @Slot(str, result=str)
    async def get_squad_injury_report(self, match_id: str) -> str:
        return await self._analysis.get_squad_injury_report(match_id)

    # ================================================================
    # Phase 6 Sprint 1 — Training Plan Auto-Generate
    # ================================================================

    @Slot(str, result=str)
    async def generate_training_plan(self, match_id: str) -> str:
        return await self._analysis.generate_training_plan(match_id)

    # ================================================================
    # Sprint 3 — Collaboration
    # ================================================================

    @Slot(str, str, str, result=str)
    async def create_collab_user(self, username: str, display_name: str, role: str = "analyst") -> str:
        return await self._analysis.create_collab_user(username, display_name, role)

    @Slot(result=str)
    async def get_collab_users(self) -> str:
        return await self._analysis.get_collab_users()

    @Slot(int, result=str)
    async def delete_collab_user(self, user_id: int) -> str:
        return await self._analysis.delete_collab_user(user_id)

    @Slot(int, int, int, str, result=str)
    async def add_comment(self, match_id: int, event_id: int, user_id: int, text: str) -> str:
        return await self._analysis.add_comment(match_id, event_id, user_id, text)

    @Slot(int, int, result=str)
    async def get_comments(self, match_id: int, event_id: int = 0) -> str:
        return await self._analysis.get_comments(match_id, event_id)

    @Slot(int, result=str)
    async def delete_comment(self, comment_id: int) -> str:
        return await self._analysis.delete_comment(comment_id)

    @Slot(int, result=str)
    async def export_project(self, match_id: int) -> str:
        return await self._analysis.export_project(match_id)

    @Slot(str, result=str)
    async def import_project(self, project_json: str) -> str:
        return await self._analysis.import_project(project_json)

    @Slot(int, result=str)
    async def get_activity_feed(self, limit: int = 50) -> str:
        return await self._analysis.get_activity_feed(limit)

    @Slot(int, int, result=str)
    async def get_event_comments(self, match_id: int, event_id: int) -> str:
        return await self._analysis.get_event_comments(match_id, event_id)

    @Slot(str, result=str)
    async def get_mentions(self, username: str) -> str:
        return await self._analysis.get_mentions(username)

    @Slot(int, result=str)
    async def mark_mention_read(self, mention_id: int) -> str:
        return await self._analysis.mark_mention_read(mention_id)

    # ================================================================
    # Sprint 4 — Live Tagging
    # ================================================================

    @Slot(str, str, result=str)
    async def live_start_session(self, home_team: str = "Home", away_team: str = "Away") -> str:
        return await self._analysis.live_start_session(home_team, away_team)

    @Slot(result=str)
    async def live_stop_session(self) -> str:
        return await self._analysis.live_stop_session()

    @Slot(str, str, int, str, float, float, result=str)
    async def live_tag_event(self, event_type: str, team: str = "", player_id: int = 0, notes: str = "", x: float = None, y: float = None) -> str:
        return await self._analysis.live_tag_event(event_type, team, player_id, notes, x, y)

    @Slot(int, result=str)
    async def live_set_period(self, period: int) -> str:
        return await self._analysis.live_set_period(period)

    @Slot(result=str)
    async def live_get_stats(self) -> str:
        return await self._analysis.live_get_stats()

    @Slot(result=str)
    async def live_get_tags(self) -> str:
        return await self._analysis.live_get_tags()

    @Slot(result=str)
    async def live_clear_tags(self) -> str:
        return await self._analysis.live_clear_tags()

    @Slot(result=str)
    async def live_get_hotkeys(self) -> str:
        return await self._analysis.live_get_hotkeys()

    @Slot(result=str)
    async def live_export(self) -> str:
        return await self._analysis.live_export()

    # ── Phase 6 Sprint 2 — Live Tagging Dashboard ───────────────────

    @Slot(str, result=str)
    async def get_live_kpis(self, session_id: str) -> str:
        return await self._analysis.get_live_kpis(session_id)

    @Slot(str, result=str)
    async def get_live_pitch_map(self, session_id: str) -> str:
        return await self._analysis.get_live_pitch_map(session_id)

    @Slot(str, result=str)
    async def get_live_xg_chart(self, session_id: str) -> str:
        return await self._analysis.get_live_xg_chart(session_id)

    # ================================================================
    # Sprint 6 — Auto-Updater
    # ================================================================

    @Slot(result=str)
    async def updater_check(self) -> str:
        return await self._analysis.updater_check()

    @Slot(str, result=str)
    async def updater_download(self, url: str) -> str:
        return await self._analysis.updater_download(url)

    @Slot(str, result=str)
    async def updater_apply(self, path: str) -> str:
        return await self._analysis.updater_apply(path)

    @Slot(result=str)
    async def updater_version(self) -> str:
        return await self._analysis.updater_version()

    # ================================================================
    # Sprint 7 — Sample Data & App Info
    # ================================================================

    @Slot(result=str)
    async def load_sample_data(self) -> str:
        return await self._analysis.load_sample_data()

    @Slot(result=str)
    async def get_app_info(self) -> str:
        return await self._analysis.get_app_info()

    # ================================================================
    # Phase 10 — Telestration v2
    # ================================================================

    @Slot(str, str, result=str)
    async def tel_layer_add(self, layer_id: str, name: str = "") -> str:
        return await self._analysis.tel_layer_add(layer_id, name)

    @Slot(str, result=str)
    async def tel_layer_remove(self, layer_id: str) -> str:
        return await self._analysis.tel_layer_remove(layer_id)

    @Slot(str, result=str)
    async def tel_layer_toggle(self, layer_id: str) -> str:
        return await self._analysis.tel_layer_toggle(layer_id)

    @Slot(str, float, result=str)
    async def tel_layer_opacity(self, layer_id: str, opacity: float) -> str:
        return await self._analysis.tel_layer_opacity(layer_id, opacity)

    @Slot(result=str)
    async def tel_get_layers(self) -> str:
        return await self._analysis.tel_get_layers()

    @Slot(str, str, result=str)
    async def tel_save_preset(self, name: str, layers_json: str) -> str:
        return await self._analysis.tel_save_preset(name, layers_json)

    @Slot(str, result=str)
    async def tel_load_preset(self, name: str) -> str:
        return await self._analysis.tel_load_preset(name)

    @Slot(result=str)
    async def tel_list_presets(self) -> str:
        return await self._analysis.tel_list_presets()

    @Slot(str, result=str)
    async def tel_delete_preset(self, name: str) -> str:
        return await self._analysis.tel_delete_preset(name)

    @Slot(str, str, str, result=str)
    async def tel_export_video(self, video_path: str, layers_json: str, output_path: str = "") -> str:
        return await self._analysis.tel_export_video(video_path, layers_json, output_path)

    # ================================================================
    # Phase 9 — Live Stream Capture
    # ================================================================

    @Slot(str, str, str, result=str)
    async def stream_start_capture(self, url: str, stream_id: str = "", output_filename: str = "") -> str:
        return await self._analysis.stream_start_capture(url, stream_id, output_filename)

    @Slot(str, result=str)
    async def stream_stop_capture(self, stream_id: str) -> str:
        return await self._analysis.stream_stop_capture(stream_id)

    @Slot(str, result=str)
    async def stream_get_status(self, stream_id: str) -> str:
        return await self._analysis.stream_get_status(stream_id)

    @Slot(result=str)
    async def stream_list(self) -> str:
        return await self._analysis.stream_list()

    @Slot(str, str, result=str)
    async def stream_add_marker(self, stream_id: str, label: str = "") -> str:
        return await self._analysis.stream_add_marker(stream_id, label)

    @Slot(result=str)
    async def stream_list_recordings(self) -> str:
        return await self._analysis.stream_list_recordings()

    @Slot(str, result=str)
    async def stream_detect_source(self, url: str) -> str:
        return await self._analysis.stream_detect_source(url)

    # ================================================================
    # Phase 12 — AI Coach Assistant v2
    # ================================================================

    @Slot(str, str, result=str)
    async def ai_v2_create_conv(self, match_id: str = "", title: str = "New Chat") -> str:
        return await self._analysis.ai_v2_create_conv(match_id, title)

    @Slot(str, result=str)
    async def ai_v2_list_convs(self, match_id: str = "") -> str:
        return await self._analysis.ai_v2_list_convs(match_id)

    @Slot(str, result=str)
    async def ai_v2_delete_conv(self, conv_id: str) -> str:
        return await self._analysis.ai_v2_delete_conv(conv_id)

    @Slot(str, str, str, str, result=str)
    async def ai_v2_ask(self, conv_id: str, question: str, match_context: str = "", language: str = "en") -> str:
        return await self._analysis.ai_v2_ask(conv_id, question, match_context, language)

    @Slot(str, str, str, result=str)
    async def ai_v2_tactical_suggestion(self, topic: str, match_context: str = "", language: str = "en") -> str:
        return await self._analysis.ai_v2_tactical_suggestion(topic, match_context, language)

    @Slot(str, str, result=str)
    async def ai_v2_auto_report(self, match_id: str, language: str = "en") -> str:
        return await self._analysis.ai_v2_auto_report(match_id, language)

    # ================================================================
    # Phase 13 — Opponent Database + Scouting Network + Transfermarkt
    # ================================================================

    @Slot(result=str)
    async def opponent_list(self) -> str:
        return await self._analysis.opponent_list()

    @Slot(str, result=str)
    async def opponent_get(self, profile_id: str) -> str:
        return await self._analysis.opponent_get(profile_id)

    @Slot(str, str, str, result=str)
    async def opponent_create(self, team_name: str, league: str = "", country: str = "") -> str:
        return await self._analysis.opponent_create(team_name, league, country)

    @Slot(str, str, result=str)
    async def opponent_update(self, profile_id: str, updates_json: str) -> str:
        return await self._analysis.opponent_update(profile_id, updates_json)

    @Slot(str, result=str)
    async def opponent_delete(self, profile_id: str) -> str:
        return await self._analysis.opponent_delete(profile_id)

    @Slot(str, str, str, str, str, str, str, str, str, result=str)
    async def opponent_add_matchup(self, profile_id: str, our_team: str, date: str, competition: str = "", home_away: str = "home", our_score: str = "0", their_score: str = "0", our_xg: str = "0.0", their_xg: str = "0.0", notes: str = "") -> str:
        return await self._analysis.opponent_add_matchup(profile_id, our_team, date, competition, home_away, our_score, their_score, our_xg, their_xg, notes)

    @Slot(str, result=str)
    async def opponent_scouting_report(self, profile_id: str) -> str:
        return await self._analysis.opponent_scouting_report(profile_id)

    @Slot(str, str, str, str, str, str, result=str)
    async def scout_network_search(self, query: str = "", position: str = "", min_age: str = "0", max_age: str = "99", league: str = "", min_rating: str = "0.0") -> str:
        return await self._analysis.scout_network_search(query, position, min_age, max_age, league, min_rating)

    @Slot(str, str, str, str, str, str, str, str, str, str, result=str)
    async def scout_network_add(self, name: str, position: str = "", club: str = "", league: str = "", rating: str = "0.0", strengths_json: str = "[]", weaknesses_json: str = "[]", scout_notes: str = "", submitted_by: str = "", tags_json: str = "[]") -> str:
        return await self._analysis.scout_network_add(name, position, club, league, rating, strengths_json, weaknesses_json, scout_notes, submitted_by, tags_json)

    @Slot(str, result=str)
    async def scout_network_get(self, player_id: str) -> str:
        return await self._analysis.scout_network_get(player_id)

    @Slot(str, result=str)
    async def scout_network_delete(self, player_id: str) -> str:
        return await self._analysis.scout_network_delete(player_id)

    @Slot(result=str)
    async def scout_network_stats(self) -> str:
        return await self._analysis.scout_network_stats()

    @Slot(str, result=str)
    async def transfermarkt_search(self, name: str) -> str:
        return await self._analysis.transfermarkt_search(name)

    @Slot(str, result=str)
    async def transfermarkt_get(self, player_id: str) -> str:
        return await self._analysis.transfermarkt_get(player_id)

    @Slot(str, result=str)
    async def transfermarkt_squad(self, club_name: str) -> str:
        return await self._analysis.transfermarkt_squad(club_name)

    # ================================================================
    # Phase 15 — Community Marketplace
    # ================================================================

    @Slot(str, str, str, str, result=str)
    async def marketplace_list(self, item_type: str = "", category: str = "", query: str = "", source: str = "") -> str:
        return await self._analysis.marketplace_list(item_type, category, query, source)

    @Slot(str, result=str)
    async def marketplace_get(self, item_id: str) -> str:
        return await self._analysis.marketplace_get(item_id)

    @Slot(str, str, str, str, str, str, str, str, result=str)
    async def marketplace_add(self, item_type: str, name: str, description: str = "", author: str = "", category: str = "", tags_json: str = "[]", data: str = "", source: str = "local") -> str:
        return await self._analysis.marketplace_add(item_type, name, description, author, category, tags_json, data, source)

    @Slot(str, str, result=str)
    async def marketplace_rate(self, item_id: str, rating: str) -> str:
        return await self._analysis.marketplace_rate(item_id, rating)

    @Slot(str, result=str)
    async def marketplace_delete(self, item_id: str) -> str:
        return await self._analysis.marketplace_delete(item_id)

    @Slot(result=str)
    async def marketplace_stats(self) -> str:
        return await self._analysis.marketplace_stats()

    @Slot(str, result=str)
    async def marketplace_categories(self, item_type: str = "") -> str:
        return await self._analysis.marketplace_categories(item_type)

    # ================================================================
    # Phase 8 — Cloud Sync
    # ================================================================

    @Slot(result=str)
    async def cloud_check_health(self) -> str:
        return await self._analysis.cloud_check_health()

    @Slot(str, str, str, result=str)
    async def cloud_register(self, username: str, email: str, password: str, display_name: str = "") -> str:
        return await self._analysis.cloud_register(username, email, password, display_name)

    @Slot(str, str, result=str)
    async def cloud_login(self, email: str, password: str) -> str:
        return await self._analysis.cloud_login(email, password)

    @Slot(result=str)
    async def cloud_logout(self) -> str:
        return await self._analysis.cloud_logout()

    @Slot(result=str)
    async def cloud_get_me(self) -> str:
        return await self._analysis.cloud_get_me()

    @Slot(result=str)
    async def cloud_is_logged_in(self) -> str:
        return await self._analysis.cloud_is_logged_in()

    @Slot(str, str, result=str)
    async def cloud_create_team(self, name: str, description: str = "") -> str:
        return await self._analysis.cloud_create_team(name, description)

    @Slot(result=str)
    async def cloud_list_teams(self) -> str:
        return await self._analysis.cloud_list_teams()

    @Slot(int, str, result=str)
    async def cloud_invite_member(self, team_id: int, email: str) -> str:
        return await self._analysis.cloud_invite_member(team_id, email)

    @Slot(str, result=str)
    async def cloud_accept_invite(self, token: str) -> str:
        return await self._analysis.cloud_accept_invite(token)

    @Slot(str, str, result=str)
    async def cloud_sync_push(self, device_id: str, operations_json: str) -> str:
        return await self._analysis.cloud_sync_push(device_id, operations_json)

    @Slot(str, result=str)
    async def cloud_sync_pull(self, device_id: str) -> str:
        return await self._analysis.cloud_sync_pull(device_id)

    @Slot(int, result=str)
    async def cloud_start_server(self, port: int = 8741) -> str:
        return await self._analysis.cloud_start_server(port)

    @Slot(result=str)
    async def cloud_server_status(self) -> str:
        return await self._analysis.cloud_server_status()

    # ================================================================
    # Sprint 2 — Wearable Import, Physiological Merge, Tactical Correlation
    # ================================================================

    @Slot(str, result=str)
    async def import_wearable(self, file_path: str) -> str:
        return await self._analysis.import_wearable(file_path)

    @Slot(int, str, str, float, result=str)
    async def merge_player_physiology(self, player_id: int, trajectory_json: str, wearable_json: str, body_mass_kg: float = 75.0) -> str:
        return await self._analysis.merge_player_physiology(player_id, trajectory_json, wearable_json, body_mass_kg)

    @Slot(str, str, str, float, result=str)
    async def analyze_physio_tactical(self, events_json: str, speed_timeline_json: str, hr_timeline_json: str = "", window_s: float = 5.0) -> str:
        return await self._analysis.analyze_physio_tactical(events_json, speed_timeline_json, hr_timeline_json if hr_timeline_json else None, window_s)

    # ================================================================
    # P0-B2: YOLO variant control
    # ================================================================

    @Slot(result=str)
    async def get_recommended_yolo_variant(self) -> str:
        return await self._analysis.get_recommended_yolo_variant()

    @Slot(result=str)
    async def get_current_yolo_variant(self) -> str:
        return await self._analysis.get_current_yolo_variant()

    @Slot(str, result=str)
    async def set_yolo_variant(self, variant: str) -> str:
        return await self._analysis.set_yolo_variant(variant)

    @Slot(result=str)
    async def get_gpu_tier(self) -> str:
        return await self._analysis.get_gpu_tier()

    # ================================================================
    # Sprint 2 — Advanced Visualizations
    # ================================================================

    @Slot(str, result=str)
    def get_pitch_control_overlay(self, match_id: str) -> str:
        return self._analysis.get_pitch_control_overlay(match_id)

    @Slot(str, str, result=str)
    def get_player_pass_sonar(self, match_id: str, track_id: str) -> str:
        return self._analysis.get_player_pass_sonar(match_id, track_id)

    @Slot(str, result=str)
    def get_space_control_heatmap(self, match_id: str) -> str:
        return self._analysis.get_space_control_heatmap(match_id)

    @Slot(str, str, result=str)
    def get_player_role(self, match_id: str, track_id: str) -> str:
        return self._analysis.get_player_role(match_id, track_id)

    @Slot(str, result=str)
    def get_dominance_index(self, match_id: str) -> str:
        return self._analysis.get_dominance_index(match_id)

    # ================================================================
    # Sprint 12+ — Advanced Analysis Bridge Methods
    # ================================================================

    @Slot(int, result=str)
    async def compute_goals_added(self, match_id: int) -> str:
        return self._analysis.compute_goals_added(match_id)

    @Slot(int, result=str)
    async def analyze_finishing(self, match_id: int) -> str:
        return self._analysis.analyze_finishing(match_id)

    @Slot(int, int, result=str)
    async def simulate_league(self, match_id: int, iterations: int = 10000) -> str:
        return self._analysis.simulate_league(match_id, iterations)

    @Slot(int, int, result=str)
    async def estimate_transfer_fee(self, match_id: int, track_id: int) -> str:
        return self._analysis.estimate_transfer_fee(match_id, track_id)

    @Slot(int, result=str)
    async def generate_match_report(self, match_id: int) -> str:
        return self._analysis.generate_match_report(match_id)

    @Slot(int, int, result=str)
    async def generate_game_plan(self, match_id: int, opponent_id: int) -> str:
        return self._analysis.generate_game_plan(match_id, opponent_id)

    @Slot(int, result=str)
    async def compute_phase_xg(self, match_id: int) -> str:
        return self._analysis.compute_phase_xg(match_id)

    @Slot(int, result=str)
    async def analyze_build_up(self, match_id: int) -> str:
        return self._analysis.analyze_build_up(match_id)

    @Slot(int, result=str)
    async def compute_territory_value(self, match_id: int) -> str:
        return self._analysis.compute_territory_value(match_id)
