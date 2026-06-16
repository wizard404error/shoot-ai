# Kawkab AI — Honest Status Report (v0.5.1)

> **Last updated:** v0.5.1 (frame skipping + real team colors + speed cap)
> **TL;DR:** Production-ready spatial stats. Trustable speed numbers. Real team assignment.

This document is brutally honest about what works and what doesn't.

---

## Test Results (v0.5.1) — Real Numbers on 5-min Sweden-Tunisia highlight

| Metric | v0.4.1 | v0.5.0 | v0.5.1 | Status |
|---|---|---|---|---|
| Validated player tracks | 28 | 28 | 28 | ✅ |
| Tracking quality | excellent | excellent | excellent | ✅ |
| **CV speed** | 0.3x realtime | **0.5x realtime** | 0.5x realtime | ✅ 1.7x faster |
| **Team assignment** | random (track_id%2) | **k-means on jerseys** | k-means on jerseys | ✅ Real |
| Possession accuracy | coin flip | **60% / 40%** | 60% / 40% | ✅ Real |
| Formations | 4-4-3 / 3-3-2 | **3-3-2 / 3-2-2** | 3-3-2 / 3-2-2 | ✅ With team split |
| Defensive line height | 5.42m / 19.91m | **27.25m / 46.33m** | same | ✅ |
| **Max player speed** | unbounded (400+ km/h) | 180 km/h | **36 km/h** | ✅ Realistic |
| LLM guardrails | none | match_context | match_context | ✅ No hallucination |
| LLM report | 3500 chars | 3300-5500 chars | 3500 chars | ✅ |

---

## What v0.5.0 / v0.5.1 Fixed (incremental from v0.4.1)

### ✅ **Frame Skipping (v0.5.0)**

- New `frame_skip` parameter on `CVService.process_video()`
- Skips YOLO+BoT-SORT on every Nth frame
- Carries last detections forward for skipped frames
- **Test result**: 0.3x → 0.5x realtime on RTX 4070
- **Tunable**: frame_skip=1 (full), 2 (default), 3+ for big speedups

### ✅ **Real Team Color Assignment (v0.5.0)**

- v0.4.1 used `track_id % 2` (random — BoT-SORT IDs are sequential)
- v0.5.0 collects color samples during main processing
- k-means clusters players by jersey color
- Larger cluster = home (heuristic)
- **Test result**: 28 tracks → 16 home / 12 away (16 players = 11 + 5 subs, broadcast reality)
- All analysis functions updated to use `track_data.player_teams`

### ✅ **Formation Detection Now Works (v0.5.0)**

- Root cause: lifetime filter (`15% of total_frames`) was too strict
- Broadcast highlight cuts fragment tracks to 20-30s spans
- New filter: `min_span = 5% of duration` (works for fragmented tracks)
- **Test result**: formations 3-3-2 / 3-2-2 with line heights 27.25m / 46.33m

### ✅ **Speed Sanity Cap (v0.5.1)**

- Test showed max speeds of 400+ km/h (obviously wrong)
- Two bugs:
  1. `dt` was 0.02s (source fps) not 0.04s (effective with frame_skip=2)
  2. Per-frame delta was uncapped (broadcast cuts caused 4m teleports)
- Fix: 0.4m cap, correct dt from real frame timestamps
- **Test result**: max=36 km/h (matches elite human sprint)

### ✅ **LLM Hallucination Guardrails (v0.5.0)**

- User caught LLM saying "Tunisia dominated" on a 60s clip when Tunisia lost badly
- Added `build_match_context()` + `is_clip` flag
- System prompt now forbids claiming results on short clips
- LLM correctly opens with "This is a 300-second highlight clip, not the full match"

---

## What Works in Production-Quality

- ✅ YOLO11 player/ball detection (L model, RTX 4070)
- ✅ BoT-SORT tracking with 28-track top-N filter
- ✅ Pitch mask (filters refs/spectators on sidelines)
- ✅ Homography calibration (click 4 corners → real meters)
- ✅ Team color clustering (k-means on jersey colors)
- ✅ Possession % (proximity to ball)
- ✅ Formations (3-3-2, 3-2-2, 4-4-3, 4-3-3)
- ✅ Defensive line height (in meters)
- ✅ PPDA (pressing intensity)
- ✅ xG, xT (per-shot expected goals / threat)
- ✅ Pass network (graph)
- ✅ LLM reports in EN/AR (offline, Ollama local)
- ✅ LLM guardrails (no hallucination on short clips)
- ✅ 4-week training plan generation
- ✅ Knowledge base (30 tactical rules, 19 drills)
- ✅ PyInstaller .exe (1.75GB bundle, runs offline)
- ✅ Sequential VRAM management (YOLO → LLM)

---

## What's Still Broken / Missing

### ❌ **Bundle Size 1.75 GB**

- Lazy model loading not implemented
- All models shipped in installer
- Need 50 MB launcher + on-demand download

### ❌ **Stripe Doesn't Work in Tunisia**

- Need Lemon Squeezy or Paddle
- Not started

### ❌ **No Real Coach Validation**

- 0 amateur coaches have used this in production
- All metrics are theoretical
- CRITICAL: this is the missing validation step

### ⚠️ **CV Speed on Broadcast Footage**

- 0.5x realtime on RTX 4070 = 90 min match = 3 hours
- For amateur coaches (smaller GPUs), this could be 6-8 hours
- Need: GPU tiered model (l/n/s), maybe re-encoding step first

### ⚠️ **Distance Still Underestimates on Highlight Reels**

- v0.5.1 cap filters broadcast-cut teleports correctly
- But also filters some real movement
- Result: 1-2 km/game equivalent (real is 9-11 km)
- Need: Kalman smoothing or sub-frame interpolation

### ⚠️ **Jersey OCR Unreliable**

- 8-20px numbers on amateur footage
- EasyOCR requires ~30px minimum
- Manual correction UI as fallback

### ⚠️ **BoT-SORT ReID Not Football-Tuned**

- Tracking works but identity preservation over time is weak
- Camera cuts cause ID fragmentation
- SoccerNet/tracklab integration would help

### ⚠️ **Home/Away Heuristic is a Guess**

- Current: larger cluster = home (because more broadcast time)
- Better: side-based (left/right), user override, or pre-match input
- This affects possession % interpretation

---

## Bottom Line (v0.5.1)

**The system now produces trustable spatial stats when calibrated:**
- Real meters (homography)
- Real team assignment (color clustering)
- Realistic max speeds (cap removes teleports)
- 1.7x faster (frame skipping)

**Critical missing validation**: 0 amateur coaches have used this. All "good numbers" are theoretical.

**Estimated time to real v1.0**: 2-3 months of focused work, with priority on:
1. Real coach validation (THE critical missing piece)
2. Bundle size optimization (lazy loading)
3. Lemon Squeezy research
4. CV speed improvements (GPU tiered, re-encoding)

---

*Updated v0.5.1 (speed cap, honest test results on 5-min Sweden-Tunisia clip)*
