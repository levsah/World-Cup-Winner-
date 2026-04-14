"""
api_client.py
=============
Handles all communication with the API-Sports v3 service.
  Base URL : https://v3.football.api-sports.io
  Auth     : single header  x-apisports-key: <key>
Responses are cached in-memory to respect the 100 req/day free-tier limit.

Endpoints used:
  GET /standings/timezone     → (health / account check)
  GET /rankings/fifa          → Current FIFA world rankings
  GET /fixtures               → Match results (form, H2H)
  GET /teams/statistics       → Aggregated team stats per competition
  GET /players/squads         → Squad / player data
"""

import time
import logging
from functools import lru_cache
from typing import Any

import requests

from config import RAPIDAPI_KEY, APISPORTS_KEY, API_BASE_URL, RAPIDAPI_HOST, CACHE_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Simple time-aware in-memory cache (avoids external cache dependency here)
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, Any]] = {}


def _cached_get(endpoint: str, params: dict) -> dict:
    """GET an API-Sports endpoint, serving from cache when fresh."""
    cache_key = endpoint + str(sorted(params.items()))
    now = time.time()
    if cache_key in _cache:
        cached_at, data = _cache[cache_key]
        if now - cached_at < CACHE_TIMEOUT_SECONDS:
            logger.debug("Cache hit: %s", cache_key)
            return data

    api_key = RAPIDAPI_KEY or APISPORTS_KEY
    if not api_key:
        raise RuntimeError(
            "No API key set. Add RAPIDAPI_KEY=<your_key> to your .env file."
        )

    if RAPIDAPI_KEY:
        headers = {
            "x-rapidapi-key":  RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
        }
    else:
        headers = {"x-apisports-key": APISPORTS_KEY}
    url = f"{API_BASE_URL}/{endpoint}"
    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    _cache[cache_key] = (now, data)
    return data


# ---------------------------------------------------------------------------
# Public API helpers
# ---------------------------------------------------------------------------

def get_fifa_rankings() -> list[dict]:
    """
    Returns a list of dicts:
      { rank, team_id, team_name, team_logo, points, ... }
    """
    data = _cached_get("rankings/fifa", {})
    return data.get("response", [])


def get_team_recent_fixtures(team_id: int, last: int = 10) -> list[dict]:
    """
    Returns the last N international fixtures for a team.
    Includes result (W/D/L), goals scored/conceded.
    """
    data = _cached_get("fixtures", {
        "team":   team_id,
        "last":   last,
        "type":   "international",   # filter to international matches only
    })
    return data.get("response", [])


def get_team_wc_history(team_id: int) -> list[dict]:
    """
    Returns fixtures for the given team across all past World Cups
    (league = 1, seasons 1930–2022).
    Note: API-Football free tier limits historical depth.
    We fetch 2018 and 2022 tournament fixtures as a proxy.
    """
    results = []
    for season in [2018, 2022]:
        data = _cached_get("fixtures", {
            "team":   team_id,
            "league": 1,          # FIFA World Cup
            "season": season,
        })
        results.extend(data.get("response", []))
    return results


def get_team_statistics(team_id: int, league_id: int, season: int) -> dict:
    """
    Returns aggregated team statistics in a given competition+season.
    Includes: fixtures played, wins, draws, losses, goals for/against,
              clean sheets, average possession, etc.
    """
    data = _cached_get("teams/statistics", {
        "team":   team_id,
        "league": league_id,
        "season": season,
    })
    return data.get("response", {})


def get_squad(team_id: int, season: int = 2025) -> list[dict]:
    """
    Returns player metadata for the squad.
    Each entry includes: player name, age, nationality, position.
    (Market value / ratings require a premium Transfermarkt API;
     we derive quality from the player's club league tier instead.)
    """
    data = _cached_get("players/squads", {"team": team_id})
    return data.get("response", [])


def get_wc_standings(season: int = 2026) -> list[dict]:
    """
    Returns group-stage standings for the World Cup.
    Will be empty pre-tournament; useful once the competition starts.
    """
    data = _cached_get("standings", {
        "league": 1,
        "season": season,
    })
    return data.get("response", [])


def get_team_by_name(name: str) -> dict | None:
    """Search for a team by name and return its API metadata."""
    data = _cached_get("teams", {"search": name})
    results = data.get("response", [])
    return results[0] if results else None


def get_fixture_h2h(team1_id: int, team2_id: int, last: int = 10) -> list[dict]:
    """Head-to-head results between two teams (last N meetings)."""
    data = _cached_get("fixtures/headtohead", {
        "h2h":  f"{team1_id}-{team2_id}",
        "last": last,
    })
    return data.get("response", [])
