# Kawkab AI ⚽

> **The AI Football Coach for Amateur Teams** — 100% Private, 100% Offline, $0 Cost

> ✅ **v0.4.1 status:** Tracking "excellent" (28 tracks, 1.27x of expected), homography in real meters.
> ⚠️ **Not yet validated with real coaches.** See [STATUS.md](STATUS.md).

---

## What It Does (v0.4.1)

- **Detects & tracks players + ball** using YOLOv11 + BoT-SORT with smart filters + top-N filter
- **Tracking quality: "excellent"** (28 tracks for 22-player match, 1.27x of expected)
- **Team color clustering** auto-assigns home/away (no manual labels)
- **Camera calibration (homography)** — coach clicks 4 pitch corners, stats become real meters
- **Computes statistics in meters**: possession %, passes, distance, player speeds, xG, xT
- **Detects formations**: 4-3-3, 4-4-2, 4-2-3-1, 3-5-2, etc.
- **Generates coach-friendly reports** in English or Arabic using a local LLM
- **Identifies tactical patterns** via a knowledge base of 22 rules + 19 drills
- **Generates 4-week training plans** with progressive overload

---

## ⚠️ Read This First

This project was built in 3 intensive sessions using AI-assisted development.
**It is not production-ready.** Critical foundation work is still needed.

**What works:**
- ✅ Desktop app launches and shows the UI
- ✅ All 12 services import and initialize
- ✅ YOLO detects players/ball on broadcast-quality footage
- ✅ LLM generates coach reports in EN/AR
- ✅ 22 rules + 19 drills in knowledge base
- ✅ 4-week training plan generator
- ✅ PyInstaller .exe builds (1.75 GB bundle)

**What doesn't work (honestly):**
- ❌ **Tracking fragmentation**: 91 tracks for 22 players (target: <30). Real amateur footage will be worse.
- ❌ **No homography by default**: All spatial stats are in pixel space, not meters. Coach must calibrate first.
- ❌ **Jersey OCR is unreliable**: 8-20px numbers on amateur footage are very hard to read.
- ❌ **No validation with real coaches**: Everything is theoretical until tested in the wild.
- ❌ **Bundle is 1.75 GB**: Way too big for amateur adoption.

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

# Test tracking quality (v0.4.1)
uv run python scripts/test_tracking_v2.py --video path/to/match.mp4

# Test homography integration (v0.4.0)
uv run python scripts/test_homography.py

# Launch the desktop app
uv run python -m kawkab
```

### v0.4.1 Workflow

1. Drop a match video in the app
2. Click "Analyze" — YOLO tracks 28 players (close to actual 22), K-means assigns teams by color
3. Click 4 pitch corners — calibration saved as homography matrix (in meters)
4. Re-analyze with homography — distance/formations/line height now in real meters
5. Generate coach report — LLM produces tactical narrative with evidence

---

## Honest Status (v0.4.1)

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

This is a **viable technical architecture** with **real domain knowledge** in the knowledge base, but it is **not yet a finished product**. The next 3-6 months need to focus on:

1. **Validating tracking accuracy** on real amateur footage (currently "fair")
2. **Integrating SoccerNet/tracklab** for football-tuned ReID
3. **Testing with 5+ amateur coaches** to see if reports are actually useful
4. **Reducing bundle size** via lazy model loading

Until those happen, this is a research project, not a product.

**The vision is sound. The execution needs validation.**

---

*Reviewed by Claude (kawkab-ai-review.md). Many critical issues identified and being addressed.*
