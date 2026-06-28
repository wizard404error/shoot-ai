# Sprint 7–11: Professional Football Analytics Platform

## Current State: 474 passing tests, 33 test files, ~23K lines of Python services, ~6K lines core analytics, ~6.5K lines JS frontend

---

## Sprint 7 — Analytics Accuracy + Model Training

| # | Task | Files | Effort | Priority |
|---|------|-------|--------|----------|
| 7.1 | **xG Trainer** — numpy-only logistic regression. Create `xg_trainer.py` with `batch_gradient_descent()`, `fit_from_events()`, `generate_synthetic_training_data()`, `save/load_coefficients()`. Update `EnhancedXgModel` with `load_trained(path)` classmethod. | `src/kawkab/core/xg_trainer.py` (new), `src/kawkab/core/xg_model.py` (edit), `tests/unit/test_xg_trainer.py` (new) | 2h | Critical |
| 7.2 | **xA Poisson Model** — Replace heuristic zone weights with Monte Carlo pass-to-shot sequence model. `compute_xa()` finds shots within 5s of each pass, weights by xG. Keep backward compat. | `src/kawkab/core/xa_model.py` (edit) | 1h | High |
| 7.3 | **Uncertainty Intervals** — `uncertainty.py` with bootstrap confidence bounds for xG/xA/PSxG. `bootstrap_metric(values, metric_fn, n_bootstrap=1000)` returning `{lower, upper, mean, std}`. | `src/kawkab/core/uncertainty.py` (new), `tests/unit/test_uncertainty.py` (new) | 1h | High |
| 7.4 | **Proper VAEP** — Replace zone-ratio VAEP with possession-phase survival model. `compute_vaep_survival()` uses Poisson goal arrivals per possession with pre/post action value deltas. | `src/kawkab/core/vaep.py` (rewrite), `tests/unit/test_vaep.py` (update) | 1.5h | High |
| 7.5 | **xT Frontend** — Bridge slot `get_xt_report`, frontend `loadXTReport()`, button `pro-xt-btn`, xT zone grid heatmap canvas (16x12), team summary, locale keys. | `src/kawkab/ui/bridge.py`, `src/kawkab/web/js/app.js`, `src/kawkab/web/js/app-charts.js`, `src/kawkab/web/index.html`, locale files | 1h | Critical |
| 7.6 | **EPV Module** — `epv.py` with `compute_zone_values()`, `compute_action_epv()`, `compute_possession_epv()`. Values each possession phase by zone scoring probability. | `src/kawkab/core/epv.py` (new), `tests/unit/test_epv.py` (new) | 1.5h | High |
| 7.7 | **Packing Passes** — `packing.py` with `compute_pass_packing()` counting opponents bypassed, `compute_penetration()` measuring territory gained. | `src/kawkab/core/packing.py` (new), `tests/unit/test_packing.py` (new) | 1h | Medium |
| 7.8 | **Set Piece xG** — Enhance `set_piece_analysis.py` with `compute_set_piece_xg()` using delivery zone weights and xT integration. | `src/kawkab/core/set_piece_analysis.py` (edit), `tests/unit/test_set_piece_analysis.py` (update) | 0.5h | Medium |

**Test target: 500+ tests**

---

## Sprint 8 — Test Coverage (18 uncovered services)

| # | Task | Effort | Lines |
|---|------|--------|-------|
| 8.1 | `test_advanced_event_detection_service.py` — 824 lines, largest uncovered | 1.5h | 824 |
| 8.2 | `test_llm_service.py` — 331 lines, used by narrative gen | 1h | 331 |
| 8.3 | `test_reasoning_service.py` — 424 lines | 1h | 424 |
| 8.4 | `test_pressure_metrics_service.py` — 345 lines | 0.5h | 345 |
| 8.5 | `test_visualization_service.py` — 318 lines | 0.5h | 318 |
| 8.6 | `test_training_plan_service.py` — 322 lines | 0.5h | 322 |
| 8.7 | `test_norfair_tracker.py` — 203 lines | 0.5h | 203 |
| 8.8 | `test_face_recognition_service.py` — 250 lines | 0.5h | 250 |
| 8.9 | `test_jersey_service.py` — 244 lines | 0.5h | 244 |
| 8.10 | `test_lightglue_homography_service.py` — 280 lines | 0.5h | 280 |
| 8.11 | `test_physical_load_service.py` — 242 lines | 0.5h | 242 |
| 8.12 | `test_knowledge_service.py` — 186 lines | 0.25h | 186 |
| 8.13 | `test_enhancement_service.py` — 201 lines | 0.25h | 201 |
| 8.14 | `test_audio_service.py` — 162 lines | 0.25h | 162 |
| 8.15 | `test_clip_service.py` — 158 lines | 0.25h | 158 |
| 8.16 | `test_tracking_metrics.py` — 144 lines | 0.25h | 144 |
| 8.17 | `test_vram_manager.py` — 152 lines | 0.25h | 152 |
| 8.18 | `test_easy_soccer_service.py` — 149 lines | 0.25h | 149 |
| 8.19 | Expand 10 thin tests (logging, psxg, heatmap, pass_flow, etc.) | 1h | — |
| 8.20 | Add hypothesis property tests to defensive_actions, pitch_control, vaep | 0.5h | — |
| 8.21 | Add stress test (100k events) to performance benchmarks | 0.5h | — |

**Test target: 580+ tests**

---

## Sprint 9 — Frontend Professionalization

| # | Task | Files | Effort |
|---|------|-------|--------|
| 9.1 | Add 6 missing frontend buttons: win probability, set pieces, pass flow, tactical periods, game state, season stats. Each needs: bridge slot (if missing), JS loader, HTML button, section, locale keys. | `bridge.py`, `app.js`, `index.html`, locale files | 1h |
| 9.2 | Split `setupEventListeners()` 168-line god function into 5 domain functions | `app.js` | 0.5h |
| 9.3 | Add `window.onerror` + `window.onunhandledrejection` handlers with toast | `app.js` | 0.25h |
| 9.4 | Add `removeEventListener` cleanup for all 69 addEventListener calls | `app.js` | 0.75h |
| 9.5 | Extract `createTeamSearch()` factory to deduplicate 3x data provider search code | `app-data-providers.js` | 0.5h |
| 9.6 | Add `aria-expanded` to collapsibles, fix keyboard gaps | `index.html`, `app.js` | 0.5h |
| 9.7 | Create missing PWA icons (192×192, 512×512) 1px SVG | — | 0.1h |
| 9.8 | Add CSP meta tag to index.html | `index.html` | 0.1h |

---

## Sprint 10 — Security + Infrastructure

| # | Task | Effort |
|---|------|--------|
| 10.1 | Remove hardcoded API key default in `config.py` (thesportsdb_api_key → None) | 0.1h |
| 10.2 | Add Pydantic validation models for complex JSON bridge inputs (feedback, issues, set piece events) | 0.5h |
| 10.3 | Add `pip-audit` to CI workflow | 0.25h |
| 10.4 | Document security architecture in `SECURITY.md` | 1h |
| 10.5 | Add SQLite backup mechanism | 0.5h |
| 10.6 | Wire crash reporting from config (Sentry placeholder in config.py exists but unused) | 0.5h |

---

## Sprint 11 — Professional UX Polish

| # | Task | Effort |
|---|------|--------|
| 11.1 | Add data table fallbacks for all canvases (a11y + reference) | 1h |
| 11.2 | Add coach report template system (structured PDF template beyond LLM narrative) | 1.5h |
| 11.3 | Add player comparison mode (side-by-side stats, 2-up) | 1h |
| 11.4 | Add match timeline visualization with interactive scrubbing | 1h |
| 11.5 | Improve empty states with icons + CTAs | 0.5h |
| 11.6 | Add keyboard shortcut cheat sheet modal | 0.5h |

---

## Summary

| Sprint | Focus | Files Changed | Tests Added | Total Tests |
|--------|-------|---------------|-------------|-------------|
| 7 | Analytics accuracy | ~20 files | ~80 | 554 |
| 8 | Test coverage | ~25 files | ~120 | 674 |
| 9 | Frontend polish | ~10 files | 0 | 674 |
| 10 | Security + infra | ~8 files | ~10 | 684 |
| 11 | UX polish | ~12 files | ~10 | 694 |
