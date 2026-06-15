# 🏆 Kawkab AI — The Ultimate Plan (v4.0)

> **The world's most advanced AI football coach for amateur teams.**

---

## 📌 Locked Decisions

| Decision | Choice |
|---|---|
| **Platform** | Desktop app (PySide6 + Python + embedded web UI) |
| **OS** | Windows (primary) |
| **GPU** | RTX 4070 (12GB VRAM) |
| **Distribution** | Single .exe via GitHub Releases |
| **Budget** | $0/month forever |
| **LLM** | Ollama local (Qwen 2.5 14B) |
| **Video Quality** | FFmpeg vidstab+hqdn3d always on, Real-ESRGAN/RIFE optional |
| **Languages** | Arabic + English (switchable) |
| **Tone** | Friendly coach voice |
| **Sport (V1)** | Football |
| **Audience** | Amateur & youth teams |
| **Architecture** | QWebChannel (no FastAPI) |
| **Jersey Numbers** | Auto-OCR from day 1 |
| **Accuracy** | Honest confidence indicators + manual correction UI |
| **Knowledge Base** | 500 rules + 500 drills (10 months) |

---

## 🎯 North Star Vision

> "Coach uploads yesterday's match. One hour later they get: *'You conceded 3 goals. 2 came from your left channel because your LB (Player 7) takes 2.4s longer to recover. Here's the video evidence and a 4-week drill plan to fix it.'*"

---

## 🏗️ Architecture

```
Kawkab AI Desktop (.exe)
│
├── PySide6 MainWindow
│   └── QWebEngineView (Vue 3 + Tailwind + TypeScript)
│       └── QWebChannel (JS ↔ Python bridge)
│           └── Service Layer (async Python)
│               ├── CVService (YOLO + BoT-SORT + ReID)
│               ├── AnalysisService (stats + patterns)
│               ├── ReasoningService (tactical diagnosis)
│               ├── KnowledgeService (500+ rules+drills)
│               ├── LLMService (Ollama + Qwen 2.5 14B)
│               ├── AudioService (Whisper + event detect)
│               ├── EnhancementService (Real-ESRGAN+RIFE)
│               └── StorageService (SQLite + FAISS)
│
├── GPU: RTX 4070 (CUDA via PyTorch, 12GB VRAM)
├── Storage: SQLite + FAISS + Local FS
├── LLM: Ollama + Qwen 2.5 14B (local) + Groq/Google (optional)
└── Distribution: PyInstaller + Inno Setup → GitHub Releases
```

---

## 🛠️ Tech Stack

| Layer | Tool |
|---|---|
| **App Shell** | PySide6 (Qt 6.6+) |
| **Web UI** | QWebEngineView + Vue 3 + Tailwind + TypeScript |
| **Backend** | Service layer (async Python) |
| **DB** | SQLite + SQLAlchemy 2.0 + FAISS |
| **Detection** | YOLOv11l (Ultralytics) |
| **Tracking** | BoT-SORT with ReID + GMC |
| **Field masking** | Adaptive Field Masking (SoccerNet) |
| **Jersey OCR** | YOLOv11 fine-tuned on jersey numbers |
| **Action spotting** | SoccerNet pre-trained models |
| **Event → SPADL** | socceraction (ML-KULeuven) |
| **Action valuation** | VAEP + xT (from socceraction) |
| **Pose (optional)** | Sports2D (davidpagnon) |
| **Graph analytics** | UnravelSports (GNN) |
| **Pitch viz** | mplsoccer + Kloppy |
| **Preprocessing** | FFmpeg (vidstab, hqdn3d, unsharp) |
| **Enhancement** | Real-ESRGAN + RIFE |
| **Knowledge Graph** | graphifyy (dev tool) |
| **Video → text** | graphifyy[video] (faster-whisper) |
| **Audio analysis** | faster-whisper + librosa |
| **LLM (default)** | Ollama + Qwen 2.5 14B |
| **LLM (optional)** | Groq / Google AI Studio |
| **Embeddings** | BGE-M3 (multilingual) |
| **AI dev tool** | graphifyy (skill installed) |
| **Packaging** | PyInstaller + Inno Setup |
| **Auto-update** | GitHub Releases API |
| **Crash reporting** | Sentry (5K events/mo free) |
| **Analytics** | Plausible (self-hosted) |
| **PDF export** | WeasyPrint |
| **Testing** | pytest + hypothesis |
| **CI/CD** | GitHub Actions (Windows runner) |

---

## 🧠 Knowledge Base Structure

```
src/kawkab/knowledge/
├── tactics/
│   ├── defensive/        # 150+ rules
│   ├── offensive/        # 150+ rules
│   ├── transitions/      # 100+ rules
│   └── individual/       # 100+ rules
├── drills/
│   ├── passing/          # 100+ drills
│   ├── pressing/         # 80+ drills
│   ├── transitions/      # 70+ drills
│   ├── finishing/        # 70+ drills
│   ├── defensive_shape/  # 80+ drills
│   ├── possession/       # 100+ drills
│   └── set_pieces/       # 50+ drills
└── mappings/
    └── problem_to_drill.yaml
```

**Timeline:**
| Month | Rules | Drills | Method |
|---|---|---|---|
| 1-2 | 100 | 150 | Semi-automated (graphify + LLM) |
| 3-4 | 200 | 250 | Semi-automated + manual |
| 5-6 | 300 | 350 | Manual + community |
| 7-8 | 400 | 450 | Community contributions |
| 9-10 | 500 | 500 | Full knowledge base |

---

## 🚀 6-Phase Roadmap

### **Phase 1: Foundation (Weeks 1–4)**
- PySide6 + QWebEngineView + QWebChannel
- YOLOv11l + BoT-SORT + ReID + Adaptive Field Masking
- Real-ESRGAN + RFFE (optional toggles)
- Auto jersey number OCR
- Basic stats: possession, distance, pass count, shots, tackles
- Video player with overlays
- Confidence indicators (🟢🟡🔴)
- Manual correction UI
- PDF export
- PyInstaller + Inno Setup

**Ship:** v0.1.0

---

### **Phase 2: The Analyst (Weeks 5–10)**
- Camera calibration (homography)
- Formation detection (k-means + GNN)
- Defensive line tracking
- Pressing intensity (PPDA)
- Pass networks (NetworkX + GNN)
- Event → SPADL converter
- xG/xT scoring (socceraction VAEP)
- Multi-match aggregator
- Player dashboard (radar charts)
- Player similarity finder (FAISS + BGE-M3)
- Audio analysis (Whisper + whistle detection)
- Set-piece detection

**Ship:** v0.2.0

---

### **Phase 3: The Detective (Weeks 11–20)** ⭐
- 50 tactical rules (top 20 amateur problems)
- Hypothesis testing engine
- Confidence scoring (Bayesian)
- Auto video clip extraction
- LLM report writer (scoped context via FAISS)
- Video evidence player
- Tactical knowledge graph (NetworkX)
- Validation with 5-10 amateur coaches
- Expand to 100 rules

**Ship:** v0.3.0

---

### **Phase 4: The Coach (Weeks 21–30)**
- 100 drills (curated, YAML)
- Mapping engine (problem → drills)
- Schedule generator (4-week plans)
- Adaptive plans (training days, squad size, equipment)
- Re-test mechanism
- Drill visualizations (SVG)
- Printable PDF plan
- Coach feedback loop
- Expand to 200 drills

**Ship:** v0.4.0

---

### **Phase 5: The Product (Weeks 31–40)**
- Polish UI (dark mode, animations)
- Multi-language UI (Arabic + English)
- Auto-update via GitHub Releases
- Performance tuning (8-min target)
- Beta program: 20-50 coaches
- Documentation + video tutorials
- Marketing site
- Expand to 200 rules + 300 drills
- Accuracy metrics dashboard
- Community contribution system

**Ship:** v1.0.0

---

### **Phase 6: Scale & Monetize (Weeks 41–52)**
- Freemium: Free (3 matches/mo), Pro $19/mo, Academy $49/mo
- Payment: Stripe
- Team management
- Parent/player portal
- Opponent analysis
- Recruitment tool
- Live in-game analysis
- Multi-camera support
- Expand to 300 rules + 400 drills
- Basketball support
- B2B licensing
- White-label

**Ship:** v2.0.0

---

## 📅 First 7 Days (Aggressive)

| Day | Tasks | Result |
|---|---|---|
| **1** | Install all tools, clone reference repos | Dev env ready |
| **2** | Set up project structure, build app shell | PySide6 + QWebChannel works |
| **3** | Video upload + FFmpeg preprocessing | Clean video ready |
| **4** | YOLOv11l + BoT-SORT + ReID + Field Masking | Players tracked |
| **5** | Jersey number OCR + basic stats | Numbers + stats |
| **6** | Dashboard UI + confidence indicators + correction UI | Full dashboard |
| **7** | PDF export + polish + ship v0.1.0 | **Demo shipped** |

---

## 🎯 Success Metrics

| Phase | Metric | Target |
|---|---|---|
| 1 | Time to first stats | <10 min |
| 1 | Player tracking accuracy | >80% |
| 1 | Jersey number accuracy | >80% |
| 2 | Formation detection | >85% |
| 2 | Event correction rate | <20% |
| 3 | Coach validation | 8/10 |
| 3 | Knowledge base | 100 rules |
| 4 | Drill relevance | 4.5/5 |
| 4 | Knowledge base | 200 drills |
| 5 | Beta retention | >80% |
| 5 | Knowledge base | 200 rules + 300 drills |
| 6 | Paying users | 100+ |
| 6 | MRR | $2K+ |

---

## 📚 Resource Master List

### Knowledge Base / Data
- **SoccerNet** (500+ matches) — github.com/SoccerNet
- **StatsBomb Open Data** — github.com/statsbomb
- **KLoppy** — github.com/PySport/kloppy
- **socceraction** — github.com/ML-KULeuven/socceraction
- **eddwebster/football_analytics** — github.com/eddwebster/football_analytics
- **withqwerty/reep** — github.com/withqwerty/reep
- **FPL-Core-Insights** — github.com/olbauday/FPL-Core-Insights
- **salimt/football-datasets** — github.com/salimt/football-datasets

### CV / Detection / Tracking
- **YOLOv11** — github.com/ultralytics/ultralytics
- **roboflow/sports** — github.com/roboflow/sports
- **SoccerNet/sn-gamestate** — github.com/SoccerNet/sn-gamestate
- **apiantonio/SoccerNet-tracking_AV2025-26** — github.com/apiantonio/SoccerNet-tracking_AV2025-26
- **SkalskiP/sports** — github.com/SkalskiP/sports
- **SportsLabKit** — github.com/AtomScott/SportsLabKit
- **Mostafa-Nafie/Football-Object-Detection** — github.com/Mostafa-Nafie/Football-Object-Detection

### Tactical Analysis
- **UnravelSports** — github.com/UnravelSports/unravelsports
- **Dato-Futbol/passing-networks** — github.com/Dato-Futbol/passing-networks
- **ggshakeR** — github.com/abhiamishra/ggshakeR
- **pldashboard** — github.com/tom-draper/pldashboard

### Pose / Biomechanics
- **Sports2D** — github.com/davidpagnon/Sports2D

### Video Enhancement
- **Real-ESRGAN** — github.com/xinntao/Real-ESRGAN
- **RIFE** — github.com/megvii-research/ECCV2022-RIFE
- **Video2X** — github.com/k4yt3x/video2x

### LLM & Knowledge Tools
- **graphifyy** — github.com/safishamsi/graphify
- **Ollama** — ollama.com
- **Qwen 2.5** — ollama.com/library/qwen2.5

### Distribution
- **PyInstaller** — pyinstaller.org
- **Nuitka** — nuitka.net
- **Inno Setup** — jrsoftware.org/isinfo.php

### Awesome Lists
- **moose-lab/awesome-sports-ai** — github.com/moose-lab/awesome-sports-ai
- **diegopastor/awesome-football-analytics** — github.com/diegopastor/awesome-football-analytics
- **JanVanHaaren/soccer-analytics-resources** — github.com/JanVanHaaren/soccer-analytics-resources

---

## 💰 $0 Budget (Confirmed)

| Need | Tool | Cost |
|---|---|---|
| IDE | VS Code | $0 |
| Python | Python 3.12 + uv | $0 |
| CV/ML libs | Ultralytics, SoccerNet, socceraction, OpenCV, mplsoccer | $0 |
| LLM | Ollama + Qwen 2.5 14B | $0 |
| Optional LLM | Groq / Google AI Studio (free tiers) | $0 |
| Knowledge graph | Graphify (open source, Ollama backend) | $0 |
| Video transcription | graphifyy[video] = faster-whisper (local) | $0 |
| Database | SQLite + FAISS | $0 |
| Video storage | Local FS | $0 |
| Icons/fonts | Lucide + Inter + Noto Sans Arabic | $0 |
| Code hosting | GitHub | $0 |
| CI/CD | GitHub Actions (2,000 min/mo free) | $0 |
| Distribution | GitHub Releases | $0 |
| Error tracking | Sentry (5K events/mo free) | $0 |
| **Total forever** | — | **$0/month** |

---

## ⚠️ Risk Matrix

| Risk | Severity | Mitigation |
|---|---|---|
| Phone video quality | 🟡 Medium | Adaptive Field Masking + FFmpeg + Real-ESRGAN + RIFE + honest confidence |
| CV accuracy | 🟡 Medium | YOLOv11l + ReID + correction UI + fine-tune on corrections |
| Knowledge base scope | 🟡 Medium | Semi-automation (graphify + LLM) + 10-month timeline + community |
| Solo dev burnout | 🟡 Medium | Ship Phase 1 in 1 week, celebrate wins, take breaks |
| Jersey number OCR | 🟢 Low | Manual confirmation UI, improves with corrections |
| socceraction integration | 🟢 Low | Dedicated SPADL converter, honest about amateur generalization |
| Timeline overruns | 🟢 Low | Aggressive but possible, ship early and often |
| Distribution size | 🟢 Low | Normal for AI apps, use compression |
| Competition | 🟢 Low | Amateur focus + knowledge base moat is defensible |
| Monetization | 🟢 Low | Freemium model, clear value proposition |

---

## 🏁 The Moat

> **No other tool does: "WHAT happened → WHY it happened → HOW TO FIX it → with video proof → audio analysis → auto jersey OCR → correction learning" for amateur teams at $0 cost.**

---

*Plan complete. Ready to build.*
