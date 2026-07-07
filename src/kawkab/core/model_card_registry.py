"""Model card registry — stores and serves model cards programmatically."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelCard:
    name: str
    description: str
    version: str = "1.0.0"
    model_type: str = ""
    input_features: list[str] = field(default_factory=list)
    output_description: str = ""
    training_data: str = ""
    known_limitations: list[str] = field(default_factory=list)
    tested_range: str = ""
    failure_modes: list[str] = field(default_factory=list)
    test_count: int = 0
    last_validated: str = ""


_registry: dict[str, ModelCard] = {}


def register_model_card(card: ModelCard):
    _registry[card.name] = card


def get_model_card(name: str) -> ModelCard | None:
    return _registry.get(name)


def list_model_cards() -> list[ModelCard]:
    return list(_registry.values())


def clear_registry():
    _registry.clear()


# ── Register built-in model cards ──

register_model_card(ModelCard(
    name="xG",
    description="Expected Goals — logistic regression model that estimates the probability a shot results in a goal",
    version="2.0.0",
    model_type="Logistic Regression (heuristic coefficients)",
    input_features=["distance_to_goal", "angle_to_goal", "body_part", "one_on_one", "under_pressure",
                    "gk_distance", "is_rebound", "big_chance"],
    output_description="Probability (0.0–1.0) that the shot results in a goal",
    training_data="StatsBomb-like distribution — coefficients hand-tuned to approximate published xG models",
    known_limitations=["Not fitted via maximum likelihood on own data", "No shot placement context",
                       "No defender positioning beyond pressure flag", "Assumes all shots are independent"],
    tested_range="Distance: 0–40m, Angle: 0–90°, 29 tests across shot scenarios",
    failure_modes=["Very long shots (>40m) may be overestimated", "Deflections not modeled",
                   "One-on-one flag may be stale by shot time"],
    test_count=29,
))

register_model_card(ModelCard(
    name="xT",
    description="Expected Threat — grid-based valuation of possession actions based on zone transitions",
    version="2.0.0",
    model_type="Grid valuation (20×32 zones with calibrated values)",
    input_features=["start_zone_x", "start_zone_y", "end_zone_x", "end_zone_y", "action_type"],
    output_description="Expected threat value (goals added) for the possession action",
    training_data="StatsBomb event data — calibrated zone values from published methodology",
    known_limitations=["No context of surrounding players", "Assumes average team skill",
                       "Grid resolution may miss fine spatial detail"],
    tested_range="All 640 zones, all action types, 165 tests",
    failure_modes=["Actions near touchline may have inflated threat", "Carry xT less validated than pass xT"],
    test_count=165,
))

register_model_card(ModelCard(
    name="VAEP",
    description="Valuing Actions by Estimating Probabilities — spatiotemporal action valuation framework",
    version="2.0.0",
    model_type="Spatiotemporal probability estimation with player-relative features",
    input_features=["player_distance_to_event", "player_velocity_to_event", "teammate_density",
                    "opponent_density", "event_type", "location_x", "location_y"],
    output_description="VAEP value — change in scoring probability attributed to the action",
    training_data="Self-generated from tracking data — post_score_prob recalculated from next event",
    known_limitations=["Requires accurate tracking (positions of all 22 players)",
                       "Zero-value bug fixed in Sprint 11", "Does not model off-ball contributions"],
    tested_range="All event types, 77 tests including correctness and property-based",
    failure_modes=["With fragmented tracking (<15 players tracked), VAEP degrades significantly",
                   "Set pieces not fully modeled"],
    test_count=77,
))

register_model_card(ModelCard(
    name="Pitch Control",
    description="Voronoi-based pitch control with ball-physics trajectory integration",
    version="2.0.0",
    model_type="Voronoi tessellation + RK4 ball trajectory",
    input_features=["player_x", "player_y", "ball_x", "ball_y", "ball_z", "player_max_speed",
                    "ball_velocity", "player_reaction_time"],
    output_description="Per-player pitch control value (proportion of pitch controlled at each timestep)",
    training_data="Theoretical model — no training data required",
    known_limitations=["Does not model tactical intent", "Players treated as having equal acceleration profiles",
                       "Ball physics simplified (no spin/wind)"],
    tested_range="5-frame sequences, 41 tests including numpy broadcasting optimization verification",
    failure_modes=["With <18 players tracked, control map becomes unreliable",
                   "Goalkeeper not modeled differently from outfield players"],
    test_count=41,
))

register_model_card(ModelCard(
    name="Win Probability",
    description="Monte Carlo simulation of match outcome based on xG rates",
    version="1.0.0",
    model_type="Monte Carlo (10,000 simulations, Poisson goal generation)",
    input_features=["home_xg_rate", "away_xg_rate", "score_home", "score_away",
                    "minutes_remaining", "home_advantage"],
    output_description="Win/draw/loss probabilities at a given match state",
    training_data="No external training — Poisson assumption with team xG rates",
    known_limitations=["Assumes goals are i.i.d. Poisson events", "No momentum or tactical context",
                       "Does not model red cards, injuries, or substitutions"],
    tested_range="All scorelines 0-0 to 5-5, all time states 0-90 min, 6 tests",
    failure_modes=["Early in match (<15 min) probabilities are near 50/50 and uninformative",
                   "Very one-sided matches may show overconfidence"],
    test_count=6,
))

register_model_card(ModelCard(
    name="Injury Risk",
    description="ACWR-based injury risk prediction using Hulin/Gabbett reference models",
    version="1.0.0",
    model_type="Heuristic with ACWR threshold bands",
    input_features=["acute_load_7d", "chronic_load_28d", "sprint_volume", "total_distance",
                    "fatigue_index", "position", "rest_days", "hrv_rmssd"],
    output_description="Risk level (low/moderate/high/critical) and recovery recommendation",
    training_data="Hulin & Gabbett published reference models — not fitted on own data",
    known_limitations=["Heuristic thresholds, not ML-based", "Does not incorporate subjective wellness",
                       "No historical injury pattern matching"],
    tested_range="All positions (GK/DEF/MID/FWD), ACWR 0.5-2.0, 12 tests",
    failure_modes=["With <7 days of load data, ACWR is unreliable",
                   "Acute spikes (single high-load session) may overstate risk"],
    test_count=12,
))

register_model_card(ModelCard(
    name="Formation Analysis",
    description="K-means clustering of player positions to detect tactical formations",
    version="1.0.0",
    model_type="K-means (k=10) with silhouette scoring for optimal k",
    input_features=["player_x_meters", "player_y_meters", "team_id", "timestamp"],
    output_description="Detected formation (e.g., '4-3-3'), per-player role assignments, width/depth metrics",
    training_data="No training data — unsupervised clustering on match positions",
    known_limitations=["Requires homography calibration (real-world meters)",
                       "Assumes players maintain position within phase", "May misclassify fluid systems"],
    tested_range="5 detected formations (4-3-3, 4-4-2, 4-2-3-1, 3-5-2, 5-3-2), 11 tests",
    failure_modes=["Without homography, formation detection is in pixel space and unreliable",
                   "During transitions, detected formation may not reflect intended shape",
                   "Substitutions mid-phase can distort cluster centers"],
    test_count=11,
))
