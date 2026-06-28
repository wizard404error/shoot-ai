# Sprint 1 — Quick Fixes + Performance

## 1A — Fix 4 Critical Bugs

### Bug 1: match_scripting.py double-append (line 137-147)
- **File**: `src/kawkab/core/match_scripting.py`
- **Problem**: Lines 138-147 duplicate the exact same ScriptedEvent appended at 127-136
- **Fix**: Delete lines 138-147 (the second duplicate append block)

### Bug 2: season_aggregator.py missing fields (line 277-284)
- **File**: `src/kawkab/core/season_aggregator.py`
- **Problem**: `SeasonReport` has no `total_passes` or `total_xg` fields. `compare_teams` uses `hasattr` which always fails, so `passes_a`/`passes_b` are always 0 and `xg_a` falls back to `total_goals * 0.12`
- **Fix**: 
  1. Add `total_passes: int = 0` and `total_xg: float = 0.0` fields to `SeasonReport` dataclass (line 87-97)
  2. Update `to_dict()` to include them (line 99-106)
  3. In `aggregate_team_season`, accumulate `total_passes` from `passes_attempted` across all players and `total_xg` from events

### Bug 3: fatigue_model.py double substitutions (line 97-106 + 136-142)
- **File**: `src/kawkab/core/fatigue_model.py`
- **Problem**: `substitutions_list` is populated in BOTH the initial `for ev` loop (lines 97-106) AND the second pass (lines 136-142) for `type == "substitution"` events
- **Fix**: Remove lines 136-142 (the duplicate substitution block in the second conditional)

### Bug 4: xa_model.py zone formula wrong (line 106)
- **File**: `src/kawkab/core/xa_model.py`
- **Problem**: `abs(x - pitch_length / 2)` maps BOTH halves to the same attacking zone, overestimating xA for deep passes
- **Fix**: Change to `atk_x = x if x > self.pitch_length / 2 else self.pitch_length - x` to only mirror passes in the defensive half

## 1B — PPDA Pressing Metric

### New function in defensive_actions.py
- **File**: `src/kawkab/core/defensive_actions.py`
- Add: `def compute_ppda(events: list[dict], team: str) -> dict` 
  - Count defensive actions (tackles, interceptions, fouls, pressures) in attacking 60% of pitch
  - Count opponent passes in same area
  - PPDA = opponent_passes / defensive_actions
  - Return `{"ppda": float, "defensive_actions": int, "opponent_passes": int}`
- Add: `def compute_ppda_both_teams(events: list[dict]) -> dict`
  - Returns PPDA for both teams

### Bridge slot + frontend
- **File**: `src/kawkab/ui/bridge.py`
- Add `@Slot(int, result=str)` async `get_ppda_report(self, match_id)` calling `compute_ppda_both_teams`
- **File**: `src/kawkab/web/js/app.js`
- Add `loadPPDA()` + `renderPPDA()` following existing pro-analytics pattern
- **File**: `src/kawkab/web/index.html`
- Add `#ppda-section` pro-card + `#pro-ppda-btn` in button panel

## 1C — Pass Network Improvements

### Betweenness centrality
- **File**: `src/kawkab/core/pass_network.py`
- Add BFS-based betweenness centrality computation
- Add `compute_betweenness(self, team: str) -> dict[int, float]` method
- Include in `to_team_report()` output

### Fix density formula
- **File**: `src/kawkab/core/pass_network.py` line ~132
- Change `n * (n - 1)` to use actual player count instead of hardcoded 11

### Edge weighting by xT
- Add optional xT edge weight parameter to `build()` method
- Store per-edge xT added value

## 1D — xT Resolution Increase

### Grid expansion
- **File**: `src/kawkab/core/xt_model.py`
- Change default grid from `rows=5, cols=4` to `rows=16, cols=12`
- Update transition matrix dimensions accordingly
- Add γ discount factor (default 0.9) to power iteration

## 1E — Video Overlay Performance

### Rate-limit bridge calls
- **File**: `src/kawkab/web/js/app.js` — `setupVideoOverlay` function
- Change timeupdate handler from 100ms to 200ms (5fps)
- Add `_pendingOverlayFrame` tracking to cancel stale requests

## 1F — Heatmap Rendering Optimization

### Replace pixel-shader rendering
- **File**: `src/kawkab/web/js/app.js`
- `renderHeatmapCanvas`, `renderDefensiveHeatmap`, `renderPressureHeatmap`
- Replace nested ImageData pixel loops with `ctx.fillRect` per cell
- Use offscreen canvas + nearest-neighbor scaling for smooth output

---

# Sprint 2 — Analytics Core Overhaul

## xG Model Rebuild with XGBoost

### New: xg_trainer.py
- **File**: `src/kawkab/core/xg_trainer.py` (new)
- Load StatsBomb open data (free 10k+ matches)
- Feature engineering: distance, angle, GK distance, GK angle, shot placement (x/y in goal), preceding action type, body part, big chance flag, rebound, fast break, one-on-one, through-ball assist, cross assist
- Train XGBoost classifier (n_estimators=500, max_depth=6)
- Serialize model to `models/xg_v2.json` via pickle/json

### Update xg_model.py
- New `XGBoostXgModel` class that loads trained model
- Keep legacy `ExpectedGoalsModel` as fallback
- `compute_xg()` with all new features
- `compute_match_xg()` aggregates per-team

## Win Probability Monte Carlo

### Rewrite win_probability.py
- Replace Elo model with xG Monte Carlo simulation
- `simulate_match(home_xg, away_xg, n_sims=10000)` — Poisson simulation for each team
- Compute home_win_pct, draw_pct, away_win_pct from simulation counts
- Dynamic updates: re-simulate after each goal using remaining time and remaining xG
- Return `WinProbabilityReport` with `timeline: list[dict]` (minute, home_pct, draw_pct, away_pct)

## Formation Detection Overhaul

### Rewrite formation_analysis.py
- Use k-means clustering on average player positions (not x-sorted thirds)
- Cluster into 3 groups (defenders, midfielders, forwards) using k-means with k=3
- Recognize specific formations: 4-3-3, 4-2-3-1, 4-4-2, 3-4-3, 3-5-2, 5-3-2, 4-1-4-1
- Add width/depth ratio as tactical indicator
- Add defensive line height, midfield line height, forward line height

---

# Sprint 3 — Frontend + Infrastructure

## i18n Consolidation

### Unified translation system
- **File**: `src/kawkab/web/js/i18n.js` (new)
- Single `t(key)` function that reads from JSON locale files
- `data-i18n` attribute processor that covers 100% of text elements
- Merge `app.js` `t()` and `kawkab_polish.js` `setLang()` into one
- **File**: `src/kawkab/web/locales/en.json` — add all missing keys (100+)
- **File**: `src/kawkab/web/locales/ar.json` — add all missing keys (100+)

### Applying i18n
- Add `data-i18n` to all: benchmark-section titles, pro-analytics buttons (14+), canvas labels, timeline filter, comparison/export/quality dropdowns, calibration toolbar, all "No data" messages, error toasts

## app.js Refactor

### Extract generic patterns
- `genericCheckStatus(name, bridgeMethod, controlsId)` — replaces 18x `checkXxxStatus()`
- `genericTeamSearch(setupFn, searchFn, ...)` — replaces 4x nearly identical search setups
- `proAnalyticsLoader(name, bridgeMethod, skeletonId, sectionId, renderFn)` — replaces 7+ load functions
- `genericHeatmapRenderer(canvasId, dataKey)` — replaces 3x heatmap renderers

## StorageService Exception Handling

### Replace asserts
- **File**: `src/kawkab/services/storage_service.py`
- Replace all 41 `assert self._conn is not None` with `raise StorageError("...")`
- Add `StorageError` exception class
- Wrap every DB method in try/except with `self._conn.rollback()` on failure
- Add input validation (match_id > 0, required keys present)
- Add WAL mode: `PRAGMA journal_mode=WAL`
- Add batch-size chunking (1000 rows per executemany)
- Add `__aenter__`/`__aexit__` for async context manager

---

# Sprint 4 — New Analytics Modules

## VAEP Module

### New: vaep.py
- **File**: `src/kawkab/core/vaep.py` (new)
- Implement VAEP framework using socceraction's SPADL pipeline
- State value function using xT grid (from xt_model.py)
- Transition modeling: for each action, compute ∆P(scoring) and ∆P(conceding)
- Action value = ∆P(scoring) - ∆P(conceding)
- Compute per-player VAEP totals

### Wire to export
- SPADL export already exists in `export_converters.py` — use as input

## xA Gradient-Boosted Model

### New: xa_model_v2.py
- **File**: `src/kawkab/core/xa_model.py` (replace compute logic)
- Add XGBoost-based xA model
- Features: pass length, angle, receiver movement, defensive density (number of defenders within 5m), pressure, body part, pass type, zone
- Train on StatsBomb data or use heuristic approximation

## Set Piece Analysis

### New: set_piece_analysis.py
- **File**: `src/kawkab/core/set_piece_analysis.py` (new)
- Corner analysis: delivery type (in-swinging, out-swinging, short), threat scoring, attacking/defending organization, shots from corners
- Free kick analysis: direct vs indirect, wall placement, delivery quality
- Throw-in analysis: retention rates, progression from throw-ins

## Chart.js Integration

### Replace raw canvas
- **File**: `src/kawkab/web/index.html` — add Chart.js CDN or vendor file
- **File**: `src/kawkab/web/js/app.js`
- Momentum → Chart.js line chart with gradient fill
- Win probability → Chart.js stacked area (home/draw/away)
- xG timeline → Chart.js with goal event annotations
- Pass flow → canvas remains (pitch overlay needed)

---

# Sprint 5 — Test Coverage

## CVService Tests
- **File**: `tests/unit/test_cv_service.py` (new, ~300 lines)
- `detect_frame`: filtering, confidence thresholds, bbox area, pitch mask
- `process_video`: frame skip, track filtering, top-N truncation, quality assessment
- `_compute_pitch_mask`: valid/invalid points
- `_get_dominant_color`: color extraction
- `_cluster_team_colors`: k-means clustering
- `swap_teams`: team color swap

## StorageService Comprehensive Tests
- **File**: `tests/unit/test_storage_service.py` (expand from 85→400 lines)
- All 41 methods including: bulk operations (1000+ events, bad event in batch), corrections, reports, benchmarks, validation results, feedback, issues, clips, playlists, player profiles
- Edge cases: corrupt DB, concurrent writes, missing required fields
- Error paths: uninitialized service, invalid match_id, DB locked

## External API Tests
- **File**: `tests/unit/test_api_external_services.py` (new, ~200 lines)
- Mock httpx for all 7 API services
- Test: rate limiting, timeouts, HTTP 429, empty responses, malformed JSON

---

# Sprint 6 — Polish + Accessibility

## RTL Coverage
- Apply `withRtlTransform` to all remaining canvases (16+)
- Audit SVG/HTML for hardcoded directional assumptions
- Add RTL transform to calibration SVG pitch preview

## Memory Leaks
- Clear `ballTrailPoints` on overlay disable
- Pause matter.js engine when sandbox section is hidden
- Cancel stale bridge promises when new match loaded

## Accessibility
- Add Enter/Space keydown handler to collapsible `.pro-card h3`
- Implement focus trap for GPU info panel, edit-event modal
- Darken `--text-muted` from `#94a3b8` to `#7e8ea8`
- Add `aria-label` to all canvases
- Make canvas tooltips `aria-hidden`

## Narrative Generation
- Wire existing LLM infrastructure (`llm_service.py`) to generate match summaries
- New bridge slot: `generate_match_narrative(match_id, language)`
- Frontend display in match summary section
- Prompt: "Generate a 3-4 sentence match summary from these events: {events}"

## Positional Benchmarks
- **File**: `src/kawkab/core/benchmarks.py`
- Add positional filtering to percentile computation
- Group players by position (CB, FB, CM, Winger, ST)
- Compare within positional group instead of whole squad
