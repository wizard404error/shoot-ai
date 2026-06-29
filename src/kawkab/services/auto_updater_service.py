from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from kawkab.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ReleaseInfo:
    version: str
    download_url: str
    release_notes: str
    published_at: str
    is_prerelease: bool = False


class AutoUpdaterService:
    def __init__(self, repo: str = "wizard404error/shoot-ai", current_version: str = "0.13.0"):
        self.repo = repo
        self.current_version = current_version
        self._check_url = f"https://api.github.com/repos/{repo}/releases/latest"

    def check_for_update(self) -> str:
        try:
            resp = httpx.get(self._check_url, timeout=10.0, headers={"Accept": "application/vnd.github.v3+json"})
            if resp.status_code != 200:
                return json.dumps({"error": f"GitHub API returned {resp.status_code}", "has_update": False})
            data = resp.json()
            latest_tag = data.get("tag_name", "").lstrip("v")
            if self._compare_versions(latest_tag, self.current_version) > 0:
                assets = data.get("assets", [])
                download_url = ""
                system = platform.system().lower()
                for asset in assets:
                    name = asset.get("name", "").lower()
                    if system == "windows" and (name.endswith(".exe") or "setup" in name):
                        download_url = asset["browser_download_url"]
                        break
                    elif system == "darwin" and name.endswith(".dmg"):
                        download_url = asset["browser_download_url"]
                        break
                return json.dumps({
                    "has_update": True,
                    "version": latest_tag,
                    "download_url": download_url,
                    "release_notes": data.get("body", ""),
                    "published_at": data.get("published_at", ""),
                })
            return json.dumps({"has_update": False, "version": self.current_version})
        except Exception as e:
            logger.error(f"check_for_update failed: {e}")
            return json.dumps({"error": str(e), "has_update": False})

    def download_update(self, download_url: str) -> str:
        try:
            temp_dir = tempfile.gettempdir()
            filename = download_url.split("/")[-1] or "update"
            dest = Path(temp_dir) / filename
            logger.info(f"Downloading update from {download_url} to {dest}")
            with httpx.stream("GET", download_url, follow_redirects=True, timeout=300.0) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(dest, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
            return json.dumps({"ok": True, "path": str(dest), "size": downloaded})
        except Exception as e:
            logger.error(f"download_update failed: {e}")
            return json.dumps({"error": str(e)})

    def apply_update(self, installer_path: str) -> str:
        try:
            system = platform.system().lower()
            if system == "windows":
                subprocess.Popen([installer_path, "/SILENT", "/SUPPRESSMSGBOXES"], shell=True)
            elif system == "darwin":
                subprocess.Popen(["open", installer_path])
            else:
                subprocess.Popen(["xdg-open", installer_path], shell=True)
            return json.dumps({"ok": True, "message": "Installer launched"})
        except Exception as e:
            logger.error(f"apply_update failed: {e}")
            return json.dumps({"error": str(e)})

    def get_current_version(self) -> str:
        return json.dumps({"version": self.current_version, "platform": platform.system(), "arch": platform.machine()})

    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        parts1 = [int(x) for x in v1.split(".") if x.isdigit()]
        parts2 = [int(x) for x in v2.split(".") if x.isdigit()]
        for a, b in zip(parts1, parts2):
            if a > b:
                return 1
            if a < b:
                return -1
        return len(parts1) - len(parts2)
