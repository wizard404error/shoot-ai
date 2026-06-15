# Kawkab AI — Honest Status Report (v0.3.1)

> **Last updated:** v0.3.1 (post-Claude review)
> **TL;DR:** Foundation is built. Almost everything needs real-world validation.

This document is brutally honest about what works and what doesn't. It was written after a thorough code review by Claude (see `kawkab-ai-review.md`).

---

## What We Claimed (Original PLAN.md)

- 500 tactical rules
- 500 training drills
- 6 phases over 10 months
- Production-ready by 12 months
- Freemium model with Stripe

## What We Actually Have (v0.3.1)

- **22 tactical rules** (4.4% of target)
- **19 training drills** (3.8% of target)
- **3 of 6 phases** "complete" (but with caveats)
- **0 paying users**
- **0 validation with real coaches**
- **0 confirmed accuracy metrics on amateur footage**

---

## Test Results (Real Numbers, Not Marketing)

### Pipeline Test (88s real football video, 22 players expected)

| Metric | Reported | Reality | Status |
|---|---|---|---|
| Frames processed | 2222 | 2222 | ✅ |
| Raw tracks (YOLO+BoT-SORT) | 160-191 | 191 | ⚠️ High |
| **Validated player tracks** | "all 22" | **91** | ❌ **4.1x too many** |
| Tracking fragmentation | not measured | 2.1x | ⚠️ Fair |
| Tracking quality | "good" | **"fair"** | ❌ |
| Formation detection | "4-3-3" | "4-3-3" | ✅ (but in pixels) |
| PPDA | "0.7" | "0.7" | ✅ |
| LLM report length | "4,000+ chars" | 4,050 chars | ✅ |
| LLM report quality | "excellent" | **untested with real coaches** | ⚠️ |

**The hard truth:** Our 91 "validated" tracks is 4x more than the 22 actual players. Tracking is not yet reliable enough to trust player-level stats (distance, speed, passes between specific players).

### What This Means for the User

- **Possession %**: Probably correct (team-level, not player-level)
- **Formation detection**: Approximately right (in pixel space, not meters)
- **Player distance**: **Unreliable** (track fragmentation breaks it)
- **Pass counts**: **Unreliable** (passes between non-existent "players")
- **LLM narrative**: Sounds impressive, may be hallucinating

---

## Critical Issues from Claude's Review

### ✅ Fixed in v0.3.1

1. **VRAM manager** — explicit memory budget tracking and CPU fallback
2. **qasync** — added to dependencies for Qt+asyncio bridge
3. **FAISS removed** — overkill for 22 rules, using simple dict
4. **Honest docs** — this STATUS.md exists

### ⚠️ Partially Fixed in v0.3.1

5. **Tracking fragmentation**: 7x → 2.1x. Still not "good" (target: 1.5x).
6. **Homography service**: Created. **Not yet used in analysis pipeline** (stats are still in pixel space).

### ❌ Not Fixed (Future Work)

7. **SoccerNet/tracklab integration** — need this for football-tuned ReID
8. **Lazy model loading** — 1.75 GB bundle is still huge
9. **Real coach validation** — zero feedback from real users
10. **Tunisia-compatible payment** — Stripe doesn't work
11. **Better documentation** — no user guide, no video tutorials

---

## Honest Capability Matrix

| Capability | Implementation | Validation | Production-Ready? |
|---|---|---|---|
| Player detection | ✅ | ✅ On broadcast | ⚠️ May fail on amateur |
| Player tracking | ✅ | ⚠️ "Fair" | ❌ No |
| Ball detection | ✅ | ⚠️ Sometimes | ❌ No |
| Possession % | ✅ | ⚠️ Untested | ❌ No |
| Distance covered | ✅ | ❌ Broken by fragmentation | ❌ No |
| Speed | ✅ | ❌ Broken by fragmentation | ❌ No |
| Formation | ✅ | ⚠️ Pixel-based | ⚠️ Approximately |
| xG / xT | ✅ | ❌ Pixel-based, no model | ❌ No |
| PPDA | ✅ | ⚠️ Heuristic | ⚠️ Approximately |
| Pass detection | ✅ | ⚠️ Heuristic | ❌ No |
| Tactical diagnosis | ✅ | ❌ Untested | ❌ No |
| LLM report EN | ✅ | ✅ Impressive output | ⚠️ Untested with coaches |
| LLM report AR | ✅ | ⚠️ Mixed | ❌ No |
| Training plan | ✅ | ❌ Untested | ❌ No |
| Clip extraction | ✅ | ✅ Works | ⚠️ Not in UI yet |
| Homography | ✅ | ⚠️ Manual only | ❌ No auto-detect |

---

## What Needs to Happen Next

### Priority 1: Make Tracking Work (Weeks 1-4)

- [ ] Integrate **SoccerNet/tracklab** for football-tuned ReID
- [ ] Switch to **boxmot** with **StrongSORT** for better identity preservation
- [ ] Add **team color clustering** (K-means on jersey color)
- [ ] Target: <30 tracks for 22 players, fragmentation <1.5x
- [ ] Add **pitch area filter** (reject detections outside pitch)

### Priority 2: Make Spatial Stats Work (Weeks 5-6)

- [ ] Build **UI for homography calibration** (click 4 corners)
- [ ] Integrate homography into analysis pipeline
- [ ] Convert all xT/xG/formation stats from pixel → meters
- [ ] Add **automatic keypoint detection** (SoccerNet camera calibration)

### Priority 3: Validate with Real Coaches (Weeks 7-12)

- [ ] Recruit 5 amateur coaches (Tunisia, Morocco, Algeria)
- [ ] Have them analyze 1 real match each
- [ ] Collect feedback on report quality, actionability
- [ ] Iterate based on feedback

### Priority 4: Reduce Bundle Size (Weeks 13-16)

- [ ] Implement **lazy model loading** (download on first run)
- [ ] Ship 50 MB launcher + 1.5 GB downloadable models
- [ ] Auto-update via GitHub Releases
- [ ] Code signing (Windows SmartScreen)

### Priority 5: Monetization (Weeks 17+)

- [ ] Research **Lemon Squeezy** (works in Tunisia)
- [ ] Set up legal entity if needed
- [ ] Beta program with 50 amateur coaches
- [ ] Freemium model: Free / Pro $19/mo / Academy $49/mo

---

## Knowledge Base Reality Check

We have **22 tactical rules** in YAML. They look comprehensive in PLAN.md but:

- Most rules were **synthesized from coaching knowledge**, not validated
- Rules fire on **specific event patterns** we don't yet detect
- Confidence thresholds are **educated guesses**
- 0 rules have been validated against real match outcomes

**Realistic timeline to 200 rules:** 12-18 months of part-time work, or 3-6 months of full-time work.

---

## Bottom Line

Kawkab AI is a **technical prototype** with a **strong architecture** and **real domain knowledge** in the knowledge base. It is **not a product**.

To become a product, we need:
1. **Better tracking** (SoccerNet/tracklab integration)
2. **Spatial calibration** (auto-homography)
3. **Real user validation** (5+ coaches)
4. **Bundle size reduction** (lazy loading)

Estimated time to a real v1.0: **6-9 months of focused work** with a small team.

**Until then, this is a research project that demonstrates the technical approach is viable.**

---

*This document is intentionally pessimistic. We need to know what doesn't work to fix it.*
