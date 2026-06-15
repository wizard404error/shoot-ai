# Kawkab AI ⚽

> **The AI Football Coach for Amateur Teams** — 100% Private, 100% Offline, $0 Cost

Kawkab AI analyzes your match videos with professional-grade computer vision and generates coach-friendly reports using a local AI assistant. Everything runs on your machine — no cloud, no subscriptions, no data leaving your computer.

---

## What It Does

- **Detects & tracks players + ball** using YOLOv11 + BoT-SORT (state-of-the-art computer vision)
- **Computes statistics**: possession %, passes, shots, distance covered, player speeds
- **Generates coach-friendly reports** in English or Arabic using a local LLM (Ollama + Qwen/Ministral/Gemma)
- **Identifies tactical patterns** across multiple matches
- **Recommends training drills** from a curated knowledge base
- **Suggests 4-week training plans** to fix detected problems
- **Works fully offline** — no internet required after setup

---

## Quick Start

### Prerequisites

- **Windows 10/11** (also works on macOS/Linux)
- **Python 3.12+** (we recommend installing via [uv](https://docs.astral.sh/uv/))
- **NVIDIA GPU** recommended (RTX 3060+ with 8GB+ VRAM) — works on CPU too, but slower
- **8GB+ RAM**, **2GB+ disk** for models
- **Ollama** for local LLM: [ollama.com/download](https://ollama.com/download)

### Installation

```powershell
# 1. Install uv (fast Python package manager)
winget install astral-sh.uv

# 2. Install Ollama
winget install Ollama.Ollama

# 3. Clone this repository
git clone https://github.com/yourusername/kawkab-ai.git
cd kawkab-ai

# 4. Install dependencies
uv sync --extra gpu --extra audio --extra tactical --extra dev

# 5. Install CUDA PyTorch (for GPU acceleration)
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 --reinstall

# 6. Pull a local LLM
ollama pull ministral-3:14b
# Or alternatives: qwen2.5:14b-instruct-q4_K_M, gemma4:12b
```

### Launch the App

```powershell
# Run the desktop application
uv run kawkab
```

The app opens a native window. Drop a match video, click "Analyze", and wait 5-15 minutes for results.

### Command-Line Analysis (No GUI)

For testing or batch processing:

```powershell
# Run end-to-end pipeline test
uv run python scripts/end_to_end_test.py --video path/to/match.mp4

# Generate a 30-second synthetic test video (requires FFmpeg)
uv run python scripts/generate_synthetic_video.py --duration 30

# Verify system is ready
uv run python scripts/verify_system.py

# Test the LLM integration
uv run python scripts/smoke_test_llm.py
```

---

## System Requirements

| Component | Minimum | Recommended |
|---|---|---|
| OS | Windows 10, macOS 11, Ubuntu 20.04 | Windows 11, macOS 13+ |
| Python | 3.12 | 3.12 |
| GPU | Any NVIDIA 8GB+ | RTX 4070 / RTX 3080+ |
| RAM | 8 GB | 16 GB+ |
| Disk | 5 GB | 20 GB+ (for video storage) |
| VRAM | 6 GB (CPU mode) | 12 GB (GPU mode) |

---

## Architecture

```
Kawkab AI Desktop (.exe)
│
├── PySide6 MainWindow
│   └── QWebEngineView (Vue 3 + Tailwind UI)
│       └── QWebChannel (JS ↔ Python bridge)
│           └── Service Layer
│               ├── CVService (YOLOv11 + BoT-SORT)
│               ├── EnhancementService (FFmpeg filters)
│               ├── AnalysisService (stats, patterns)
│               ├── ReasoningService (tactical diagnosis)
│               ├── KnowledgeService (500+ rules + drills)
│               ├── LLMService (Ollama / Groq / Google)
│               ├── AudioService (Whisper transcription)
│               └── StorageService (SQLite + FAISS)
│
├── GPU: NVIDIA CUDA (PyTorch)
├── Storage: SQLite + Local Filesystem
└── LLM: Ollama local (Qwen/Ministral/Gemma) or cloud (Groq/Google)
```

---

## Features

### ✅ Phase 1: Foundation (Complete)

- [x] **YOLOv11 + BoT-SORT** player & ball detection + tracking
- [x] **FFmpeg preprocessing**: stabilization, denoising, sharpening
- [x] **Basic stats**: possession %, passes, shots, distance, speeds
- [x] **Video player with player overlays** (track IDs, team colors)
- [x] **SQLite storage** of all matches, players, events
- [x] **Local LLM reports** in English & Arabic
- [x] **PySide6 desktop app** with embedded web UI
- [x] **PyInstaller .exe builder** (66 MB exe + 1.75 GB bundle)

### ✅ Phase 2: The Analyst (Complete)

- [x] **Formation detection** (4-3-3, 4-4-2, etc.) with k-means
- [x] **PPDA calculation** (Passes Per Defensive Action) — pressing intensity
- [x] **xG computation** (Expected Goals from shot distance + angle)
- [x] **xT computation** (Expected Threat from pass location)
- [x] **Defensive line height** tracking
- [x] **Pass networks** (NetworkX graphs)
- [x] **Tactical reasoning engine** — diagnoses issues using rules
- [x] **Knowledge base**: 22 tactical rules + 18 training drills
- [x] **Multi-language reports**: English + Arabic

### ✅ Phase 3: The Detective (Complete)

- [x] **Auto video clip extraction** (FFmpeg-based) for evidence
- [x] **Player jersey number OCR** (EasyOCR + YOLO torso detection)
- [x] **Tactical reasoning engine** with 22+ rule patterns
- [x] **4-week training plan generator** (Foundation → Building → Application → Mastery)
- [x] **Drill library** with 18+ curated training drills
- [x] **QWebChannel proper setup** (deferred to page load)
- [x] **Knowledge base expansion** to 22 rules + 18 drills

### 🚧 Phase 4: The Coach (In Progress)

- [ ] Drill visualizations (SVG diagrams)
- [ ] Print plan as PDF
- [ ] Re-test mechanism (auto-compare before/after plan)
- [ ] Coach feedback loop
- [ ] Multi-match pattern aggregation
- [ ] Validation with 5+ amateur coaches

### 💰 Phase 5: Scale & Monetize (Planned)

- [ ] Beta program with 20-50 amateur coaches
- [ ] Freemium model: Free, Pro ($19/mo), Academy ($49/mo)
- [ ] Multi-language polish
- [ ] Basketball support
- [ ] B2B licensing to federations

---

## Knowledge Base

The tactical knowledge is stored in versioned YAML files:

```
src/kawkab/knowledge/
├── tactics/
│   ├── defensive/      # Goal conceded patterns, line height, etc.
│   ├── offensive/      # Build-up play, chance creation, etc.
│   ├── transitions/    # Defensive/offensive transitions
│   └── individual/     # Position-specific analysis
├── drills/             # Training drills with rules, progressions
└── mappings/           # Problem → drill mapping
```

**Current:** 3 tactical rules + 3 drills (seed data)
**Target:** 500 rules + 500 drills over 10 months

To add a new rule, create a YAML file in the appropriate subdirectory. See the existing rules for the format.

---

## Open-Source Tools We Build On

- **[Ultralytics YOLOv11](https://github.com/ultralytics/ultralytics)** — Object detection
- **[roboflow/sports](https://github.com/roboflow/sports)** — Sports CV reference
- **[SoccerNet](https://github.com/SoccerNet)** — Football event detection
- **[socceraction](https://github.com/ML-KULeuven/socceraction)** — Action valuation (VAEP/xT)
- **[Ollama](https://ollama.com)** — Local LLM runner
- **[FFmpeg](https://ffmpeg.org)** — Video preprocessing
- **[mplsoccer](https://github.com/andrewjohnsonsports/mplsoccer)** — Pitch visualizations
- **[Kloppy](https://github.com/PySport/kloppy)** — Sports data standardization
- **[PySide6](https://wiki.qt.io/Qt_for_Python)** — Desktop UI framework

---

## Development

### Project Structure

```
kawkab-ai/
├── src/kawkab/
│   ├── app.py                  # Main PySide6 window
│   ├── core/                   # Config, logging, paths
│   ├── services/               # 8 async services
│   ├── ui/                     # QWebChannel bridge
│   ├── web/                    # Frontend (HTML/JS/CSS)
│   ├── knowledge/              # YAML rules + drills
│   └── __main__.py             # CLI entry point
├── scripts/                    # Test & utility scripts
│   ├── verify_system.py        # Full system check
│   ├── end_to_end_test.py      # Pipeline test with real video
│   ├── smoke_test_cv.py        # YOLO loading test
│   └── smoke_test_llm.py       # LLM integration test
├── data/                       # User videos, models
├── pyproject.toml              # All dependencies
└── PLAN.md                     # Full development plan
```

### Running Tests

```powershell
# Verify all services work
uv run python scripts/verify_system.py

# Test YOLO on GPU
uv run python scripts/smoke_test_cv.py

# Test LLM (English + Arabic)
uv run python scripts/smoke_test_llm.py

# Run full pipeline on a video
uv run python scripts/end_to_end_test.py --video your_match.mp4
```

### Building the Installer

```powershell
# Install PyInstaller
uv sync --extra build

# Build Windows .exe
uv run pyinstaller KawkabAI.spec

# Result: dist/KawkabAI.exe (single-file installer)
```

---

## Roadmap

| Phase | Weeks | Status | Focus |
|---|---|---|---|
| 1. Foundation | 1-4 | ✅ Done | Detection, basic stats, LLM reports |
| 2. The Analyst | 5-12 | 🚧 In Progress | Formations, patterns, xG |
| 3. The Detective | 13-24 | 📋 Planned | Tactical reasoning, diagnoses |
| 4. The Coach | 25-36 | 📋 Planned | Drill prescriptions, training plans |
| 5. The Product | 37-48 | 📋 Planned | Polish, beta, monetization |
| 6. Scale | 49+ | 📋 Planned | B2B, basketball, enterprise |

See [PLAN.md](PLAN.md) for the full development plan.

---

## Performance

Tested on **RTX 4070 (12GB VRAM)** with 88-second match video:

| Metric | Value |
|---|---|
| Processing speed | 26 FPS |
| CV pipeline time | ~85s |
| Formations detected | 4-3-3 / 4-2-3 |
| PPDA | 0.7 (heavy press detected) |
| Players detected | 160 unique tracks |
| Events detected | 61 passes |
| Confidence | 64.7% |
| LLM report length | 4,000+ chars |
| Knowledge base | 22 rules + 18 drills |

For 90-minute match (5400s): ~6 minutes CV + ~1 minute LLM = **~7 minutes total**

---

## Privacy

Kawkab AI is **100% private**:
- All videos stay on your computer
- All processing happens locally
- LLM runs locally via Ollama (or optionally via Groq/Google with opt-in)
- No telemetry, no analytics, no tracking
- No account required

Your tactical secrets are yours.

---

## Contributing

We welcome contributions! See [PLAN.md](PLAN.md) for the roadmap and priorities.

**Most needed:**
- Tactical rules (YAML format in `src/kawkab/knowledge/tactics/`)
- Training drills (YAML format in `src/kawkab/knowledge/drills/`)
- Bug reports and feature requests
- Translations (especially Arabic native reviews)

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Acknowledgments

Built with the help of:
- The open-source football analytics community
- Coaches' Voice, Tifo Football, Spielverlagerung (tactical knowledge)
- All the open-source maintainers whose tools make this possible

**The vision:** Every amateur team deserves the same quality of analysis that professional teams have. Kawkab AI makes that free, private, and offline.
