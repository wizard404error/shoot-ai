# Kawkab AI API Reference

This is the API reference for Kawkab AI's Python service layer. It
covers every public class and function intended for use by application
code, plugins, and the WebBridge.

## Module layout

```
kawkab
├── services/        Async, dependency-injectable domain services
│   ├── cv_service                 Computer-vision pipeline (YOLO + tracker)
│   ├── analysis_service           xG, xT, possession, formations, line-breaks
│   ├── positioning_service        Off-ball run analysis
│   ├── player_development_service Per-player trend tracking
│   ├── workload_service           ACWR, monotony, strain, injury risk
│   ├── scouting_service           Pre-match opponent profiles
│   ├── video_review_service       Frame-accurate clips + annotations
│   ├── pitch_detector             CV-based pitch line detection
│   ├── homography_service         Pitch-to-pixel mapping + validation
│   ├── setpiece_service           Corners, free kicks, throw-ins
│   ├── goalkeeper_service         Saves, xGOT, distribution
│   ├── substitution_service       xG-delta impact, ratings
│   ├── possession_service         Chains, counter-press, touches
│   ├── psychology_service         Momentum, score-state, late-game
│   ├── football_rules_service     IFAB Laws reference + classifier
│   ├── card_detection_service     Visual+audio+tactical card detection
│   ├── weather_service            Manual + Open-Meteo + video inference
│   ├── realtime_service           Streaming analysis + alert rules
│   ├── llm_service                Ollama wrapper (Qwen 2.5 14B)
│   ├── reasoning_service          LLM-driven tactical diagnosis
│   ├── knowledge_service          YAML drill/tactic/rule loader
│   ├── storage_service            SQLite persistence
│   ├── enhancement_service        Video upscaling + denoising
│   ├── physical_load_service      HIR, sprint, distance per player
│   ├── pressure_metrics_service   PPDA, compactness
│   └── mujoco_ball_service        Analytical ball physics
├── utils/                          Pure-function algorithm ports
│   ├── kabsch                     Rigid alignment
│   ├── hungarian                  O(n³) assignment
│   └── spatial_hash               2D/3D spatial bucketing
├── web/                            Browser-side assets
│   ├── js/kawkab_animations.js    Popmotion wrapper
│   ├── js/kawkab_polish.js         ARIA, i18n, keyboard shortcuts
│   ├── js/tactical_sandbox.js     matter.js formation sandbox
│   ├── css/main.css               Main stylesheet
│   └── css/accessibility.css      a11y / RTL / reduced-motion
└── migrations/                     SQL schema migrations
```

## Quick start

```python
import asyncio
from kawkab.services.cv_service import CVService
from kawkab.services.analysis_service import AnalysisService

async def analyze_video(path):
    cv = CVService()
    await cv.initialize()
    analysis = AnalysisService()
    track_data = await cv.process_video(path)
    report = await analysis.analyze_match(track_data)
    return report

asyncio.run(analyze_video("match.mp4"))
```

## Service index

| Service | Purpose | Async |
|---|---|---|
| CVService | Detection + tracking | yes |
| AnalysisService | xG, xT, formations, line-breaks, attribution | yes |
| PositioningService | Off-ball run analysis | no |
| PlayerDevelopmentService | Per-player trends | no |
| WorkloadService | ACWR, monotony, injury risk | no |
| ScoutingService | Pre-match opponent report | no |
| VideoReviewService | Clips, annotations, tags | no |
| PitchDetector | CV-based calibration guess | no |
| HomographyService | Pixel↔pitch transform | no |
| SetPieceService | Corners, free kicks | no |
| GoalkeeperService | Saves, xGOT | no |
| SubstitutionService | xG-delta impact | no |
| PossessionService | Chains, counter-press | no |
| PsychologyService | Momentum, score-state | no |
| FootballRulesService | IFAB Laws + classifier | no |
| CardDetectionService | Card detection (multi-source) | no |
| WeatherService | Weather impact | no |
| RealtimeService | Live streaming + alerts | yes |
| LLMService | Ollama LLM wrapper | yes |
| ReasoningService | Tactical diagnosis | yes |
| KnowledgeService | YAML rule loader | no |
| StorageService | SQLite | yes |
| EnhancementService | Video upscaling | yes |
| PhysicalLoadService | HIR, sprints | yes |
| PressureMetricsService | PPDA, compactness | yes |
| MuJoCoBallService | Ball physics | yes |

See `services/` for full per-service API.
