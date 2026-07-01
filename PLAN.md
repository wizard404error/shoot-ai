# Kawkab AI — Next Build Plan (v0.12.0)

## Context
Project: Kawkab AI — AI Football Coach for Amateur Teams
Current version: v0.12.0
Goal: Continue building toward Phase 2/3 (Analyst → Detective)

> **Note:** Previous versions of this plan referenced v0.5.5/v0.6.0. As of
> v0.12.0 the project has shipped all 25 audit gaps closed, production
> hardening, 900+ tests, 57 services.

## What We Build Next

### 1. Match Type Detection + Kalman Smoother Integration
**Why:** Kalman smoother exists (v0.5.3) but is NOT wired into the main pipeline. STATUS.md says it "degrades on fragmented highlight reels" but would help full-match analysis. We need to detect match type and only enable Kalman for full matches.

**Implementation:**
- Add `match_type` inference to `CVService.process_video()` based on:
  - Duration >= 80 min → "full_match"
  - Duration < 20 min → "highlight"  
  - In between → "unknown"
  - Also consider fragmentation rate and avg track span
- Add `match_type` field to `MatchTrackData`
- Modify `AnalysisService._compute_player_stats()`:
  - When `match_type == "full_match"`, use `PlayerPositionSmoother` per track
  - When `match_type == "highlight"`, use existing raw delta cap approach
  - Log which method is used
- Update `Bridge.analyze_match()` to pass match_type
- Add `use_kalman` toggle to `AnalysisService.__init__`

### 2. Knowledge Base Expansion
**Why:** Current KB has ~30 rules + ~19 drills. PLAN.md targets 100 rules + 100 drills by Phase 3.

**Implementation:**
- Add 10 new tactical rules covering gaps:
  - Defensive: poor_pressing_shape, weak_aerial_defense, zonal_marking_gaps, defensive_third_errors
  - Transitions: slow_defensive_transition, poor_counter_pressing
  - Individual: midfielder_positioning, striker_pressing, winger_defensive_work_rate
  - Meta: goalkeeper_communication
- Add 5 new drills:
  - pressing_shape_8v8, defensive_transition_6v6, aerial_defense_circles, zonal_marking_game, counter_pressing_4v4

### 3. Update graphify after changes
- Run `graphify update .` or document the structural changes
- Verify new connections appear in graph

## Success Criteria
- [ ] Kalman produces smoother trajectories for full-match test videos
- [ ] Distance estimates improve for full matches (no broadcast-cut fragmentation)
- [ ] Highlight reels continue using existing cap-based approach (no regression)
- [ ] Knowledge base loads all new rules without errors
- [ ] All tests pass
- [ ] graphify updated to reflect new code structure

## Files to Modify
- `src/kawkab/services/cv_service.py` — match_type detection
- `src/kawkab/services/analysis_service.py` — Kalman integration
- `src/kawkab/ui/bridge.py` — pass match_type
- `src/kawkab/knowledge/tactics/*/` — new rules
- `src/kawkab/knowledge/drills/` — new drills
- `tests/` — add tests for new features
- `STATUS.md` — update with v0.6.0 changes
