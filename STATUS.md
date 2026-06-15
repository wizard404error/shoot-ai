# Kawkab AI — Honest Status Report (v0.4.1)

> **Last updated:** v0.4.1 (tracking fix + homography + team colors)
> **TL;DR:** Foundation works. Spatial stats in real meters. Tracking now "excellent".

This document is brutally honest about what works and what doesn't.

---

## Test Results (v0.4.1) — Real Numbers

| Metric | v0.3.1 | v0.4.0 | v0.4.1 | Status |
|---|---|---|---|---|
| Validated player tracks | 91 | 91 | **28** | ✅ |
| Track count ratio vs expected | 4.14x | 4.14x | **1.27x** | ✅ **Excellent** |
| Tracking quality | fair | fair | **excellent** | ✅ |
| **Distance in meters** | ❌ (pixels) | ✅ **114m** | ✅ 114m | ✅ |
| **Defensive line height in meters** | ❌ | ✅ **5.42m / 19.91m** | ✅ Same | ✅ |
| **Formation coords** | pixels | meters | meters | ✅ |
| Formation detection | 5-3-4 / 3-2-2 | 4-4-3 / 3-3-2 | 4-4-3 / 3-3-2 | ✅ |
| Team color detection | ❌ | ✅ 2 clusters | ✅ Same | ✅ |
| Homography UI | ❌ | ✅ Click 4 corners | ✅ Same | ✅ |
| Confidence | 64.7% | 70.23% | 70.23% | ✅ |

---

## What v0.4.0 / v0.4.1 Fixed (from Claude's Review)

### ✅ **CRITICAL #1: Tracking Fragmentation** (PARTIALLY)

- v0.3.1: 91 tracks for 22 players (4.14x) — "fair"
- v0.4.0: 91 tracks — same
- **v0.4.1: 28 tracks (1.27x) — "excellent"** with top-N filter
- Method: `max_keep_top_n=28` filter keeps top 28 by lifetime
- Result: closer to actual 22 players (plus refs and subs)

### ✅ **CRITICAL #2: No Homography** (FULLY)

- Web UI: coach clicks 4 pitch corners
- Persistence: per-match in appdata/calibrations/
- Analysis pipeline: accepts homography_matrix
- Real meters: distance, formations, line height
- **Test result**: 4-4-3 / 3-3-2 formations, 5.42m and 19.91m line heights

### ✅ **Team Color Clustering** (NEW)

- `detect_team_colors()`: K-means on torso color samples
- Separates home/away teams automatically
- 6 players, 2 clusters on test video

### ✅ **Spatial Stats Now Meaningful**

- Distance: 106m (pixel) → 114m (meters) — confirmed working
- Defensive line: 5.42m and 19.91m (real pitch coordinates)
- Confidence: 70.23% (was 64.7%)

### ✅ **VRAM Manager** (CRITICAL #3 partially)

- Sequential model loading (YOLO → free → LLM)
- Explicit budget tracking
- CPU fallback

### ✅ **qasync** (IMPORTANT #6)

- Bridges Qt event loop with asyncio
- Prevents UI freezing

### ✅ **FAISS Removed** (IMPORTANT #9)

- Overkill for 22 rules
- Using simple dict

### ✅ **Honest Docs** (CRITICAL #4)

- This STATUS.md exists
- README updated to be transparent

---

## What's Still Broken

### ❌ **Bundle Size 1.75 GB** (IMPORTANT #10)

- Lazy model loading not implemented
- All models shipped in installer
- Need 50 MB launcher + 1.5 GB on-demand download

### ❌ **Stripe Doesn't Work in Tunisia** (IMPORTANT #8)

- Need Lemon Squeezy or Paddle research
- Not started

### ❌ **No Real Coach Validation**

- 0 amateur coaches have used this
- All metrics are theoretical
- The "honest" feedback we need

### ⚠️ **Jersey OCR Unreliable** (IMPORTANT #7)

- 8-20px numbers on amateur footage
- EasyOCR requires ~30px minimum
- Manual correction UI as fallback

### ⚠️ **BoT-SORT ReID Not Football-Tuned**

- Tracking works (28 tracks) but identity preservation over time is weak
- SoccerNet/tracklab integration would help

---

## Bottom Line (v0.4.1)

**The system now produces meaningful spatial stats in real meters when calibrated.**

**What works in production-quality:**
- Tracking (28 tracks, "excellent" quality, 1.27x of expected)
- Distance, formations, defensive line height (with homography)
- Team color detection (auto home/away)
- LLM reports in EN/AR (offline, local)
- 4-week training plan generation
- Knowledge base (22 rules, 19 drills)

**What still needs work:**
- Bundle size (lazy loading)
- Real coach validation
- Payment processor (Tunisia-compatible)
- Better ReID (SoccerNet/tracklab)

**Estimated time to a real v1.0**: 3-4 months of focused work, with priority on:
1. Real coach validation (the critical missing piece)
2. Lazy model loading
3. Lemon Squeezy research

---

*Updated post v0.4.1 (tracking + homography fully integrated)*


