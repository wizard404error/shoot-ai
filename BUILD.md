# Build Instructions

This document explains how to build the Kawkab AI Windows installer.

## Prerequisites

- Python 3.12 with all project dependencies installed (`uv sync --extra gpu --extra dev --extra build`)
- PyTorch with CUDA support
- PyInstaller (`uv sync --extra build` installs it)
- (Optional) [Inno Setup](https://jrsoftware.org/isinfo.php) for creating the Windows installer

## Build Steps

### 1. Run the full pipeline test (optional sanity check)

```powershell
uv run python scripts/end_to_end_test.py --video data/real_match.mp4
```

This ensures the codebase is working before bundling.

### 2. Pre-build cleanup

```powershell
# Remove old build artifacts
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
```

### 3. Build the PyInstaller bundle

```powershell
# Build as a directory distribution (faster, smaller startup)
uv run pyinstaller KawkabAI.spec

# Or build as a single .exe (slower startup, single file)
# Modify KawkabAI.spec: change EXE to have console=False and add --onefile
```

**Output:** `dist/KawkabAI/` (folder with .exe and dependencies)

**Bundle size:** ~1.5-2.5 GB (includes PyTorch + ultralytics + all models)

**Build time:** 5-15 minutes on modern hardware

### 4. (Optional) Create Windows installer with Inno Setup

1. Download and install [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Open `installer.iss` in Inno Setup
3. Click "Compile" (or run from CLI: `iscc installer.iss`)
4. **Output:** `installer/KawkabAI-Setup-0.1.0.exe` (single .exe installer)

**Installer size:** Same as bundle (~2 GB), compressed to ~800 MB

### 5. Test the installer

1. Run `installer/KawkabAI-Setup-0.1.0.exe`
2. Follow the installation wizard
3. Launch Kawkab AI from Start Menu or Desktop
4. Verify it opens, accepts video uploads, and analyzes matches

### 6. Distribute

Upload the installer to GitHub Releases:

```powershell
gh release create v0.1.0 installer/KawkabAI-Setup-0.1.0.exe `
  --title "Kawkab AI v0.1.0" `
  --notes "First public release! See README.md for features."
```

## Build Optimization

To reduce bundle size:

```powershell
# Use conda-installed PyTorch (smaller than pip)
conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia

# Exclude unnecessary packages in KawkabAI.spec:
excludes=[
    'torchvision.datasets',
    'torch.distributions',
    'matplotlib.tests',
    'PIL.ImageQt',
    # ... etc
]
```

To reduce startup time:

- Use a directory distribution instead of --onefile
- Bundle models separately (download on first run)

## Code Signing (Optional)

For a professional release, sign the .exe with a code certificate:

```powershell
# Using signtool (Windows SDK)
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com dist\KawkabAI\KawkabAI.exe
```

This prevents Windows SmartScreen warnings.

## Continuous Integration

The project includes a GitHub Actions workflow (`.github/workflows/build.yml`)
that automatically builds the installer on every release tag.

## Troubleshooting

**"Failed to load Qt platform plugin"**: Ensure PySide6.QtWebEngineWidgets is in hiddenimports.

**"Module not found"**: Add the missing module to `hiddenimports` in KawkabAI.spec.

**Antivirus flags the .exe**: Code-sign it or submit to Microsoft for analysis.

**Build takes too long**: Build only the directory distribution, not --onefile.
