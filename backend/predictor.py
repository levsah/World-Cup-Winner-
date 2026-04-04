"""
predictor.py
============
Monte Carlo tournament simulator for the 2026 FIFA World Cup.

Format (48 teams):
  • 12 groups of 4 teams each (Groups A–L from the Washington DC draw)
  • Top 2 from each group + 8 best 3rd-place teams → Round of 32 (32 teams)
  • Single-elimination: R32 → R16 → QF → SF → Final → Champion

Each match uses an attack/defense Poisson goal model + logistic win-probability,
both driven by the normalised metric scores from data_processor.py.
A per-simulation Gaussian strength fluctuation (σ=5) adds realistic match variance.
"""

import random
import math
import logging
from collections import defaultdict
from typing import Any

import numpy as np

from config import WEIGHTS, MONTE_CARLO_SIMULATIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strength score computation
# ---------------------------------------------------------------------------

def compute_strength(profile: dict) -> float:
    """
    Weighted average of normalised 0–100 metric scores → composite strength.
    """
    score = 0.0
    score += WEIGHTS["fifa_ranking"]          * profile.get("fifa_ranking_score",      50)
    score += WEIGHTS["recent_form"]           * profile.get("recent_form_score",       50)
    score += WEIGHTS["wc_history"]            * profile.get("wc_history_score",        50)
    score += WEIGHTS["squad_strength"]        * profile.get("squad_strength_score",    50)
    score += WEIGHTS["goal_difference"]       * profile.get("goal_diff_score",         50)
    score += WEIGHTS["tournament_experience"] * profile.get("tournament_exp_score",    50)
    score += WEIGHTS["player_performance"]    * profile.get("player_performance_score", 55)
    return round(score, 2)


# ---------------------------------------------------------------------------
# Match simulation
# ---------------------------------------------------------------------------

_HOSTS = {"USA", "Canada", "Mexico"}

# Average goals per team per game in recent World Cups (≈ 1.35 per side)
_BASE_GOALS = 1.35


def _win_probability(sa: float, sb: float) -> float:
    """Logistic win probability for team A. Scale factor 40 → 70 % chance at +20 pts."""
    return 1.0 / (1.0 + 10 ** ((sb - sa) / 40.0))


def simulate_match(
    team_a: dict,
    team_b: dict,
    knockout: bool = False,
) -> dict:
    """
    Simulate one match using an attack/defense Poisson model.

    Expected goals for A = BASE_GOALS * (A_attack / 50) * (50 / B_defense)

    where attack  ≈ offensive component of strength and
          defense ≈ defensive component (stronger team defends better too).

    Returns {"winner": team | None, "goals_a": int, "goals_b": int}.
    winner=None means a group-stage draw.
    """
    sa = team_a["strength"]
    sb = team_b["strength"]

    # Host nation home-tournament advantage
    if team_a["name"] in _HOSTS:
        sa = min(sa + 5, 100)
    if team_b["name"] in _HOSTS:
        sb = min(sb + 5, 100)

    # Decompose strength into attack / defense components so each team's
    # expected goals depends on both their attack AND the opponent's defense.
    # attack_x weights strength more offensively; defense_x more defensively.
    attack_a  = sa * 0.65 + 35 * 0.35
    attack_b  = sb * 0.65 + 35 * 0.35
    defense_a = sa * 0.35 + 35 * 0.65
    defense_b = sb * 0.35 + 35 * 0.65

    lam_a = max(0.1, _BASE_GOALS * (attack_a / 50) * (50 / defense_b))
    lam_b = max(0.1, _BASE_GOALS * (attack_b / 50) * (50 / defense_a))

    goals_a = int(np.random.poisson(lam_a))
    goals_b = int(np.random.poisson(lam_b))

    if goals_a > goals_b:
        winner = team_a
    elif goals_b > goals_a:
        winner = team_b
    else:
        if knockout:
            # Penalty shoot-out: decide by raw win probability
            p_a = _win_probability(sa, sb)
            winner = team_a if random.random() < p_a else team_b
        else:
            winner = None   # draw in group stage

    return {"winner": winner, "goals_a": goals_a, "goals_b": goals_b}


# ---------------------------------------------------------------------------
# Group stage (16 groups × 3 teams)
# ---------------------------------------------------------------------------

def simulate_group(group: list[dict]) -> tuple[list[dict], dict]:
    """Round-robin within a 4-team group.

    Returns:
        (ranked_teams, third_place_entry)
        ranked_teams  – teams sorted 1st→4th with _grp_* attributes set.
        third_place_entry – stats dict for the 3rd-place team (used for
                            cross-group best-3rd comparison).
    """
    stats: dict[int, dict] = {
        t["id"]: {"team": t, "pts": 0, "gf": 0, "ga": 0}
        for t in group
    }
    pairs = [
        (group[i], group[j])
        for i in range(len(group))
        for j in range(i + 1, len(group))
    ]
    for a, b in pairs:
        r   = simulate_match(a, b, knockout=False)
        aid = a["id"]
        bid = b["id"]
        stats[aid]["gf"] += r["goals_a"]
        stats[aid]["ga"] += r["goals_b"]
        stats[bid]["gf"] += r["goals_b"]
        stats[bid]["ga"] += r["goals_a"]
        if r["winner"] is None:
            stats[aid]["pts"] += 1
            stats[bid]["pts"] += 1
        elif r["winner"]["id"] == aid:
            stats[aid]["pts"] += 3
        else:
            stats[bid]["pts"] += 3

    ranked = sorted(
        stats.values(),
        key=lambda x: (x["pts"], x["gf"] - x["ga"], x["gf"]),
        reverse=True,
    )
    for pos, entry in enumerate(ranked):
        entry["team"]["_grp_pos"] = pos + 1
        entry["team"]["_grp_pts"] = entry["pts"]
        entry["team"]["_grp_gd"]  = entry["gf"] - entry["ga"]
        entry["team"]["_grp_gf"]  = entry["gf"]

    return [e["team"] for e in ranked], ranked[2]


# ---------------------------------------------------------------------------
# Knockout round helper
# ---------------------------------------------------------------------------

def run_knockout_round(teams: list[dict]) -> list[dict]:
    """Pair teams sequentially and return winners (half the bracket)."""
    winners = []
    for i in range(0, len(teams) - 1, 2):
        r = simulate_match(teams[i], teams[i + 1], knockout=True)
        winners.append(r["winner"])
    return winners


# ---------------------------------------------------------------------------
# Full tournament simulation (one run)
# ---------------------------------------------------------------------------

def simulate_tournament(teams: list[dict]) -> dict:
    """
    Simulate one complete 2026 World Cup.

    Format: 12 groups × 4 teams (Groups A–L from the official draw).
    Advancement: top 2 from each group (24 teams) + the 8 best 3rd-place
    teams out of 12 = 32 teams in the Round of 32.

    If all teams carry a "group" key (from the final draw data), the actual
    group assignments are used — making the simulation faithful to the draw.
    Otherwise teams are randomly assigned to 12 groups.

    Each run applies a per-team Gaussian form fluctuation (σ = 5 pts) so
    that teams can over- or under-perform their baseline strength.

    Returns {"champion": team_dict, "finalist": team_dict, "semifinalists": [...]}.
    """
    # Apply per-run form fluctuation: each team can be ±~5 pts from baseline
    simulated_teams = []
    for t in teams:
        t_copy = dict(t)
        fluctuation = random.gauss(0, 5)
        t_copy["strength"] = max(10.0, min(100.0, t["strength"] + fluctuation))
        simulated_teams.append(t_copy)

    # Set up groups — use actual draw group assignments if present
    if all("group" in t and t["group"] for t in simulated_teams):
        group_map: dict[str, list[dict]] = {}
        for t in simulated_teams:
            grp = t["group"]
            if grp not in group_map:
                group_map[grp] = []
            group_map[grp].append(t)
        groups = list(group_map.values())
    else:
        shuffled = simulated_teams[:]
        random.shuffle(shuffled)
        groups = [shuffled[i * 4:(i + 1) * 4] for i in range(12)]

    r32_direct: list[dict] = []
    third_place_entries: list[dict] = []

    for grp in groups:
        ranked, third_entry = simulate_group(grp)
        r32_direct.extend(ranked[:2])           # top 2 qualify directly
        third_place_entries.append(third_entry) # collect 3rd-place stats

    # Best 8 of 12 third-place finishers also advance to R32
    third_sorted = sorted(
        third_place_entries,
        key=lambda x: (x["pts"], x["gf"] - x["ga"], x["gf"]),
        reverse=True,
    )
    r32_teams = r32_direct + [p["team"] for p in third_sorted[:8]]

    # Shuffle R32 bracket to avoid systematic group-stage bias in pairings
    random.shuffle(r32_teams)

    round_results = {}
    current = r32_teams
    round_names = ["Round of 32", "Round of 16", "Quarter-Finals", "Semi-Finals"]
    for rname in round_names:
        current = run_knockout_round(current)
        round_results[rname] = [t["name"] for t in current]

    # Final
    assert len(current) == 2, f"Expected 2 finalists, got {len(current)}"
    final_result = simulate_match(current[0], current[1], knockout=True)
    champion = final_result["winner"]
    finalist = current[1] if champion["id"] == current[0]["id"] else current[0]

    return {
        "champion":      champion,
        "finalist":      finalist,
        "semifinalists": round_results.get("Semi-Finals", []),
        "rounds":        round_results,
    }


# ---------------------------------------------------------------------------
# Monte Carlo aggregation
# ---------------------------------------------------------------------------

def run_monte_carlo(
    profiles: list[dict],
    n_simulations: int = MONTE_CARLO_SIMULATIONS,
) -> list[dict]:
    """
    Run N full tournament simulations and return a ranked list of teams
    with win / finalist / semi-final probabilities.
    """
    # Attach composite strength to each profile copy
    teams = []
    for p in profiles:
        t = dict(p)
        t["strength"] = compute_strength(p)
        teams.append(t)

    win_counts:   defaultdict[str, int] = defaultdict(int)
    final_counts: defaultdict[str, int] = defaultdict(int)
    sf_counts:    defaultdict[str, int] = defaultdict(int)

    logger.info("Running %d Monte Carlo simulations…", n_simulations)
    for _ in range(n_simulations):
        result = simulate_tournament(teams)
        champ_name    = result["champion"]["name"]
        finalist_name = result["finalist"]["name"]
        win_counts[champ_name] += 1
        final_counts[champ_name]    += 1
        final_counts[finalist_name] += 1
        for name in result["semifinalists"]:
            sf_counts[name] += 1

    output = []
    for team in teams:
        name = team["name"]
        output.append({
            "id":             team["id"],
            "name":           name,
            "flag":           team.get("flag", ""),
            "confederation":  team.get("confederation", ""),
            "group":          team.get("group", ""),
            "strength":       team["strength"],
            "fifa_rank":      team.get("fifa_rank", "N/A"),
            "win_probability": round(win_counts[name]   / n_simulations * 100, 2),
            "final_prob":      round(final_counts[name] / n_simulations * 100, 2),
            "semifinal_prob":  round(sf_counts[name]    / n_simulations * 100, 2),
            "metrics": {
                "FIFA Ranking Score":    round(team.get("fifa_ranking_score",       50), 1),
                "Recent Form":          round(team.get("recent_form_score",         50), 1),
                "WC History":           round(team.get("wc_history_score",          50), 1),
                "Squad Strength":       round(team.get("squad_strength_score",      50), 1),
                "Goal Difference":      round(team.get("goal_diff_score",           50), 1),
                "Tournament Experience":round(team.get("tournament_exp_score",      50), 1),
                "Player Performance":   round(team.get("player_performance_score",  55), 1),
            },
        })

    output.sort(key=lambda x: x["win_probability"], reverse=True)
    return output
