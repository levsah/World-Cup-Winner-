# ============================================================
# 2026 World Cup Predictor — Configuration
# ============================================================
import os
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# API-Sports (direct — faster, no middleman)
# Get your free key at: https://dashboard.api-football.com/register
# Free tier: 100 requests / day
# ------------------------------------------------------------------
RAPIDAPI_KEY    = os.getenv("RAPIDAPI_KEY", "")
APISPORTS_KEY   = os.getenv("APISPORTS_KEY", "")   # kept for backwards compat
API_BASE_URL    = "https://api-football-v1.p.rapidapi.com"
RAPIDAPI_HOST   = "api-football-v1.p.rapidapi.com"

# ------------------------------------------------------------------
# API-Football league / competition IDs
# ------------------------------------------------------------------
WC_LEAGUE_ID        = 1      # FIFA World Cup
WC_2026_SEASON      = 2026
WC_2022_SEASON      = 2022
NATIONS_LEAGUE_ID   = 6      # UEFA Nations League (recent form proxy)
CONFED_CUP_IDS      = {
    "UEFA":    4,    # UEFA Euro / qualifiers
    "CONMEBOL": 9,   # Copa América
    "CONCACAF": 30,
    "CAF":      6,   # AFCON
    "AFC":      7,   # Asian Cup
    "OFC":      8,
}

# ------------------------------------------------------------------
# Prediction model weights
# Each weight is the relative importance of that metric (sum = 1)
# ------------------------------------------------------------------
WEIGHTS = {
    "fifa_ranking":          0.20,   # Current FIFA world ranking (with embedded fallback)
    "recent_form":           0.20,   # Last 10 international results (team-perspective-aware)
    "wc_history":            0.12,   # Historical World Cup performance
    "squad_strength":        0.08,   # Squad completeness (23-man roster bonus)
    "goal_difference":       0.10,   # Recent matches goal difference
    "tournament_experience": 0.10,   # # of WC appearances
    "player_performance":    0.20,   # Per-team player quality (stars + squad depth)
}

# ------------------------------------------------------------------
# Simulation settings
# ------------------------------------------------------------------
MONTE_CARLO_SIMULATIONS = 50_000   # Number of tournament simulations

# ------------------------------------------------------------------
# Caching
# ------------------------------------------------------------------
CACHE_TIMEOUT_SECONDS = 3600       # 1 hour — API data doesn't change hourly

# ------------------------------------------------------------------
# Flask
# ------------------------------------------------------------------
FLASK_HOST  = "0.0.0.0"
FLASK_PORT  = 8080
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
