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
        'faiss',
        'PIL',
        'tqdm',
        'lap',
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
