"""Windows-aware path management for Kawkab AI."""

from __future__ import annotations

import os
import platform
from pathlib import Path


def _get_appdata_dir() -> Path:
    """Get the platform-specific app data directory."""
    system = platform.system().lower()

    if system == "windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "KawkabAI"
        return Path.home() / "AppData" / "Roaming" / "KawkabAI"

    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "KawkabAI"

    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "kawkab-ai"
    return Path.home() / ".local" / "share" / "kawkab-ai"


def _get_localappdata_dir() -> Path:
    """Get the platform-specific local app data directory (cache/temp)."""
    system = platform.system().lower()

    if system == "windows":
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            return Path(localappdata) / "KawkabAI"
        return Path.home() / "AppData" / "Local" / "KawkabAI"

    if system == "darwin":
        return Path.home() / "Library" / "Caches" / "KawkabAI"

    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "kawkab-ai"
    return Path.home() / ".cache" / "kawkab-ai"


def _get_documents_dir() -> Path:
    """Get the user's documents directory."""
    system = platform.system().lower()

    if system == "windows":
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            return Path(userprofile) / "Documents" / "KawkabAI"
        return Path.home() / "Documents" / "KawkabAI"

    if system == "darwin":
        return Path.home() / "Documents" / "KawkabAI"

    xdg_docs = os.environ.get("XDG_DOCUMENTS_DIR")
    if xdg_docs:
        return Path(xdg_docs) / "KawkabAI"
    return Path.home() / "Documents" / "KawkabAI"


class Paths:
    """Centralized path management for Kawkab AI."""

    def __init__(self) -> None:
        self._appdata = _get_appdata_dir()
        self._localappdata = _get_localappdata_dir()
        self._documents = _get_documents_dir()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create all required directories if they don't exist."""
        for path in [
            self.appdata,
            self.localappdata,
            self.documents,
            self.videos,
            self.exports,
            self.cache,
            self.logs,
            self.models,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    @property
    def appdata(self) -> Path:
        """%APPDATA%/KawkabAI/ - Config, settings, SQLite database."""
        return self._appdata

    @property
    def localappdata(self) -> Path:
        """%LOCALAPPDATA%/KawkabAI/ - Cache, temporary files."""
        return self._localappdata

    @property
    def documents(self) -> Path:
        """Documents/KawkabAI/ - User data root."""
        return self._documents

    @property
    def videos(self) -> Path:
        """Documents/KawkabAI/videos/ - Match video storage."""
        return self._documents / "videos"

    @property
    def exports(self) -> Path:
        """Documents/KawkabAI/exports/ - PDF reports, video clips, CSV."""
        return self._documents / "exports"

    @property
    def cache(self) -> Path:
        """%LOCALAPPDATA%/KawkabAI/cache/ - Preprocessed videos, temp files."""
        return self._localappdata / "cache"

    @property
    def logs(self) -> Path:
        """%APPDATA%/KawkabAI/logs/ - Application logs."""
        return self._appdata / "logs"

    @property
    def models(self) -> Path:
        """%APPDATA%/KawkabAI/models/ - Downloaded AI model weights."""
        return self._appdata / "models"

    @property
    def database(self) -> Path:
        """SQLite database file path."""
        return self._appdata / "kawkab.db"

    @property
    def config_file(self) -> Path:
        """User config file path."""
        return self._appdata / "config.json"

    @property
    def knowledge_base(self) -> Path:
        """Knowledge base directory (bundled with app)."""
        possible = [
            Path(__file__).parent / "knowledge",
            Path(__file__).parent.parent / "knowledge",
            Path(__file__).parent.parent.parent / "src" / "kawkab" / "knowledge",
        ]
        for p in possible:
            if p.exists():
                return p
        return Path(__file__).parent / "knowledge"


_paths: Paths | None = None


def get_paths() -> Paths:
    """Get or create paths singleton."""
    global _paths
    if _paths is None:
        _paths = Paths()
    return _paths
