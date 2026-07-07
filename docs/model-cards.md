# Model Cards

## xG Model (xg_model.py)

**What it does** — Predicts the probability that a shot results in a goal using logistic regression. Two variants: legacy (`compute_xg`) and enhanced (`EnhancedXgModel` with GK distance, rebound, big chance features).

**Input features**
- `distance_m` — shot distance in meters (0–55, clamped ≥0.5)
- `angle_deg` — shot angle in degrees (central=0, side>35)
- `body_part` — `right_foot`, `left_foot`, `head`
- `shot_type` — `open_play`, `volley`, `half_volley`, `free_kick`, `penalty`
- `assist_type` — `standard`, `through_ball`, `cross`
- `is_one_on_one` — attacker through on goal
- `is_pressed` — defender within press distance
- `is_rebound` — *(enhanced)* shot following a save
- `is_big_chance` — *(enhanced)* clear-cut opportunity
- `gk_distance_m` — *(enhanced)* distance to goalkeeper at shot time

**Model type** — Logistic regression (heuristic coefficients, not fitted on training data). Logit = intercept + Σ(βᵢ·xᵢ), probability = 1/(1 + exp(−logit)). Penalty shots return fixed 0.76.

**Training data** — Coefficients hand-calibrated to StatsBomb-like shot distributions. Not trained on the project's own event data. The `load_trained()` class method can load fitted coefficients from a JSON file produced by `xg_trainer.py`.

**Known limitations**
- Heuristic coefficients — not optimised against a real dataset for this project
- No shot placement direction (post vs corner), no defender positions beyond press flag
- GK distance requires tracking data or annotated events
- Rebound detection needs a temporal window (≤3s after save)
- No contextual features (scoreline, time, competition)

**Tested range**
- Distance: 0.5–55 m
- Angle: 0–90°
- All body part / shot type combinations
- 29 unit tests coverage

**Failure modes**
- Missing coordinates → falls back to defaults (18 m, 30°)
- Zero or negative distance → clamped to 0.5 m
- `NaN`/`Inf` logit → returns 0.0
- Penalty flag always returns 0.76 regardless of other features
- Wide-angle shots (from_side=True) get a fixed penalty

---

## xT Model (xt_model.py)

**What it does** — Computes the expected threat (scoring probability) of each pitch zone by solving a transition matrix from passes and carries. Action value = end-zone xT − start-zone xT.

**Input features**
- Start zone (row, col) derived from (start_x, start_y)
- End zone (row, col) derived from (end_x, end_y)
- Action type: `pass` or `carry`
- Completion status (failed passes mirror to opponent zone)

**Model type** — Grid-based value iteration (power method). 20×32 grid (640 zones) on a 105×68 m pitch. Discount factor γ=0.9, 100 iterations max, convergence threshold 1×10⁻⁶.

**Training data** — Transition matrix built from actual match events. Zone scoring rate (z_e) = goals / possessions in zone. The `build_transition_matrix()` method ingests event dicts.

**Known limitations**
- No off-ball movement (only accounts for completed actions)
- Failed passes mirror to opponent zone — approximation, not ball-recovery probability
- Uniform discount factor — no per-zone or per-team variability
- Grid resolution fixed at init (default 20×32)
- Requires minimum event volume per zone for reliable transition estimates
- No contextual adjustment for scoreline, time, or team strength

**Tested range**
- Grid sizes: 16×12, 20×32
- Events per match: 100–3,000
- 8 unit tests + 157 extended analytical tests

**Failure modes**
- Empty event list → all zeros
- Missing coordinates → default to (0, 34)
- No shots in a zone → z_e = 0, zone valued only through transitions
- No pass/carry events → returns z_e matrix (no transition value)

---

## VAEP (vaep.py)

**What it does** — Values each event by the change in goal probability for both teams. Uses possession-phase survival model with Poisson goal arrivals and spatiotemporal features (player-relative distance/velocity, teammate/opponent density).

**Input features**
- Event position (x, y) zoned into 16×12 grid
- Event type: shot, pass, carry, dribble, tackle, interception, etc.
- Team, timestamp, is_goal flag
- *Derived features*: number of defenders ahead, teammates nearby (~15 m), speed of attack (avg gap over last 3 possession events), through-ball flag, space behind flag

**Model type** — Possession-phase survival model with Laplace-smoothed Poisson rates. Per-zone attack and defend rates estimated from event data. Survival decay factor = 0.85 per second. Lookahead window = 10 s.

**Training data** — Poisson rate tables estimated from match events with Laplace smoothing (α=0.01, β=0.1). No external training dataset; rates are match-specific.

**Known limitations**
- Requires accurate event type classification and team attribution
- No tracking data integration for true player positions — uses proxied features from previous events
- Possession phase identification is heuristic (event-type transitions)
- Poisson assumption: goal arrivals are independent and rate-constant within each zone
- Small event counts per zone produce unreliable rate estimates despite Laplace smoothing

**Tested range**
- Events per match: 10–3,000
- Lookahead: 1–30 s
- 26 VAEP tests + 51 correctness/property-based tests

**Failure modes**
- Empty events → empty result list
- Single event → no possession phases → PID = −1 for all
- Missing team → defaults to "home"; missing x/y → defaults to pitch centre
- All events same team → one possession phase

---

## Pitch Control (pitch_control.py, ball_physics_pitch_control.py)

**What it does** — Computes which areas of the pitch each team controls. Three models: Voronoi tessellation (`VoronoiPitchControl`), velocity-weighted soft assignment (`WeightedPitchControl`), and ball-physics trajectory simulation (`BallPhysicsPitchControl` — player arrival times with RK4 ball trajectory).

**Input features**
- Home and away player positions (x, y) — up to 11 per side
- Ball position (x, y) — optional
- Player velocities (vx, vy) — optional, default zero
- Player max speed and acceleration — configurable (default 7 m/s, 3 m/s²)
- Ball speed: kicked (20 m/s) or rolling (10 m/s)
- Grid resolution: 30×46 (default per model)

**Model type**
- *Voronoi*: hard assignment — nearest player owns the grid cell
- *Weighted*: soft Gaussian assignment — σ = v_max × τ (time horizon 2 s)
- *Ball-physics*: player arrival time = reaction (0.3 s) + kinematic travel distance, ball arrival time = distance / ball speed. Disputed zones where ball arrives first.

**Training data** — None required. All parameters are physical constants and configurable.

**Known limitations**
- No tactical context (pressing traps, zonal blocks, offside line)
- Voronoi ignores player speed/acceleration
- Weighted model uses isotropic Gaussian — no directional influence
- Ball-physics model simplified (no air resistance, spin, bounce)
- No goalkeeper-specific positioning model

**Tested range**
- Players per side: 0–11
- Grid: 30×46, custom resolutions
- Multiple frames per match
- 22 pitch control + 19 ball physics tests

**Failure modes**
- No players → 50/50 split with 0% disputed
- All players at same position → large disputed areas via ball-physics
- Missing ball → no disputed classification (ball-physics)
- NaN positions → broadcast to all neighbours

---

## Win Probability (win_probability.py)

**What it does** — Computes minute-by-minute win/draw/loss probabilities using Monte Carlo simulation. Samples from Poisson(xG) for remaining time, re-simulates after each goal. Falls back to Elo-based model when no xG data available.

**Input features**
- Shot events with xG value, team, is_goal flag
- Remaining xG = rate-based extrapolation from events so far
- Current scoreline
- Match duration (default 90 min)
- Home/away Elo ratings (fallback only, default 1500)

**Model type** — Monte Carlo with 10,000 Poisson(xG) simulations per evaluation point. Function `_simulate_remaining` is LRU-cached. Fallback is logistic Elo with draw margin adjustment.

**Training data** — None. Uses xG values from the xG model directly. No model fitting.

**Known limitations**
- i.i.d. goal assumption: Poisson process treats goals as independent events
- xG rate extrapolation is crude (total xG / minutes elapsed × remaining)
- No shot suppression effect (leading team may reduce attack)
- No stoppage time modelling
- 10,000 simulations are deterministic within the session for a given seed — no confidence intervals by default
- Substitution, tactical changes, red cards not modelled

**Tested range**
- Match duration: 0–120 min
- Goals: 0–15
- 10,000 simulations per call
- 6 unit tests

**Failure modes**
- No xG data → falls back to Elo (50/50 split if ratings equal)
- Zero remaining time → returns current scoreline as deterministic (win=1 for leading team)
- Missing timestamp → 0.0, events not ordered
- NaN xG → treated as 0.0

---

## Injury Risk (injury_risk.py)

**What it does** — Computes ACWR (acute:chronic workload ratio) and a composite injury risk score using a weighted heuristic formula. Produces risk category (low/moderate/high/critical) and recovery recommendations per position.

**Input features**
- `acwr` — acute:chronic workload ratio (7 d acute / 28 d chronic)
- `recent_sprint_count` — sprint volume in recent period
- `recent_distance_km` — total distance in recent period
- `fatigue_index` — fatigue metric (0–30+)
- `position` — GK, DEF, MID, FWD
- `days_since_last_rest` — days since a rest day

**Model type** — Heuristic weighted formula (not ML). Score contributions: ACWR deviation (0.3 max), sprint volume (0.2), distance (0.15), fatigue index (0.15), position base risk (0.05–0.15), rest gap (0–0.1). Total clamped to [0, 1].

**Training data** — None. Thresholds derived from Hulin (2016) and Gabbett (2016) reference models.

**Known limitations**
- Not machine learning based — heuristic thresholds are general population norms
- No individual player history or baseline
- No soft tissue or injury type prediction
- ACWR requires 28 d of continuous data; returns "insufficient data" below 7 d
- Position-risk weights are coarse (4 categories)
- No load type differentiation (GPS vs heart rate vs RPE)

**Tested range**
- ACWR: 0.0–3.0
- Sprint count: 0–50
- Distance: 0–20 km
- Fatigue index: 0–50
- 12 unit tests

**Failure modes**
- <7 d workload data → ACWR=0, risk="low", "insufficient data" recommendation
- Zero chronic load → ACWR set to 1.0 (no risk)
- Unknown position → treated as MID
- Negative days_since_rest → no penalty applied

---

## Formation Analysis (formation_analysis.py)

**What it does** — Detects in-possession and out-of-possession formations from player tracking data. Uses 1D k-means clustering on player x-coordinates to identify defensive, midfield, and forward lines. Computes width, depth, compactness, line distance, and defensive line height.

**Input features**
- Player (x, y) positions per frame (up to 11 per team)
- Possession flag (in-possession vs out-of-possession)
- Pitch dimensions (default 105×68 m)

**Model type** — 1D k-means clustering (k=3 or k=4) with silhouette-like scoring. Formation classified by counting players per cluster and matching against known templates (4-3-3, 4-2-3-1, 4-4-2, 3-4-3, 3-5-2, 5-3-2, 4-1-4-1). Best match by line count overlap.

**Training data** — None. Formation templates are hardcoded. No training or fitting required.

**Known limitations**
- Requires homography-mapped (x, y) positions — raw pixel coordinates will fail
- 1D k-means on x-coordinates only — no lateral/y-shape differentiation
- Goalkeeper excluded (11 player limit)
- Cannot detect asymmetric formations (e.g., 4-2-2-2 box midfield)
- Cluster quality degrades with <8 players visible
- Formation template matching is exact (count tuple must match) — no fuzzy matching

**Tested range**
- Players visible: 3–11
- K-means iterations: up to 30
- 4 cluster groups tested (k=3 and k=4)
- 11 unit tests

**Failure modes**
- <8 players → returns "unknown" for formation
- Player spread <15 m on x-axis → "unknown", line distance = 0, defensive line = mean x
- Single frame or all-identical x values → centroids may not converge
- Out-of-possession with no data → empty report fields (0.0, "unknown")
