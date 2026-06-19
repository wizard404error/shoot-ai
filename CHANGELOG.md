# Changelog

All notable changes to Kawkab AI are documented here.

## v0.12.0 (2026-06-18) — All 25 audit gaps closed + production hardening

### New
- **25 audit gaps closed**: SetPieceService, GoalkeeperService, SubstitutionService, PositioningService, PlayerDevelopmentService, WorkloadService, ScoutingService, VideoReviewService, PeriodizationService, PitchDetector, calibration_v2.js, Arabic glossary, accessibility.css, profiler, strict mypy CI, API docs
- **Profiler wired** into analysis pipeline with frontend UI (stage breakdown, bottlenecks, p50/p95/p99)
- **core/observability.py**: Prometheus-style Counter, Gauge, Histogram with exposition format render
- **metrics_text bridge slot** for on-demand metrics retrieval
- **Plugin system**: KawkabPlugin ABC, PluginManager with entry-point discovery (group: `kawkab.plugins`)
- **TacticalReviewService**: LLM-powered per-section tactical analysis (formation, attack, defense, transitions, set pieces, key players, momentum)
- **.po-based i18n**: locales/en.po + locales/ar.po (77 keys), compile_i18n.py → JSON, JS loads via fetch()
- **PWA support**: manifest.json, service-worker.js (network-first cache)
- **E2E test scaffold**: 18 tests across observability, profiler, bridge slots, .po compilation, CI config
- **Coverage threshold 50%** in CI, badge row in README

### Changes
- PyInstaller spec updated: locales data, new hidden imports
- STATUS.md updated to v0.12.0
- CHANGELOG.md created

## v0.11.0 (2026-06-17) — 6 new services + 355 tests

### New
- SetPieceService (corners, free-kicks, throw-ins, threat, routines)
- GoalkeeperService (saves, xGOT, distribution, sweeps, crosses)
- SubstitutionService (xG-delta impact, rating, verdicts)
- PositioningService (off-ball runs, RunType, xT creation)
- PlayerDevelopmentService (per-player trends, slope, rolling stats)
- WorkloadService (ACWR, monotony, strain, injury risk)
- ScoutingService (opponent profiles, formation prefs, vulnerabilities)
- VideoReviewService (clips, annotations, tags, export/import)
- PeriodizationService (multi-week load, taper, congestion, macrocycle)
- PitchDetector (CV-based line detection via Hough)
- calibration_v2.js (8 drag handles, snap-to-grid, validation badge)
- Arabic glossary: docs/translations/ar.yml (70+ terms)
- accessibility.css + kawkab_polish.js (skip-link, focus-visible, high-contrast, RTL, ARIA)
- Profiler in utils/profiler.py (p50/p95/p99, bottleneck detection)
- API.md + per-service docs
- xG simple model (distance + angle), xT zone threat model
- analysis_service extensions: formations timeline, line-breaking passes, robust possession

## v0.10.2 (2026-06-16) — integration smoke tests

### New
- Integration pro-pipeline smoke tests
- 429 total tests (27× growth from initial 16)

## v0.10.1 (2026-06-15) — i18n + service tests

### New
- Arabic glossary tests
- 294 unit tests

## v0.10.0 (2026-06-14) — real-time streaming + UX polish

### New
- RealtimeService with ShotAlertRule, LowFpsAlertRule, LowConfidenceAlertRule
- ConsoleSubscriber, CallbackSubscriber
- accessibility.css (skip-link, focus-visible, high-contrast, reduced-motion, RTL)
- kawkab_polish.js (ARIA live, keyboard shortcuts, i18n dict, reduced-motion detection)
- Arabic glossary loader

## v0.9.0 (2026-06-10) — 9 native services, 8 external sources, 222 tests

### New
- **8 external data sources**: football-data.org, Bzzoiro, EasySoccerData, API-Football, TheSportsDB, StatsBomb, OpenFootball, RoboFlow Sports
- PsychologyService, FootballRulesService, CardDetectionService, WeatherService
- PoseAnalysisService (YOLO26-pose), MuJoCoBallService, FluidX3DService
- Advanced event detection, physical load, pressure metrics
- Multi-match analysis, data export, visualization, anomaly detection
- Quality scoring, LightGlue homography
- Batch processing, validation framework
- Professional analytics UI (player profiles, match comparison, export)
- PDF report, clip extraction, team swap, visualizations

## v0.5.5 (2026-05-28) — frame skip 3, shot detection, bugfixes

### Fixed
- Enhancement cache crash (wrong path reference)
- frame_skip=3 default (50 → 16.7 fps effective, ~0.75x realtime)
- Shot detection: ball velocity + homography-based, 22 events per 5min

## v0.5.4 (2026-05-26) — pitch-side home/away heuristic

### New
- Median pitch-x per cluster determines home (left) vs away (right)
- Falls back to larger-cluster heuristic

## v0.5.3 (2026-05-24) — hard 36 km/h cap, Kalman smoother

### New
- Hard 36 km/h speed cap (belt-and-suspenders)
- Kalman smoother infrastructure (not wired for fragmented highlights)

## v0.5.2 (2026-05-22) — cluster color logging

### New
- Log home/away BGR cluster colors for manual verification

## v0.5.1 (2026-05-20) — speed sanity caps

### Fixed
- dt correction (0.02s → 0.04s with frame_skip=2)
- 0.4m per-frame delta cap, max speed 36 km/h

## v0.5.0 (2026-05-18) — frame skipping + team colors

### New
- Frame skip parameter (1=full, 2=default, 3+)
- Real team color assignment via k-means clustering
- Formation detection with relaxed lifetime filter

## v0.4.3 (2026-05-15) — LLM guardrails

### New
- build_match_context(), is_clip flag
- System prompt forbids claiming results on short clips

## v0.4.2 (2026-05-12) — knowledge base

### New
- 30 tactical rules, 19 drills
- KnowledgeService with EN/AR text

## v0.4.1 (2026-05-10) — top-N filter

### Fixed
- Top-28 track filter achieves 'excellent' tracking quality

## v0.4.0 (2026-05-08) — homography UI

### New
- Camera calibration UI (4-click corner selection)
- Team color clustering

## v0.3.1 (2026-05-05) — foundation fixes

### Fixed
- Review issues from gap analysis
- STATUS.md, README updates

## v0.3.0 (2026-05-01) — initial desktop app

### New
- PySide6 + QWebEngineView desktop app
- YOLOv11 + BoT-SORT tracking
- Basic event detection (passes, shots)
- LLM coach report via Ollama
- PyInstaller build
