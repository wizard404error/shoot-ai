"""Game Plan Scouting Report — match preparation report for upcoming opponents."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OpponentProfile:
    team_name: str
    formation_probabilities: dict[str, float]
    strength_of_play: dict[str, float]
    top_scorers: list[dict]
    top_assisters: list[dict]
    set_piece_threat: float
    pressing_intensity: float
    transition_speed: float
    key_weaknesses: list[str]


@dataclass
class GamePlan:
    opponent: OpponentProfile
    recommended_formation: str
    recommended_tactics: list[str]
    key_players_to_neutralize: list[dict]
    set_piece_plan: list[str]
    predicted_scoreline: dict
    preparation_notes: str

    def to_dict(self) -> dict:
        return {
            "opponent": {
                "team_name": self.opponent.team_name,
                "formation_probabilities": self.opponent.formation_probabilities,
                "strength_of_play": self.opponent.strength_of_play,
                "top_scorers": self.opponent.top_scorers,
                "top_assisters": self.opponent.top_assisters,
                "set_piece_threat": self.opponent.set_piece_threat,
                "pressing_intensity": self.opponent.pressing_intensity,
                "transition_speed": self.opponent.transition_speed,
                "key_weaknesses": self.opponent.key_weaknesses,
            },
            "recommended_formation": self.recommended_formation,
            "recommended_tactics": self.recommended_tactics,
            "key_players_to_neutralize": self.key_players_to_neutralize,
            "set_piece_plan": self.set_piece_plan,
            "predicted_scoreline": self.predicted_scoreline,
            "preparation_notes": self.preparation_notes,
        }

    def to_markdown(self) -> str:
        lines = []
        lines.append(f"# Game Plan: vs {self.opponent.team_name}")
        lines.append("")
        lines.append("## Opponent Profile")
        lines.append(f"- **Formation tendencies**: {self._fmt_dict(self.opponent.formation_probabilities)}")
        lines.append(f"- **Set piece threat**: {self.opponent.set_piece_threat:.2f}")
        lines.append(f"- **Pressing intensity**: {self.opponent.pressing_intensity:.2f}")
        lines.append(f"- **Transition speed**: {self.opponent.transition_speed:.2f}")
        lines.append(f"- **Strengths**: {self._fmt_dict(self.opponent.strength_of_play)}")
        if self.opponent.key_weaknesses:
            lines.append(f"- **Key weaknesses**: {', '.join(self.opponent.key_weaknesses)}")
        lines.append("")
        lines.append("## Top Scorers")
        for s in self.opponent.top_scorers[:5]:
            lines.append(f"- {s.get('player', 'Unknown')}: {s.get('goals', 0)} goals")
        lines.append("")
        lines.append("## Top Assisters")
        for a in self.opponent.top_assisters[:5]:
            lines.append(f"- {a.get('player', 'Unknown')}: {a.get('assists', 0)} assists")
        lines.append("")
        lines.append("## Recommended Approach")
        lines.append(f"- **Formation**: {self.recommended_formation}")
        for t in self.recommended_tactics:
            lines.append(f"- {t}")
        lines.append("")
        lines.append("## Key Players to Neutralize")
        for p in self.key_players_to_neutralize:
            lines.append(f"- **{p.get('player', 'Unknown')}**: {p.get('why', '')}")
            lines.append(f"  - *How*: {p.get('how', '')}")
        lines.append("")
        lines.append("## Set Piece Plan")
        for s in self.set_piece_plan:
            lines.append(f"- {s}")
        lines.append("")
        lines.append("## Predicted Scoreline")
        for k, v in self.predicted_scoreline.items():
            lines.append(f"- **{k.replace('_', ' ').title()}**: {v}")
        lines.append("")
        if self.preparation_notes:
            lines.append("## Preparation Notes")
            lines.append(self.preparation_notes)
        return "\n".join(lines)

    @staticmethod
    def _fmt_dict(d: dict) -> str:
        return ", ".join(f"{k}: {v:.0%}" if isinstance(v, float) else f"{k}: {v}" for k, v in d.items())


def generate_game_plan(
    opponent_team_id: str,
    opponent_matches: list[dict],
    own_team_id: str,
    own_matches: list[dict],
    home_advantage: bool = True,
    formation_analyzer=None,
    similarity_engine=None,
    scouting_service=None,
) -> GamePlan:
    if not opponent_matches:
        return _default_game_plan(opponent_team_id)

    formation_probs = _compute_formation_probabilities(opponent_matches)
    strength_of_play = _compute_strength_of_play(opponent_matches)
    top_scorers = _extract_top_scorers(opponent_matches)
    top_assisters = _extract_top_assisters(opponent_matches)
    set_piece_threat = _compute_set_piece_threat(opponent_matches)
    pressing_intensity = _compute_pressing_intensity(opponent_matches)
    transition_speed = _compute_transition_speed(opponent_matches)
    key_weaknesses = _identify_key_weaknesses(pressing_intensity, opponent_matches)

    opponent = OpponentProfile(
        team_name=opponent_team_id,
        formation_probabilities=formation_probs,
        strength_of_play=strength_of_play,
        top_scorers=top_scorers,
        top_assisters=top_assisters,
        set_piece_threat=set_piece_threat,
        pressing_intensity=pressing_intensity,
        transition_speed=transition_speed,
        key_weaknesses=key_weaknesses,
    )

    recommended_formation = _recommend_formation(formation_probs, own_matches)
    recommended_tactics = _recommend_tactics(opponent, key_weaknesses)
    key_players_to_neutralize = _build_key_players(opponent)
    set_piece_plan = _build_set_piece_plan(opponent)
    predicted_scoreline = _compute_predicted_scoreline(opponent, own_matches, home_advantage)
    preparation_notes = _build_preparation_notes(opponent, recommended_formation)

    return GamePlan(
        opponent=opponent,
        recommended_formation=recommended_formation,
        recommended_tactics=recommended_tactics,
        key_players_to_neutralize=key_players_to_neutralize,
        set_piece_plan=set_piece_plan,
        predicted_scoreline=predicted_scoreline,
        preparation_notes=preparation_notes,
    )


def _default_game_plan(team_name: str) -> GamePlan:
    return GamePlan(
        opponent=OpponentProfile(
            team_name=team_name,
            formation_probabilities={},
            strength_of_play={},
            top_scorers=[],
            top_assisters=[],
            set_piece_threat=0.0,
            pressing_intensity=0.5,
            transition_speed=0.5,
            key_weaknesses=[],
        ),
        recommended_formation="4-4-2",
        recommended_tactics=["Standard preparation — insufficient opponent data"],
        key_players_to_neutralize=[],
        set_piece_plan=["Standard defensive set piece organization"],
        predicted_scoreline={"most_likely": "1-1", "home_win_pct": 40, "draw_pct": 30, "away_win_pct": 30},
        preparation_notes=f"No recent match data available for {team_name}. Recommend standard tactical setup.",
    )


def _compute_formation_probabilities(matches: list[dict]) -> dict[str, float]:
    counts: dict[str, int] = {}
    total = 0
    for m in matches:
        for formation_key in ("in_possession_formation", "out_possession_formation", "formation"):
            f = m.get(formation_key)
            if f and f != "unknown":
                counts[f] = counts.get(f, 0) + 1
                total += 1
    if total == 0:
        return {}
    return {k: round(v / total, 3) for k, v in sorted(counts.items(), key=lambda x: -x[1])}


def _compute_strength_of_play(matches: list[dict]) -> dict[str, float]:
    vals: dict[str, list[float]] = {}
    for m in matches:
        for key in ("build_up_score", "counter_attack_score", "directness_score", "width_score"):
            v = m.get(key)
            if v is not None:
                vals.setdefault(key, []).append(float(v))
    if not vals:
        return {"build_up": 0.5, "counter_attack": 0.5}

    display_map = {
        "build_up_score": "build_up",
        "counter_attack_score": "counter_attack",
        "directness_score": "directness",
        "width_score": "width",
    }
    result = {}
    for key, values in vals.items():
        display = display_map.get(key, key)
        result[display] = round(statistics.mean(values), 3)
    return result


def _extract_top_scorers(matches: list[dict]) -> list[dict]:
    totals: dict[str, float] = {}
    for m in matches:
        for s in m.get("scorers", m.get("goals", [])):
            if isinstance(s, dict):
                player = s.get("player", "unknown")
                goals = float(s.get("goals", 1))
                totals[player] = totals.get(player, 0) + goals
    sorted_players = sorted(totals.items(), key=lambda x: -x[1])
    return [{"player": p, "goals": int(g)} for p, g in sorted_players]


def _extract_top_assisters(matches: list[dict]) -> list[dict]:
    totals: dict[str, float] = {}
    for m in matches:
        for a in m.get("assisters", m.get("assists", [])):
            if isinstance(a, dict):
                player = a.get("player", "unknown")
                assists = float(a.get("assists", 1))
                totals[player] = totals.get(player, 0) + assists
    sorted_players = sorted(totals.items(), key=lambda x: -x[1])
    return [{"player": p, "assists": int(a)} for p, a in sorted_players]


def _compute_set_piece_threat(matches: list[dict]) -> float:
    threats = []
    for m in matches:
        t = m.get("set_piece_threat")
        if t is not None:
            threats.append(float(t))
        else:
            corners = float(m.get("corners", 0))
            goals_from_sp = float(m.get("goals_from_set_pieces", 0))
            total_goals = float(m.get("goals", 0))
            if total_goals > 0:
                threats.append(goals_from_sp / total_goals)
            elif corners > 0:
                threats.append(min(1.0, goals_from_sp / max(corners, 1)))
    return round(statistics.mean(threats), 3) if threats else 0.0


def _compute_pressing_intensity(matches: list[dict]) -> float:
    ppdas = []
    for m in matches:
        ppda = m.get("ppda") or m.get("pressing_intensity")
        if ppda is not None:
            ppdas.append(float(ppda))
    if not ppdas:
        return 0.5
    avg_ppda = statistics.mean(ppdas)
    if avg_ppda <= 0:
        return 0.5
    normalized = max(0.0, min(1.0, 1.0 - (avg_ppda - 3.0) / 15.0))
    return round(normalized, 3)


def _compute_transition_speed(matches: list[dict]) -> float:
    speeds = []
    for m in matches:
        s = m.get("transition_speed") or m.get("avg_transition_seconds")
        if s is not None:
            speeds.append(float(s))
    if not speeds:
        return 0.5
    avg = statistics.mean(speeds)
    normalized = max(0.0, min(1.0, 1.0 - avg / 10.0))
    return round(normalized, 3)


def _identify_key_weaknesses(pressing_intensity: float, matches: list[dict]) -> list[str]:
    weaknesses: list[str] = []
    if pressing_intensity < 0.4:
        weaknesses.append("Low pressing intensity — can be dominated in midfield")
    if pressing_intensity > 0.8:
        weaknesses.append("Very aggressive press — vulnerable to quick switches and through balls")

    avg_conceded = statistics.mean(
        [float(m.get("goals_conceded", 0)) for m in matches if m.get("goals_conceded") is not None]
    ) if any(m.get("goals_conceded") is not None for m in matches) else 0
    if avg_conceded > 2:
        weaknesses.append("Concedes heavily — defensive organization is weak")

    build_up = _compute_strength_of_play(matches).get("build_up", 0.5)
    if build_up < 0.4:
        weaknesses.append("Weak build-up play — pressing will force errors")
    if build_up > 0.8:
        weaknesses.append("Relies heavily on build-up — cutting passing lanes disrupts their rhythm")

    for m in matches:
        if m.get("slow_center_backs"):
            weaknesses.append("Slow center-backs — exploit with pace in behind")
            break

    return weaknesses


def _recommend_formation(formation_probs: dict[str, float], own_matches: list[dict]) -> str:
    if not formation_probs:
        return "4-4-2"
    top_formation = max(formation_probs, key=formation_probs.get)

    counter_formations = {
        "4-3-3": "4-2-3-1",
        "4-2-3-1": "4-3-3",
        "4-4-2": "3-5-2",
        "3-5-2": "4-4-2",
        "3-4-3": "4-4-2",
        "5-3-2": "4-3-3",
        "4-1-4-1": "4-4-2",
    }
    return counter_formations.get(top_formation, "4-4-2")


def _recommend_tactics(opponent: OpponentProfile, weaknesses: list[str]) -> list[str]:
    tactics: list[str] = []

    for w in weaknesses:
        if "pressing" in w.lower():
            tactics.append("Press high to capitalize on opponent's weak pressing")
        if "build-up" in w.lower() and "Weak" in w:
            tactics.append("High press — opponent struggles against pressure")
        if "build-up" in w.lower() and "Relies" in w:
            tactics.append("Block passing lanes to center-backs and defensive midfielder")
        if "concedes" in w.lower():
            tactics.append("Attack with numbers — their defensive organization is vulnerable")
        if "pace" in w.lower():
            tactics.append("Use pace in behind — their defense lacks recovery speed")

    if opponent.set_piece_threat > 0.25:
        tactics.append("Defend set pieces with zonal marking — opponent is dangerous from dead balls")
    else:
        tactics.append("Commit fewer players to set piece defense — maintain counter-attacking shape")

    if opponent.transition_speed > 0.7:
        tactics.append("Quick transitions — opponent recovers slowly")
        tactics.append("Counter-press immediately after losing possession")

    if opponent.pressing_intensity < 0.4:
        tactics.append("Build patiently from the back — opponent does not press effectively")

    if not tactics:
        tactics.append("Balanced approach — maintain shape and exploit tactical adjustments at half-time")

    return tactics


def _build_key_players(opponent: OpponentProfile) -> list[dict]:
    players: list[dict] = []
    for s in opponent.top_scorers[:3]:
        players.append({
            "player": s.get("player", "Unknown"),
            "why": "Primary goal threat — leads team in scoring",
            "how": "Double-team when in shooting range, force onto weaker foot",
        })
    for a in opponent.top_assisters[:2]:
        if not any(p["player"] == a.get("player", "") for p in players):
            players.append({
                "player": a.get("player", "Unknown"),
                "why": "Creative hub — main chance creator",
                "how": "Deny space in final third, close down quickly",
            })
    return players


def _build_set_piece_plan(opponent: OpponentProfile) -> list[str]:
    plan: list[str] = []
    if opponent.set_piece_threat > 0.25:
        plan.append("Zonal marking on corners — opponent has strong aerial presence")
        plan.append("Short corners expected — prepare for quick combination plays")
        plan.append("Assign quick players to cover short options on free kicks")
    else:
        plan.append("Man-marking on corners — opponent set pieces are not a primary threat")
        plan.append("Leave two players upfield for counter-attacks on corners")

    if opponent.transition_speed > 0.6:
        plan.append("Defensive midfielder to screen back line on opponent transitions")
    plan.append("All players track runners from deep on set pieces")
    return plan


def _compute_predicted_scoreline(
    opponent: OpponentProfile,
    own_matches: list[dict],
    home_advantage: bool,
) -> dict:
    opp_goal_rate = _estimate_goal_rate(opponent)
    own_goal_rate = _estimate_own_goal_rate(own_matches)

    home_factor = 1.15 if home_advantage else 0.85
    home_xg = own_goal_rate * home_factor
    away_xg = opp_goal_rate * (0.85 if home_advantage else 1.15)

    import math
    home_avg = round(home_xg, 1)
    away_avg = round(away_xg, 1)

    home_win = math.exp(-away_xg) * (1 - math.exp(-home_xg)) if home_xg > 0 else 0
    draw = math.exp(-home_xg) * math.exp(-away_xg) + home_xg * away_xg * math.exp(-home_xg - away_xg)
    away_win = math.exp(-home_xg) * (1 - math.exp(-away_xg)) if away_xg > 0 else 0
    total = home_win + draw + away_win
    if total > 0:
        home_win_pct = round(home_win / total * 100)
        draw_pct = round(draw / total * 100)
        away_win_pct = round(away_win / total * 100)
    else:
        home_win_pct = draw_pct = away_win_pct = 33

    most_likely = f"{max(0, round(home_avg))}-{max(0, round(away_avg))}"
    if most_likely == "0-0":
        most_likely = "1-1"

    return {
        "most_likely": most_likely,
        "home_win_pct": home_win_pct,
        "draw_pct": draw_pct,
        "away_win_pct": away_win_pct,
    }


def _estimate_goal_rate(opponent: OpponentProfile) -> float:
    goals_scored = sum(s.get("goals", 0) for s in opponent.top_scorers)
    base = max(0.5, goals_scored * 0.15)
    if opponent.set_piece_threat > 0.2:
        base += opponent.set_piece_threat * 0.5
    return min(3.0, base)


def _estimate_own_goal_rate(matches: list[dict]) -> float:
    goals = []
    for m in matches:
        g = m.get("goals_scored") or m.get("goals", 0)
        if g is not None:
            goals.append(float(g))
    return statistics.mean(goals) * 0.15 if goals else 1.2


def _build_preparation_notes(opponent: OpponentProfile, formation: str) -> str:
    parts: list[str] = []
    parts.append(f"The opponent's most likely formation is {max(opponent.formation_probabilities, key=opponent.formation_probabilities.get) if opponent.formation_probabilities else 'unknown'}.")
    parts.append(f"Recommended counter-formation: {formation}.")

    if opponent.set_piece_threat > 0.2:
        parts.append("Set pieces will be critical — ensure zonal marking is rehearsed.")
    if opponent.pressing_intensity < 0.4:
        parts.append("Their pressing is weak — build-up play should be comfortable.")
    if opponent.transition_speed > 0.6:
        parts.append("They rely on fast transitions — structure defensive shape before committing numbers forward.")
    if opponent.key_weaknesses:
        parts.append("Key weaknesses to exploit: " + "; ".join(opponent.key_weaknesses[:3]))

    return " ".join(parts)
