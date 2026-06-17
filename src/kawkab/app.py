"""Main application window - PySide6 + QWebEngineView + QWebChannel."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from PySide6.QtWebChannel import QWebChannel

from kawkab.core.config import get_settings
from kawkab.core.logging import get_logger, setup_logging
from kawkab.core.paths import get_paths
from kawkab.services import (
    AdvancedEventDetectionService,
    AnomalyDetectionService,
    ApiFootballService,
    AudioService,
    AnalysisService,
    BenchmarkService,
    BzzoiroService,
    ClipExtractionService,
    CVService,
    DataExportService,
    EasySoccerService,
    EnhancementService,
    FaceRecognitionService,
    FeedbackService,
    FluidX3DService,
    FootballDataService,
    FootballRulesService,
    HomographyService,
    KnowledgeService,
    LightGlueHomographyService,
    LLMConfig,
    LLMService,
    MultiMatchAnalysisService,
    MuJoCoBallService,
    OpenFootballDataService,
    PhysicalLoadService,
    PlayerProfileService,
    PoseAnalysisService,
    PossessionService,
    PressureMetricsService,
    PsychologyService,
    QualityScoringService,
    RealtimeService,
    RoboflowSportsService,
    SetPieceService,
    GoalkeeperService,
    StatsBombService,
    StorageService,
    SubstitutionService,
    TheSportsDBService,
    VisualizationService,
    WeatherService,
    CardDetectionService,
)
from kawkab.core.model_manager import ModelManager
from kawkab.ui.bridge import Bridge

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.paths = get_paths()

        self.setWindowTitle(f"{self.settings.app_name} v{self.settings.app_version}")
        self.setMinimumSize(QSize(1280, 800))

        self._init_services()
        self._init_ui()
        self._init_system_tray()
        self._init_bridge()

        logger.info(f"MainWindow initialized: {self.windowTitle()}")

    def _init_services(self) -> None:
        """Initialize all backend services."""
        logger.info("Initializing services...")

        self.storage = StorageService()

        self.model_manager = ModelManager()

        self.cv = CVService(
            model_size=self.settings.model_size,
            confidence_threshold=self.settings.confidence_threshold,
            iou_threshold=self.settings.iou_threshold,
            gpu_enabled=self.settings.gpu_enabled,
            model_manager=self.model_manager,
        )

        self.enhancement = EnhancementService(
            enable_stabilization=True,
            enable_denoising=True,
            enable_sharpening=True,
            enable_upscaling=self.settings.enable_upscaling,
            enable_interpolation=self.settings.enable_interpolation,
            gpu_enabled=self.settings.gpu_enabled,
        )

        self.analysis = AnalysisService()

        self.player_profiles = PlayerProfileService()
        self.multi_match = MultiMatchAnalysisService()
        self.data_export = DataExportService()
        self.visualization = VisualizationService()
        self.anomaly_detection = AnomalyDetectionService()
        self.quality_scoring = QualityScoringService()

        self.advanced_events = AdvancedEventDetectionService()
        self.physical_load = PhysicalLoadService()
        self.pressure_metrics = PressureMetricsService()
        self.benchmark = BenchmarkService()
        self.feedback = FeedbackService(storage_service=self.storage)
        self.clip_extraction = ClipExtractionService(cache_dir=self.paths.exports)
        self.face_recognition = FaceRecognitionService()

        self.football_data = FootballDataService(
            api_key=self.settings.football_data_api_key,
        )
        self.bzzoiro = BzzoiroService(
            api_key=self.settings.bzzoiro_api_key,
        )
        self.easy_soccer = EasySoccerService()
        self.api_football = ApiFootballService(
            api_key=self.settings.apifootball_api_key,
        )
        self.thesportsdb = TheSportsDBService(
            api_key=self.settings.thesportsdb_api_key,
        )
        self.statsbomb = StatsBombService()
        self.openfootball = OpenFootballDataService()
        self.roboflow_sports = RoboflowSportsService()
        self.pose_analysis = PoseAnalysisService(
            model_size=self.settings.pose_model_size,
        )
        self.mujoco_ball = MuJoCoBallService()
        self.fluidx3d = FluidX3DService()
        self.weather = WeatherService()
        self.psychology = PsychologyService()
        self.football_rules = FootballRulesService()
        self.card_detection = CardDetectionService()
        self.setpiece = SetPieceService()
        self.goalkeeper = GoalkeeperService()
        self.substitution = SubstitutionService()
        self.possession = PossessionService()
        self.realtime = RealtimeService(cv_service=self.cv)

        # Auto-detect GPU tier and apply recommended settings
        if self.settings.auto_detect_gpu_tier:
            self._apply_gpu_tier_settings()

        llm_config = LLMConfig(
            provider=self.settings.llm_provider,
            ollama_model=self.settings.ollama_model,
            ollama_base_url=self.settings.ollama_base_url,
        )
        self.llm = LLMService(llm_config)

        self.knowledge = KnowledgeService()

        self.audio = AudioService(
            enable_transcription=True,
            enable_whistle_detection=True,
            gpu_enabled=self.settings.gpu_enabled,
        )

        self.homography = HomographyService()
        self.lightglue_homography = LightGlueHomographyService()

    def _apply_gpu_tier_settings(self) -> None:
        """Detect GPU and apply recommended settings."""
        try:
            from kawkab.services.benchmark_service import BenchmarkService
            gpu_name = self.benchmark._system_info.get("gpu_name", "unknown")
            if gpu_name == "unknown":
                logger.info("GPU detection: no GPU found, using default settings")
                return

            tier = BenchmarkService.classify_gpu_tier(gpu_name)
            recommendations = BenchmarkService.recommend_settings(tier)

            logger.info(f"GPU detected: {gpu_name} (tier: {tier})")
            logger.info(f"Recommended settings: {recommendations}")

            # Apply recommendations if different from current
            if recommendations["model_size"] != self.settings.model_size:
                self.settings.model_size = recommendations["model_size"]
                logger.info(f"Auto-set model_size to {recommendations['model_size']}")

            if recommendations["frame_skip"] != self.settings.frame_skip:
                self.settings.frame_skip = recommendations["frame_skip"]
                logger.info(f"Auto-set frame_skip to {recommendations['frame_skip']}")

            if not recommendations["gpu_enabled"] and self.settings.gpu_enabled:
                self.settings.gpu_enabled = False
                logger.info("Auto-disabled GPU (no CUDA detected)")

        except Exception as e:
            logger.warning(f"GPU tier detection failed: {e}")

    def _init_ui(self) -> None:
        """Initialize the web view UI."""
        self.web_view = QWebEngineView(self)
        self.setCentralWidget(self.web_view)

        page = self.web_view.page()
        if hasattr(page, "settings"):
            page.settings().setAttribute(
                QWebEngineSettings.LocalContentCanAccessFileUrls, True
            )
            page.settings().setAttribute(
                QWebEngineSettings.LocalContentCanAccessRemoteUrls, True
            )

        possible_paths = [
            Path(__file__).parent / "web" / "index.html",
            Path(__file__).parent.parent / "web" / "index.html",
            Path(__file__).parent / ".." / "web" / "index.html",
            Path.cwd() / "src" / "kawkab" / "web" / "index.html",
        ]
        index_path = None
        for path in possible_paths:
            if path.exists():
                index_path = path.resolve()
                break

        if index_path is None:
            logger.error(f"index.html not found in any of: {[str(p) for p in possible_paths]}")
            self.web_view.setHtml(
                "<h1>Kawkab AI</h1><p>Frontend not found. "
                "Reinstall the application or check installation integrity.</p>"
            )
            return

        logger.info(f"Loading UI from: {index_path}")

        self._index_url = QUrl.fromLocalFile(str(index_path))
        self.web_view.loadFinished.connect(self._on_page_loaded)
        self.web_view.setUrl(self._index_url)

    def _on_page_loaded(self, ok: bool) -> None:
        """Set up QWebChannel AFTER the page has loaded."""
        if ok:
            logger.info("Page loaded, setting up QWebChannel")
            try:
                self.channel = QWebChannel()
                self.channel.registerObject("kawkab", self.bridge)
                self.web_view.page().setWebChannel(self.channel)
                logger.info("QWebChannel set up successfully")
            except Exception as e:
                logger.error(f"Failed to set up QWebChannel: {e}")
        else:
            logger.error("Page failed to load")

    def _init_system_tray(self) -> None:
        """Initialize system tray icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.info("System tray not available")
            return

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon())
        self.tray_icon.setToolTip(self.settings.app_name)

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self.show)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)
        self.tray_icon.setContextMenu(tray_menu)

        self.tray_icon.show()

    def _init_bridge(self) -> None:
        """Initialize the QWebChannel bridge (will be attached to page after load)."""
        self.bridge = Bridge(
            cv_service=self.cv,
            enhancement_service=self.enhancement,
            analysis_service=self.analysis,
            llm_service=self.llm,
            knowledge_service=self.knowledge,
            storage_service=self.storage,
            audio_service=self.audio,
            homography_service=self.homography,
            lightglue_homography_service=self.lightglue_homography,
            player_profile_service=self.player_profiles,
            multi_match_service=self.multi_match,
            data_export_service=self.data_export,
            visualization_service=self.visualization,
            anomaly_detection_service=self.anomaly_detection,
            quality_scoring_service=self.quality_scoring,
            advanced_event_detection_service=self.advanced_events,
            physical_load_service=self.physical_load,
            pressure_metrics_service=self.pressure_metrics,
            benchmark_service=self.benchmark,
            feedback_service=self.feedback,
            clip_service=self.clip_extraction,
            football_data_service=self.football_data,
            bzzoiro_service=self.bzzoiro,
            easy_soccer_service=self.easy_soccer,
            api_football_service=self.api_football,
            thesportsdb_service=self.thesportsdb,
            statsbomb_service=self.statsbomb,
            openfootball_service=self.openfootball,
            roboflow_sports_service=self.roboflow_sports,
            pose_analysis_service=self.pose_analysis,
            mujoco_ball_service=self.mujoco_ball,
            fluidx3d_service=self.fluidx3d,
            weather_service=self.weather,
            psychology_service=self.psychology,
            football_rules_service=self.football_rules,
            card_detection_service=self.card_detection,
            setpiece_service=self.setpiece,
            goalkeeper_service=self.goalkeeper,
            substitution_service=self.substitution,
            possession_service=self.possession,
            realtime_service=self.realtime,
            frame_skip=self.settings.frame_skip,
            parent=self,
        )

    def closeEvent(self, event) -> None:
        """Handle window close - minimize to tray."""
        if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                self.settings.app_name,
                "Still running in system tray. Right-click to quit.",
                QSystemTrayIcon.Information,
                2000,
            )
            self.hide()
            event.ignore()
        else:
            event.accept()

    async def shutdown(self) -> None:
        """Graceful shutdown of all services."""
        logger.info("Shutting down services...")
        await self.cv.shutdown()
        await self.storage.close()
        logger.info("Shutdown complete")


def run_app() -> int:
    """Launch the Kawkab AI desktop application.

    Returns:
        Exit code (0 for success)
    """
    settings = get_settings()
    setup_logging(debug=settings.debug)

    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"GPU enabled: {settings.gpu_enabled}")
    logger.info(f"Model size: {settings.model_size}")
    logger.info(f"LLM provider: {settings.llm_provider}")

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    app.setApplicationVersion(settings.app_version)
    app.setOrganizationName("KawkabAI")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(run_app())
