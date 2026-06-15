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
    AudioService,
    AnalysisService,
    CVService,
    EnhancementService,
    KnowledgeService,
    LLMConfig,
    LLMService,
    StorageService,
)
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

        self.cv = CVService(
            model_size=self.settings.model_size,
            confidence_threshold=self.settings.confidence_threshold,
            iou_threshold=self.settings.iou_threshold,
            gpu_enabled=self.settings.gpu_enabled,
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
