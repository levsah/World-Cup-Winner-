"""
predictor.py
============
Monte Carlo tournament simulator for the 2026 FIFA World Cup.

Format (48 teams):
  • 16 groups of 3 teams each
  • Top 2 from each group → Round of 32 (32 teams)
  • Single-elimination: R32 → R16 → QF → SF → Final → Champion

Each match uses a Poisson goal model + logistic win-probability,
both driven by the normalised metric scores from data_processor.py.
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
    score += WEIGHTS["fifa_ranking"]          * profile.get("fifa_ranking_score",    50)
    score += WEIGHTS["recent_form"]           * profile.get("recent_form_score",     50)
    score += WEIGHTS["wc_history"]            * profile.get("wc_history_score",      50)
    score += WEIGHTS["squad_strength"]        * profile.get("squad_strength_score",  50)
    score += WEIGHTS["goal_difference"]       * profile.get("goal_diff_score",       50)
    score += WEIGHTS["tournament_experience"] * profile.get("tournament_exp_score",  50)
    return round(score, 2)


# ---------------------------------------------------------------------------
# Match simulation
# ---------------------------------------------------------------------------

_HOSTS = {"USA", "Canada", "Mexico"}


def _win_probability(sa: float, sb: float) -> float:
    """Logistic win probability for team A. Scale factor 40 → 70 % chance at +20 pts."""
    return 1.0 / (1.0 + 10 ** ((sb - sa) / 40.0))


def simulate_match(
    team_a: dict,
    team_b: dict,
    knockout: bool = False,
) -> dict:
    """
    Simulate one match; returns {"winner": team | None, "goals_a": int, "goals_b": int}.
    winner=None means a group-stage draw.
    """
    sa = team_a["strength"]
    sb = team_b["strength"]

    # Host nation home-tournament advantage
    if team_a["name"] in _HOSTS:
        sa = min(sa + 5, 100)
    if team_b["name"] in _HOSTS:
        sb = min(sb + 5, 100)

    # Expected goals via Poisson (avg top-team scores ~2.5 goals when at full strength)
    lam_a = max(0.1, (sa / 100) * 2.5)
    lam_b = max(0.1, (sb / 100) * 2.5)
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

def simulate_group(group: list[dict]) -> list[dict]:
    """Round-robin within a 3-team group. Returns teams sorted 1st→3rd."""
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

    return [e["team"] for e in ranked]


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
    Returns {"champion": team_dict, "finalist": team_dict, "semifinalists": [...]}.
    """
    # 16 groups of 3
    shuffled = teams[:]
    random.shuffle(shuffled)
    groups = [shuffled[i * 3:(i + 1) * 3] for i in range(16)]

    r32_teams = []
    for grp in groups:
        ranked = simulate_group(grp)
        r32_teams.extend(ranked[:2])   # top 2 advance

    # Shuffle R32 bracket to avoid group-stage bias in pairings
    random.shuffle(r32_teams)

    round_results = {}

    current = r32_teams
    round_names = [
        "Round of 32", "Round of 16",
        "Quarter-Finals", "Semi-Finals",
    ]
    for rname in round_names:
        current = run_knockout_round(current)
        round_results[rname] = [t["name"] for t in current]

    # Final
    assert len(current) == 2, f"Expected 2 finalists, got {len(current)}"
    final_result = simulate_match(current[0], current[1], knockout=True)
    champion = final_result["winner"]
    finalist = current[1] if champion["id"] == current[0]["id"] else current[0]

    return {
        "champion":     champion,
        "finalist":     finalist,
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
            "strength":       team["strength"],
            "fifa_rank":      team.get("fifa_rank", "N/A"),
            "win_probability": round(win_counts[name]   / n_simulations * 100, 2),
            "final_prob":      round(final_counts[name] / n_simulations * 100, 2),
            "semifinal_prob":  round(sf_counts[name]    / n_simulations * 100, 2),
            "metrics": {
                "FIFA Ranking Score":    round(team.get("fifa_ranking_score",   50), 1),
                "Recent Form":          round(team.get("recent_form_score",     50), 1),
                "WC History":           round(team.get("wc_history_score",      50), 1),
                "Squad Strength":       round(team.get("squad_strength_score",  50), 1),
                "Goal Difference":      round(team.get("goal_diff_score",       50), 1),
                "Tournament Experience":round(team.get("tournament_exp_score",  50), 1),
            },
        })

    output.sort(key=lambda x: x["win_probability"], reverse=True)
    return output
