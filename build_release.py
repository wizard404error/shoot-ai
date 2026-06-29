"""Kawkab AI — Full release build pipeline.

Usage:
    python build_release.py          # Build + package (default)
    python build_release.py --spec   # Only regenerate PyInstaller spec
    python build_release.py --exe    # Only build .exe
    python build_release.py --installer   # Only build installer
    python build_release.py --dmg    # Only build macOS DMG
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
SPEC_FILE = ROOT / "KawkabAI.spec"
VERSION = "0.13.0"


def clean():
    print("[1/5] Cleaning previous builds...")
    for d in ["build", "dist/KawkabAI", "dist/installer"]:
        p = ROOT / d
        if p.exists():
            shutil.rmtree(p)
    print("  OK")


def build_spec():
    print("[2/5] Regenerating PyInstaller spec...")
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "KawkabAI",
        "--icon", str(ROOT / "assets" / "icon.ico"),
        "--add-data", f"src/kawkab/web{os.pathsep}kawkab/web",
        "--add-data", f"src/kawkab/knowledge{os.pathsep}kawkab/knowledge",
        "--add-data", f"locales{os.pathsep}locales",
        "--hidden-import", "PySide6.QtWebEngineWidgets",
        "--hidden-import", "PySide6.QtWebChannel",
        "--hidden-import", "ultralytics",
        "--hidden-import", "torch",
        "--hidden-import", "torchvision",
        "--hidden-import", "cv2",
        "--hidden-import", "numpy",
        "--hidden-import", "pandas",
        "--hidden-import", "loguru",
        "--hidden-import", "pydantic",
        "--hidden-import", "yaml",
        "--hidden-import", "networkx",
        "--hidden-import", "httpx",
        "--hidden-import", "PIL",
        "--hidden-import", "tqdm",
        "--hidden-import", "sklearn",
        "--hidden-import", "mplsoccer",
        "--hidden-import", "kloppy",
        "--hidden-import", "kawkab.plugins",
        "--hidden-import", "kawkab.plugins.manager",
        "--hidden-import", "kawkab.core.observability",
        "--hidden-import", "kawkab.services.tactical_review_service",
        "--hidden-import", "kawkab.services.live_tagging_service",
        "--hidden-import", "kawkab.services.auto_updater_service",
        "--hidden-import", "kawkab.services.collaboration_service",
        "--hidden-import", "kawkab.services.video_sync_service",
        "--hidden-import", "kawkab.services.highlight_reel_service",
        "--hidden-import", "kawkab.services.wearable_import_service",
        "--hidden-import", "kawkab.services.physiological_merge_service",
        "--hidden-import", "kawkab.services.physio_tactical_correlation",
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib.tests",
        "--exclude-module", "pytest",
        "--exclude-module", "sphinx",
        "--exclude-module", "IPython",
        "--exclude-module", "jupyter",
        "--exclude-module", "easyocr",
        "--console",
        str(ROOT / "src" / "kawkab" / "__main__.py"),
    ])
    print("  OK")


def build_exe():
    print("[3/5] Building executable with PyInstaller...")
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        str(SPEC_FILE),
        "--noconfirm",
    ])
    print("  OK")


def build_installer():
    print("[4/5] Building Windows installer with Inno Setup...")
    iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if not Path(iscc).exists():
        print("  WARNING: Inno Setup not found. Install from https://jrsoftware.org/isdl.php")
        print("  Then run: iscc installer.iss")
        return
    subprocess.check_call([iscc, str(ROOT / "installer.iss")])
    print("  OK")


def build_dmg():
    print("[5/5] Building macOS DMG...")
    dmg_script = ROOT / "build_dmg.sh"
    if not dmg_script.exists():
        print("  WARNING: build_dmg.sh not found. Skipping DMG.")
        return
    subprocess.check_call(["bash", str(dmg_script)])
    print("  OK")


def main():
    parser = argparse.ArgumentParser(description="Kawkab AI Release Builder")
    parser.add_argument("--spec", action="store_true", help="Only regenerate spec")
    parser.add_argument("--exe", action="store_true", help="Only build exe")
    parser.add_argument("--installer", action="store_true", help="Only build installer")
    parser.add_argument("--dmg", action="store_true", help="Only build DMG")
    args = parser.parse_args()

    if args.spec:
        build_spec()
    elif args.exe:
        clean()
        build_spec()
        build_exe()
    elif args.installer:
        build_installer()
    elif args.dmg:
        build_dmg()
    else:
        clean()
        build_spec()
        build_exe()
        build_installer()
        build_dmg()
        print(f"\n✅ Release v{VERSION} built successfully in {DIST_DIR}")


if __name__ == "__main__":
    main()
