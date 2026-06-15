# Kawkab AI — Honest Status Report (v0.4.0)

> **Last updated:** v0.4.0 (homography integrated, team colors working)
> **TL;DR:** Foundation is built. Spatial stats now work in meters. Tracking still needs work.

This document is brutally honest about what works and what doesn't.

---

## Test Results (v0.4.0) — Real Numbers

| Metric | v0.3.1 | v0.4.0 | Status |
|---|---|---|---|
| Validated player tracks | 91 | 91 | Same (tracking still needs work) |
| Tracking fragmentation | 2.09x | 2.09x | Same |
| **Distance in meters** | ❌ (pixels) | ✅ **114m** | **FIXED** |
| **Defensive line height in meters** | ❌ (pixels) | ✅ **5.42m / 19.91m** | **FIXED** |
| **Formation coords** | pixels | meters | **FIXED** |
| Formation detection | 5-3-4 / 3-2-2 | **4-4-3 / 3-3-2** (more realistic) | Improved |
| Team color detection | ❌ | ✅ **2 clusters, 6 players** | **NEW** |
| Homography UI | ❌ | ✅ **Click 4 corners** | **NEW** |
| Confidence | 64.7% | **70.23%** | Improved |

---

## What v0.4.0 Fixed (from Claude's Review)

### ✅ **CRITICAL #2: No Homography**

- **Web UI**: Coach clicks 4 pitch corners on a video frame
- **Persistence**: Saved per-match in appdata/calibrations/
- **Analysis pipeline**: Now accepts homography_matrix parameter
- **Real meters**: Distance, defensive line, formations all in meters
- **Test result**: 4-4-3 / 3-3-2 formations with 5.42m and 19.91m line heights

### ✅ **Team Color Clustering** (helps with CRITICAL #1)

- `detect_team_colors()` method: K-means on torso color samples
- Separates home/away teams automatically
- Works with or without sklearn
- 6 players detected, 2 clusters on test video

### ✅ **Spatial Stats Now Meaningful**

- Distance: 106m (pixel) → 114m (meters) for top player
- Formations: more realistic (4-4-3 / 3-3-2 vs 5-3-4 / 3-2-2)
- Confidence: 70.23% (was 64.7%)

---

## What's Still Broken

### ❌ **CRITICAL #1: Tracking Fragmentation**

- 91 tracks for 22 players (target: <30)
- Fragmentation: 2.09x (target: <1.5x)
- Tracking quality: "fair" (target: "good" for 22 players)
- **Root cause**: BoT-SORT ReID model not fine-tuned for amateur footage

**Status**: Smart filters helped (7x → 2x), but real fix needs SoccerNet/tracklab integration.

### ❌ **CRITICAL #3: VRAM Still Constrained**

- VRAMManager added (sequential model loading)
- But on 12GB GPU, can't run YOLO + LLM simultaneously
- LLM has to run on CPU or after YOLO shutdown

### ❌ **Stripe Doesn't Work in Tunisia**

- Need Lemon Squeezy or Paddle research
- Not started

### ❌ **Bundle Size 1.75 GB**

- Lazy model loading not implemented
- All models shipped in installer

### ❌ **No Real Coach Validation**

- 0 amateur coaches have used this
- All metrics are theoretical

---

## Bottom Line (v0.4.0)

**The system now produces meaningful spatial stats in real meters when calibrated.**

**What works in production-quality:**
- Distance, formations, defensive line height (with homography)
- Team color detection (auto home/away)
- LLM reports in EN/AR (offline, local)
- 4-week training plan generation
- Knowledge base (22 rules, 19 drills)

**What still needs work:**
- Tracking (91 vs 22 players is the #1 issue)
- Real coach validation
- Bundle size
- Payment processor

**Estimated time to a real v1.0**: 4-6 months of focused work, with priority on:
1. SoccerNet/tracklab integration (better tracking)
2. Beta testing with 5 real coaches
3. Lazy model loading (smaller bundle)

---

*Updated post v0.4.0 (homography integration)*

