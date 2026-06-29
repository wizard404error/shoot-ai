# Kawkab AI - Build Spec for PyInstaller
# Builds a single-folder distribution; use --onefile for single .exe

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['src/kawkab/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/kawkab/web', 'kawkab/web'),
        ('src/kawkab/knowledge', 'kawkab/knowledge'),
        ('locales', 'locales'),
    ],
    hiddenimports=[
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebChannel',
        'ultralytics',
        'torch',
        'torchvision',
        'cv2',
        'numpy',
        'pandas',
        'loguru',
        'pydantic',
        'pydantic_settings',
        'yaml',
        'ffmpeg',
        'mplsoccer',
        'kloppy',
        'networkx',
        'httpx',
        'PIL',
        'tqdm',
        'lap',
        'sklearn',
        'kawkab.plugins',
        'kawkab.plugins.manager',
        'kawkab.core.observability',
        'kawkab.services.tactical_review_service',
        'kawkab.services.live_tagging_service',
        'kawkab.services.auto_updater_service',
        'kawkab.services.collaboration_service',
        'kawkab.services.video_sync_service',
        'kawkab.services.highlight_reel_service',
        'kawkab.services.wearable_import_service',
        'kawkab.services.physiological_merge_service',
        'kawkab.services.physio_tactical_correlation',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib.tests',
        'pytest',
        'sphinx',
        'IPython',
        'jupyter',
        'notebook',
        'easyocr',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KawkabAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KawkabAI',
)
