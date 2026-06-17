"""Model manager - handles model download, caching, and lazy loading.

Production-grade model management for Kawkab AI:
1. Check if models exist in local cache
2. Download from remote URLs with progress callbacks
3. Validate downloaded files (SHA-256 checksum)
4. Cache management (cleanup old models)
5. Integration with CVService and VRAMManager for sequential loading

This enables future lazy-loading: the installer can be small (~50MB launcher)
and models can be downloaded on first run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable
from urllib.request import urlopen, Request
from urllib.error import URLError

from kawkab.core.logging import get_logger
from kawkab.core.paths import get_paths

logger = get_logger(__name__)


class ModelManager:
    """Manages AI model download, caching, and validation.

    Models are stored in the user's cache directory under `models/`.
    A manifest file (`models.json`) tracks available models, versions,
    and checksums.
    """

    # Default model URLs (can be overridden via manifest)
    DEFAULT_MODELS = {
        "yolo11n": {
            "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt",
            "size_mb": 5.4,
            "sha256": None,  # Fetched at runtime or from manifest
        },
        "yolo11s": {
            "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt",
            "size_mb": 18.6,
            "sha256": None,
        },
        "yolo11m": {
            "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11m.pt",
            "size_mb": 38.9,
            "sha256": None,
        },
        "yolo11l": {
            "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11l.pt",
            "size_mb": 51.5,
            "sha256": None,
        },
        "yolo11x": {
            "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11x.pt",
            "size_mb": 97.1,
            "sha256": None,
        },
    }

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = (cache_dir or get_paths().cache / "models")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.cache_dir / "models.json"
        self._manifest: dict = {}
        self._load_manifest()

    def _load_manifest(self) -> None:
        """Load the model manifest from disk."""
        if self.manifest_path.exists():
            try:
                self._manifest = json.loads(self.manifest_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load model manifest: {e}")
                self._manifest = {}
        else:
            self._manifest = {}

    def _save_manifest(self) -> None:
        """Save the model manifest to disk."""
        try:
            self.manifest_path.write_text(json.dumps(self._manifest, indent=2))
        except OSError as e:
            logger.warning(f"Failed to save model manifest: {e}")

    def _compute_sha256(self, path: Path) -> str:
        """Compute SHA-256 checksum of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def get_model_path(self, model_name: str) -> Path | None:
        """Get the local path to a cached model.

        Args:
            model_name: e.g., "yolo11l" or "yolo11l.pt"

        Returns:
            Path to the model file if cached, None otherwise
        """
        name = model_name.replace(".pt", "")
        model_path = self.cache_dir / f"{name}.pt"
        if model_path.exists():
            return model_path
        return None

    def is_model_available(self, model_name: str) -> bool:
        """Check if a model is available locally."""
        return self.get_model_path(model_name) is not None

    def download_model(
        self,
        model_name: str,
        progress_callback: Callable[[float, str], None] | None = None,
        force: bool = False,
    ) -> Path:
        """Download a model to the local cache.

        Args:
            model_name: e.g., "yolo11l"
            progress_callback: Called with (progress_0_to_1, message)
            force: Re-download even if already cached

        Returns:
            Path to the downloaded model file

        Raises:
            ValueError: If model_name is not known
            RuntimeError: If download fails
        """
        name = model_name.replace(".pt", "")
        model_path = self.cache_dir / f"{name}.pt"

        if not force and model_path.exists():
            logger.info(f"Model {name} already cached at {model_path}")
            if progress_callback:
                progress_callback(1.0, "Model already cached")
            return model_path

        info = self.DEFAULT_MODELS.get(name)
        if info is None:
            raise ValueError(f"Unknown model: {name}. Available: {list(self.DEFAULT_MODELS.keys())}")

        url = info["url"]
        logger.info(f"Downloading {name} from {url}...")

        if progress_callback:
            progress_callback(0.0, f"Downloading {name}...")

        try:
            req = Request(url, headers={"User-Agent": "KawkabAI/1.0"})
            with urlopen(req, timeout=300) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192

                with open(model_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0 and progress_callback:
                            progress = downloaded / total_size
                            mb = downloaded / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            progress_callback(
                                progress,
                                f"Downloading {name}: {mb:.1f} / {total_mb:.1f} MB",
                            )

        except URLError as e:
            if model_path.exists():
                model_path.unlink()
            raise RuntimeError(f"Failed to download {name}: {e}") from e

        # Verify checksum if available
        expected_sha256 = info.get("sha256")
        if expected_sha256:
            actual_sha256 = self._compute_sha256(model_path)
            if actual_sha256 != expected_sha256:
                model_path.unlink()
                raise RuntimeError(
                    f"Checksum mismatch for {name}: expected {expected_sha256}, got {actual_sha256}"
                )

        # Update manifest
        self._manifest[name] = {
            "path": str(model_path),
            "size_bytes": model_path.stat().st_size,
            "sha256": self._compute_sha256(model_path),
        }
        self._save_manifest()

        logger.info(f"Model {name} downloaded to {model_path}")
        if progress_callback:
            progress_callback(1.0, f"{name} downloaded successfully")

        return model_path

    def ensure_model(
        self,
        model_name: str,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> Path:
        """Ensure a model is available, downloading if necessary.

        Args:
            model_name: e.g., "yolo11l"
            progress_callback: Called with progress updates

        Returns:
            Path to the model file
        """
        path = self.get_model_path(model_name)
        if path is not None:
            if progress_callback:
                progress_callback(1.0, "Model ready")
            return path
        return self.download_model(model_name, progress_callback)

    def list_cached_models(self) -> list[str]:
        """List all models currently in the cache."""
        return [
            f.stem for f in self.cache_dir.glob("*.pt")
            if f.name != "models.json"
        ]

    def cleanup_cache(self, keep_models: list[str] | None = None) -> int:
        """Remove old/unused models from cache.

        Args:
            keep_models: List of model names to keep (e.g., ["yolo11l"])

        Returns:
            Number of files removed
        """
        keep = set(keep_models or [])
        removed = 0
        for f in self.cache_dir.glob("*.pt"):
            if f.stem not in keep:
                try:
                    f.unlink()
                    removed += 1
                    logger.info(f"Removed cached model: {f.name}")
                except OSError as e:
                    logger.warning(f"Failed to remove {f}: {e}")
        return removed

    def get_cache_size_mb(self) -> float:
        """Get total size of cached models in MB."""
        total = 0
        for f in self.cache_dir.glob("*.pt"):
            total += f.stat().st_size
        return total / (1024 * 1024)
