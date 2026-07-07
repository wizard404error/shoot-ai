# Kawkab AI ⚽

> **The AI Football Coach for Amateur Teams** — 100% Private, 100% Offline, $0 Cost

> 📊 **Current state:** 140+ services, 8 external data sources, 3700+ unit tests, full Arabic+English support.
> 🚧 **Status:** Production-aiming. See [STATUS.md](STATUS.md) for the full report.

[![Tests](https://github.com/user-attachments/assets/4e7f3e3a-1e0e-4f0f-8f0f-3e3a1e0e4f0f)](.github/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-50%25-yellowgreen)](.github/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## What It Does

- **Detects & tracks players + ball** using YOLOv11/YOLO26 + BoT-SORT/Norfair with smart filters
- **YOLO-pose** for activity classification, fall detection, and player orientation
- **Team color clustering** auto-assigns home/away (no manual labels)
- **Jersey number recognition** via OCR for player identification
- **Face recognition** with InsightFace for re-identification
- **Camera calibration (homography)** — 4 pitch corners → real meters
- **Computes statistics in meters**: possession %, passes, distance, sprints, xG, xT, PPDA
- **Advanced metrics**: pressure, physical load, set-piece detection, progressive actions
- **Detects formations**: 4-3-3, 4-4-2, 4-2-3-1, 3-5-2, 5-3-2, 4-1-4-1, etc.
- **Native services**: PsychologyService, FootballRulesService, CardDetectionService, WeatherService
- **External data**: football-data.org, Bzzoiro, TheSportsDB, API-Football, EasySoccerData, StatsBomb, OpenFootball, RoboFlow Sports
- **Algorithm ports**: Kabsch (rigid alignment), Hungarian (optimal assignment), SpatialHash (O(1) neighbor lookup)
- **Bilingual reports** in English or Arabic via local LLM (Ollama)
- **Tactical pattern knowledge base** of 22+ rules and 19+ drills
- **Tactical sandbox** with matter.js for interactive formation play
- **Set-piece simulator** with MuJoCo-style physics for free-kick analysis
- **Video weather detection** with TobyBreckon-style raindrop sliding window
- **Generates 4-week training plans** with progressive overload

---

## ⚠️ Status

This project is under active development toward production quality.
- 50+ backend services, 200+ unit tests, full Arabic+English UI
- Multi-phase roadmap: ✅ Phase 1 (test coverage), 🚧 Phase 2 (real-time), Phase 3 (pro analytics), Phase 4 (UX polish)

**What works:**
- ✅ Desktop app launches and shows the UI
- ✅ 50+ services initialize and operate
- ✅ YOLO + Norfair tracking on broadcast-quality footage
- ✅ YOLO26-pose for activity/fall/orientation
- ✅ Face recognition + jersey OCR
- ✅ 8 external data sources (free tiers)
- ✅ LLM generates coach reports in EN/AR
- ✅ 22+ rules + 19+ drills knowledge base
- ✅ Weather video detection (TobyBreckon-style)
- ✅ Football rules classifier (17 IFAB Laws)
- ✅ Set-piece simulator (MuJoCo + analytical fallback)
- ✅ Matter.js tactical sandbox
- ✅ 4-week training plan generator
- ✅ PyInstaller .exe builds (~1.75 GB bundle)

**Known limitations (honest):**
- ⚠️ **Tracking fragmentation**: 91 tracks for 22 players (target: <30). Real amateur footage will be worse.
- ⚠️ **No homography by default**: All spatial stats are in pixel space, not meters. Coach must calibrate first.
- ⚠️ **Jersey OCR is unreliable**: 8-20px numbers on amateur footage are very hard to read.
- ⚠️ **No validation with real coaches**: Everything is theoretical until tested in the wild.
- ⚠️ **Bundle is 1.75 GB**: Way too big for amateur adoption.

**Read [STATUS.md](STATUS.md) for the full honest assessment.**

---

## Quick Start

### Prerequisites

- **Windows 10/11** (also works on macOS/Linux)
- **Python 3.12+** (we recommend [uv](https://docs.astral.sh/uv/))
- **NVIDIA GPU** with 8GB+ VRAM (RTX 3060+, RTX 4070 recommended)
- **8GB+ RAM**
- **Ollama** for local LLM: [ollama.com/download](https://ollama.com/download)
- **FFmpeg** for video processing

### Installation

```powershell
# 1. Install uv (fast Python package manager)
winget install astral-sh.uv

# 2. Install Ollama
winget install Ollama.Ollama

# 3. Install FFmpeg
winget install Gyan.FFmpeg

# 4. Clone this repository
git clone https://github.com/jraya106/kawkab-ai.git
cd kawkab-ai

# 5. Install dependencies (includes qasync for Qt+asyncio bridge)
uv sync --extra gpu --extra audio --extra tactical --extra dev

# 6. Install CUDA-enabled PyTorch (CRITICAL for GPU)
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 --reinstall

# 7. Pull a local LLM (8-9 GB)
ollama pull ministral-3:14b
# Alternatives: qwen3:14b, gemma4:12b
```

### First Run

```powershell
# Verify everything is set up
uv run python scripts/verify_system.py

# Test tracking quality (v0.12.0)
uv run python scripts/test_tracking_v2.py --video path/to/match.mp4

# Test homography integration (v0.12.0)
uv run python scripts/test_homography.py

# Launch the desktop app
uv run python -m kawkab
```

### v0.12.0 Workflow

1. Drop a match video in the app
2. Click "Analyze" — YOLO tracks 28 players (close to actual 22), K-means assigns teams by color
3. Click 4 pitch corners — calibration saved as homography matrix (in meters)
4. Re-analyze with homography — distance/formations/line height now in real meters
5. Generate coach report — LLM produces tactical narrative with evidence

---

## Honest Status (v0.12.0)

### What's Actually Working ✅

| Feature | Status | Notes |
|---|---|---|
| YOLOv11 + BoT-SORT + Top-N filter | ✅ "Excellent" | 28 tracks, 1.27x of expected |
| Homography UI + integration | ✅ Working | Real meters for distance/formations |
| Team color clustering | ✅ Working | K-means auto home/away |
| SQLite storage | ✅ Working | Tested with SQLite |
| LLM (Ollama) | ✅ Working | EN + AR, with retry logic |
| Knowledge base | ✅ Working | 22 rules + 19 drills, YAML loader |
| Desktop app | ✅ Launches | PySide6 + QWebChannel bridge |
| PyInstaller | ✅ Builds | 1.75 GB bundle |

### What Needs Validation ⚠️

| Feature | Status | Risk |
|---|---|---|
| Tracking on amateur footage | ⚠️ "Excellent" on broadcast | Real amateur footage untested |
| Homography | ✅ Manual only | Coach must click 4 pitch corners per match |
| xG / xT | ✅ In meters | Need homography applied |
| Formations | ✅ 4-4-3 / 3-3-2 realistic | In meters with homography |
| Jersey OCR | ⚠️ Unreliable | 8-20px numbers on amateur footage |
| Reasoning | ⚠️ Untested | Rules fire on patterns we don't measure yet |
| LLM reports | ⚠️ Impressive but untested | Need real coach feedback |

### What's Not Started ❌

| Feature | Plan | Status |
|---|---|---|
| Auto keypoint detection | Homography | ❌ |
| SoccerNet/tracklab integration | Better ReID | ❌ |
| Lazy model loading | 50 MB launcher | ❌ |
| Validation with 5+ amateur coaches | Quality | ❌ |
| Documentation videos | Adoption | ❌ |
| Freemium model (Lemon Squeezy) | Monetization | ❌ |

---

## Architecture

```
Kawkab AI Desktop (1.75 GB bundle, 66 MB exe)
│
├── 13 Services (async)
│   ├── CVService              (YOLOv11l + BoT-SORT + top-N filter + pitch mask)
│   ├── HomographyService      (manual 4-corner calibration, meters-based)
│   ├── VRAMManager            (sequential model loading, GPU budget)
│   ├── EnhancementService     (FFmpeg filters)
│   ├── AnalysisService        (formations, PPDA, xG, xT in meters)
│   ├── ReasoningService       (22-rule tactical diagnosis)
│   ├── TrainingPlanGenerator  (4-week progressive plans)
│   ├── ClipExtractionService  (FFmpeg evidence clips)
│   ├── KnowledgeService       (22 rules + 19 drills)
│   ├── LLMService             (Ollama local, EN+AR)
│   ├── AudioService           (Whisper, whistle)
│   └── StorageService         (SQLite)
│
├── GPU: RTX 4070 (CUDA 12.1, PyTorch 2.5.1)
├── LLM: Ollama + Ministral/Qwen/Gemma (local, free)
└── Distribution: PyInstaller → GitHub Releases
```

---

## Resources We Build On

- **[Ultralytics YOLOv11](https://github.com/ultralytics/ultralytics)** — Object detection
- **[SoccerNet](https://github.com/SoccerNet)** — Football CV (we should integrate SoccerNet/tracklab next)
- **[boxmot](https://github.com/mikel-brostrom/boxmot)** — Multi-tracker library (next integration)
- **[socceraction](https://github.com/ML-KULeuven/socceraction)** — Action valuation
- **[Ollama](https://ollama.com)** — Local LLM runner
- **[FFmpeg](https://ffmpeg.org)** — Video preprocessing
- **[mplsoccer](https://github.com/andrewjohnsonsports/mplsoccer)** — Pitch visualizations
- **[Kloppy](https://github.com/PySport/kloppy)** — Sports data standardization
- **[PySide6](https://wiki.qt.io/Qt_for_Python)** — Desktop UI framework
- **[qasync](https://github.com/CabbageDevelopment/qasync)** — Qt + asyncio bridge ⭐ NEW

---

## Development

### Project Structure

```
kawkab-ai/
├── src/kawkab/
│   ├── app.py                  # Main PySide6 window
│   ├── core/                   # Config, logging, paths
│   ├── services/               # 12 async services
│   │   ├── cv_service.py       # YOLO + BoT-SORT (v2: smart filters)
│   │   ├── homography_service.py  # ⭐ NEW: pixel->pitch conversion
│   │   ├── vram_manager.py     # ⭐ NEW: GPU memory management
│   │   ├── enhancement_service.py
│   │   ├── analysis_service.py
│   │   ├── reasoning_service.py
│   │   ├── training_plan_service.py
│   │   ├── clip_service.py
│   │   ├── knowledge_service.py
│   │   ├── llm_service.py
│   │   ├── audio_service.py
│   │   └── storage_service.py
│   ├── ui/                     # QWebChannel bridge
│   ├── web/                    # Frontend (HTML/JS/CSS)
│   └── knowledge/              # YAML rules + drills
├── scripts/                    # Test & utility scripts
├── tests/                      # Unit tests
├── data/                       # User videos
├── docs/                       # Additional documentation
└── PLAN.md                     # Original development plan
```

### Running Tests

```powershell
# Verify all services work
uv run python scripts/verify_system.py

# Test tracking quality (NEW v2)
uv run python scripts/test_tracking_v2.py --video path/to/match.mp4

# Test YOLO on GPU
uv run python scripts/smoke_test_cv.py

# Test LLM (English + Arabic)
uv run python scripts/smoke_test_llm.py

# Run full pipeline on a video
uv run python scripts/end_to_end_test.py --video your_match.mp4
```

### Building the Installer

See [BUILD.md](BUILD.md) for detailed build instructions.

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Bottom Line

This is a **viable technical architecture** with **real domain knowledge** in the knowledge base, and at v0.8.3 is on the path toward a real product. The next phases need to focus on:

1. **Validating tracking accuracy** on real amateur footage (currently tuned for broadcast)
2. **Integrating SoccerNet/tracklab** for football-tuned ReID
3. **Testing with 5+ amateur coaches** to see if reports are actually useful
4. **Reducing bundle size** via lazy model loading
5. **Building the trust layer** (model card, data card, ground truth eval, LLM groundedness)

See **[`docs/INDEX.md`](docs/INDEX.md)** for the full documentation map.
See **[`ITERATION_LOG.md`](ITERATION_LOG.md)** for the current cycle log and the 63-target backlog.

**The vision is sound. The execution is iterating.**

---

*Initial review by Claude (kawkab-ai-review.md). Subsequent cycles tracked in ITERATION_LOG.md.*
