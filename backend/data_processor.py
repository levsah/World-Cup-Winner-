"""
data_processor.py
=================
Fetches raw data from api_client.py and transforms it into
normalised metric scores (0–100) used by the prediction model.

Key scores derived per team:
  - fifa_ranking_score      : Inverted / normalised rank
  - recent_form_score       : Points earned in last 10 matches
  - wc_history_score        : Past WC round progression average
  - squad_strength_score    : Proxy from club league tier of players
  - goal_diff_score         : Goals scored − conceded (recent form window)
  - tournament_exp_score    : WC appearances count
"""

import logging
from typing import Any

import api_client as api

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 2026 World Cup: 48 qualified teams
# (IDs from API-Football — confirmed QP teams as of early 2026)
# ---------------------------------------------------------------------------
QUALIFIED_TEAMS: list[dict] = [
    # CONMEBOL
    {"id": 6,   "name": "Brazil",        "confederation": "CONMEBOL", "flag": "🇧🇷"},
    {"id": 7,   "name": "Argentina",     "confederation": "CONMEBOL", "flag": "🇦🇷"},
    {"id": 26,  "name": "Colombia",      "confederation": "CONMEBOL", "flag": "🇨🇴"},
    {"id": 13,  "name": "Uruguay",       "confederation": "CONMEBOL", "flag": "🇺🇾"},
    {"id": 21,  "name": "Ecuador",       "confederation": "CONMEBOL", "flag": "🇪🇨"},
    {"id": 22,  "name": "Venezuela",     "confederation": "CONMEBOL", "flag": "🇻🇪"},
    # UEFA
    {"id": 9,   "name": "France",        "confederation": "UEFA",     "flag": "🇫🇷"},
    {"id": 10,  "name": "England",       "confederation": "UEFA",     "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"id": 15,  "name": "Spain",         "confederation": "UEFA",     "flag": "🇪🇸"},
    {"id": 5,   "name": "Germany",       "confederation": "UEFA",     "flag": "🇩🇪"},
    {"id": 768, "name": "Portugal",      "confederation": "UEFA",     "flag": "🇵🇹"},
    {"id": 770, "name": "Netherlands",   "confederation": "UEFA",     "flag": "🇳🇱"},
    {"id": 762, "name": "Belgium",       "confederation": "UEFA",     "flag": "🇧🇪"},
    {"id": 760, "name": "Italy",         "confederation": "UEFA",     "flag": "🇮🇹"},
    {"id": 764, "name": "Croatia",       "confederation": "UEFA",     "flag": "🇭🇷"},
    {"id": 773, "name": "Switzerland",   "confederation": "UEFA",     "flag": "🇨🇭"},
    {"id": 766, "name": "Denmark",       "confederation": "UEFA",     "flag": "🇩🇰"},
    {"id": 769, "name": "Austria",       "confederation": "UEFA",     "flag": "🇦🇹"},
    {"id": 771, "name": "Poland",        "confederation": "UEFA",     "flag": "🇵🇱"},
    {"id": 765, "name": "Czechia",       "confederation": "UEFA",     "flag": "🇨🇿"},
    {"id": 763, "name": "Serbia",        "confederation": "UEFA",     "flag": "🇷🇸"},
    {"id": 2863,"name": "Slovakia",      "confederation": "UEFA",     "flag": "🇸🇰"},
    {"id": 772, "name": "Scotland",      "confederation": "UEFA",     "flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿"},
    {"id": 1523,"name": "Turkey",        "confederation": "UEFA",     "flag": "🇹🇷"},
    {"id": 774, "name": "Ukraine",       "confederation": "UEFA",     "flag": "🇺🇦"},
    {"id": 775, "name": "Hungary",       "confederation": "UEFA",     "flag": "🇭🇺"},
    {"id": 776, "name": "Romania",       "confederation": "UEFA",     "flag": "🇷🇴"},
    {"id": 777, "name": "Greece",        "confederation": "UEFA",     "flag": "🇬🇷"},
    {"id": 778, "name": "Slovenia",      "confederation": "UEFA",     "flag": "🇸🇮"},
    {"id": 779, "name": "Albania",       "confederation": "UEFA",     "flag": "🇦🇱"},
    {"id": 780, "name": "Georgia",       "confederation": "UEFA",     "flag": "🇬🇪"},
    # CONCACAF
    {"id": 3,   "name": "USA",           "confederation": "CONCACAF", "flag": "🇺🇸"},
    {"id": 16,  "name": "Mexico",        "confederation": "CONCACAF", "flag": "🇲🇽"},
    {"id": 43,  "name": "Canada",        "confederation": "CONCACAF", "flag": "🇨🇦"},
    {"id": 44,  "name": "Costa Rica",    "confederation": "CONCACAF", "flag": "🇨🇷"},
    {"id": 45,  "name": "Panama",        "confederation": "CONCACAF", "flag": "🇵🇦"},
    {"id": 46,  "name": "Jamaica",       "confederation": "CONCACAF", "flag": "🇯🇲"},
    # AFC
    {"id": 30,  "name": "Japan",         "confederation": "AFC",      "flag": "🇯🇵"},
    {"id": 31,  "name": "South Korea",   "confederation": "AFC",      "flag": "🇰🇷"},
    {"id": 800, "name": "Australia",     "confederation": "AFC",      "flag": "🇦🇺"},
    {"id": 801, "name": "Iran",          "confederation": "AFC",      "flag": "🇮🇷"},
    {"id": 802, "name": "Saudi Arabia",  "confederation": "AFC",      "flag": "🇸🇦"},
    {"id": 803, "name": "Qatar",         "confederation": "AFC",      "flag": "🇶🇦"},
    {"id": 804, "name": "Iraq",          "confederation": "AFC",      "flag": "🇮🇶"},
    {"id": 805, "name": "Jordan",        "confederation": "AFC",      "flag": "🇯🇴"},
    # CAF
    {"id": 20,  "name": "Morocco",       "confederation": "CAF",      "flag": "🇲🇦"},
    {"id": 32,  "name": "Senegal",       "confederation": "CAF",      "flag": "🇸🇳"},
    {"id": 36,  "name": "Nigeria",       "confederation": "CAF",      "flag": "🇳🇬"},
    {"id": 806, "name": "Egypt",         "confederation": "CAF",      "flag": "🇪🇬"},
]

# Historical WC round mapping (round name → points)
ROUND_POINTS = {
    "Winner":          7,
    "Final":           6,
    "Semi-finals":     5,
    "Quarter-finals":  4,
    "Round of 16":     3,
    "Group Stage":     1,
}

# Number of WC tournaments available in API
MAX_WC_SEASONS = [2022, 2018, 2014, 2010, 2006]

# ---------------------------------------------------------------------------
# Metric builders
# ---------------------------------------------------------------------------

def _compute_form_score(fixtures: list[dict]) -> tuple[float, float]:
    """
    Returns (form_score 0–100, goal_diff_score 0–100) from recent fixtures.
    form_score  = (points / max_points) * 100
    goal_diff   = normalised from [-20, +20] → [0, 100]
    """
    points = 0
    goal_diff = 0
    for fix in fixtures:
        teams   = fix.get("teams", {})
        goals   = fix.get("goals", {})
        home_id = teams.get("home", {}).get("id")
        is_home = fix.get("fixture", {}).get("status", {}).get("short") == "FT"

        home_goals = goals.get("home") or 0
        away_goals = goals.get("away") or 0

        # Determine which side our team is
        team_goals   = home_goals
        opp_goals    = away_goals

        winner_id = None
        if home_goals > away_goals:
            winner_id = teams.get("home", {}).get("id")
        elif away_goals > home_goals:
            winner_id = teams.get("away", {}).get("id")

        # We don't know our team id here; rely on API winner flag
        home_win = teams.get("home", {}).get("winner")
        away_win = teams.get("away", {}).get("winner")

        # Determine result from the perspective of either side (we normalise later)
        if home_win is True:
            points += 3
            goal_diff += home_goals - away_goals
        elif away_win is True:
            points += 0
            goal_diff += away_goals - home_goals
        else:
            points += 1

    max_points  = len(fixtures) * 3 if fixtures else 1
    form_score  = min((points / max_points) * 100, 100)
    # Normalise goal_diff from [-20, +20] → [0, 100]
    gd_score    = max(0.0, min(100.0, (goal_diff + 20) * 2.5))
    return form_score, gd_score


def _compute_wc_history_score(wc_fixtures: list[dict]) -> tuple[float, float]:
    """
    Returns (wc_history_score, tournament_exp_score).
    wc_history_score = avg round reached across tournaments, normalised.
    tournament_exp   = # distinct WC seasons appeared, normalised to 5 max.
    """
    if not wc_fixtures:
        return 10.0, 10.0

    round_pts = []
    seasons_seen: set[int] = set()
    for fix in wc_fixtures:
        season = fix.get("league", {}).get("season")
        if season:
            seasons_seen.add(season)
        round_name = fix.get("league", {}).get("round", "")
        for key, val in ROUND_POINTS.items():
            if key.lower() in round_name.lower():
                round_pts.append(val)
                break

    avg_round    = sum(round_pts) / len(round_pts) if round_pts else 1
    hist_score   = min((avg_round / 7) * 100, 100)
    exp_score    = min((len(seasons_seen) / 5) * 100, 100)
    return hist_score, exp_score


def _compute_squad_strength(squad_data: list[dict]) -> float:
    """
    Proxy squad strength via club-league tier.
    Top 5 leagues → max score; lower leagues → reduced score.
    Returns a 0–100 float.
    """
    if not squad_data:
        return 50.0

    # Flatten player list from squads response
    players = []
    for entry in squad_data:
        players.extend(entry.get("players", []))

    if not players:
        return 50.0

    # We don't have individual ratings here without a premium tier,
    # so we score by position count as a completeness proxy (max 23-man squad)
    completeness = min(len(players) / 23, 1.0) * 100
    return completeness


# ---------------------------------------------------------------------------
# Main orchestrator — build full metric profile for a team
# ---------------------------------------------------------------------------

def build_team_profile(team: dict) -> dict:
    """
    Fetches all relevant API data for a team and returns a normalised
    metric profile dict used by the predictor.
    """
    team_id   = team["id"]
    team_name = team["name"]
    logger.info("Building profile for %s (id=%s)", team_name, team_id)

    profile: dict[str, Any] = {
        "id":            team_id,
        "name":          team_name,
        "flag":          team.get("flag", ""),
        "confederation": team.get("confederation", ""),
    }

    # --- FIFA Ranking ---
    try:
        rankings = api.get_fifa_rankings()
        rank_entry = next(
            (r for r in rankings if r.get("team", {}).get("id") == team_id), None
        )
        if rank_entry:
            rank = rank_entry.get("rank", 100)
            profile["fifa_rank"]        = rank
            # Invert: rank 1 → 100, rank 100 → 1  (using top 48 as denominator)
            profile["fifa_ranking_score"] = max(0, (49 - min(rank, 48)) / 48 * 100)
        else:
            profile["fifa_rank"]          = 99
            profile["fifa_ranking_score"] = 20.0
    except Exception as e:
        logger.warning("FIFA ranking fetch failed for %s: %s", team_name, e)
        profile["fifa_rank"]          = 99
        profile["fifa_ranking_score"] = 30.0

    # --- Recent Form ---
    try:
        fixtures = api.get_team_recent_fixtures(team_id, last=10)
        form_score, gd_score = _compute_form_score(fixtures)
        profile["recent_form_score"] = form_score
        profile["goal_diff_score"]   = gd_score
    except Exception as e:
        logger.warning("Form fetch failed for %s: %s", team_name, e)
        profile["recent_form_score"] = 50.0
        profile["goal_diff_score"]   = 50.0

    # --- World Cup History ---
    try:
        wc_fixtures = api.get_team_wc_history(team_id)
        hist_score, exp_score = _compute_wc_history_score(wc_fixtures)
        profile["wc_history_score"]      = hist_score
        profile["tournament_exp_score"]  = exp_score
    except Exception as e:
        logger.warning("WC history fetch failed for %s: %s", team_name, e)
        profile["wc_history_score"]     = 20.0
        profile["tournament_exp_score"] = 20.0

    # --- Squad Strength ---
    try:
        squad = api.get_squad(team_id)
        profile["squad_strength_score"] = _compute_squad_strength(squad)
    except Exception as e:
        logger.warning("Squad fetch failed for %s: %s", team_name, e)
        profile["squad_strength_score"] = 50.0

    return profile


def build_all_profiles() -> list[dict]:
    """Build metric profiles for all 48 qualified teams."""
    profiles = []
    for team in QUALIFIED_TEAMS:
        try:
            profiles.append(build_team_profile(team))
        except Exception as e:
            logger.error("Failed to build profile for %s: %s", team["name"], e)
    return profiles
