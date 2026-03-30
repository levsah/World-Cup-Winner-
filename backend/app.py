"""
app.py — Flask REST API for the 2026 World Cup Predictor
"""

import logging
import os
import sys
import time

from flask import Flask, jsonify, send_from_directory, request, abort
from flask_cors import CORS
from flask_caching import Cache

sys.path.insert(0, os.path.dirname(__file__))

from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, CACHE_TIMEOUT_SECONDS, APISPORTS_KEY
from data_processor import build_all_profiles
from predictor import run_monte_carlo

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(
    __name__,
    static_folder=os.path.join(FRONTEND_DIR, "static"),
    template_folder=FRONTEND_DIR,
)
CORS(app, origins=[
    f"http://localhost:{FLASK_PORT}",
    f"http://127.0.0.1:{FLASK_PORT}",
])

cache = Cache(app, config={
    "CACHE_TYPE":             "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT":  CACHE_TIMEOUT_SECONDS,
})

# Rate-limit state for forced refresh (prevents API quota exhaustion)
_last_refresh: float = 0.0
_REFRESH_COOLDOWN = 60  # seconds


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"]         = "DENY"
    response.headers["Referrer-Policy"]         = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self';"
    )
    return response


# ---------------------------------------------------------------------------
# Routes — Frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "static"), filename)


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "api_key_set": bool(APISPORTS_KEY),
        "timestamp": int(time.time()),
    })


@app.route("/api/predict")
@cache.cached(timeout=CACHE_TIMEOUT_SECONDS, key_prefix="predict")
def api_predict():
    """
    Fetch live data from API-Football, run Monte Carlo simulation,
    and return ranked predictions.
    """
    try:
        profiles = build_all_profiles()
        rankings = run_monte_carlo(profiles)
        return jsonify({
            "status":   "ok",
            "rankings": rankings,
            "winner":   rankings[0] if rankings else None,
            "top_5":    rankings[:5],
            "weights":  {
                "FIFA Ranking":          "20%",
                "Recent Form":           "25%",
                "WC History":            "15%",
                "Squad Strength":        "20%",
                "Goal Difference":       "10%",
                "Tournament Experience": "10%",
            },
            "simulations": 50_000,
        })
    except RuntimeError as e:
        # Missing API key
        return jsonify({"status": "error", "message": str(e)}), 503
    except Exception as e:
        logger.exception("Prediction failed")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@app.route("/api/predict/refresh", methods=["POST"])
def api_predict_refresh():
    """Force-clear the cache and re-run the simulation (rate-limited to 1/min)."""
    global _last_refresh
    now = time.time()
    remaining = _REFRESH_COOLDOWN - (now - _last_refresh)
    if remaining > 0:
        return jsonify({
            "status": "error",
            "message": f"Too many requests. Wait {int(remaining)}s before refreshing again.",
        }), 429
    _last_refresh = now
    cache.delete("predict")
    return api_predict()


@app.route("/api/teams")
def api_teams():
    """Return the list of all 48 qualified teams."""
    from data_processor import QUALIFIED_TEAMS
    return jsonify(QUALIFIED_TEAMS)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "message": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"status": "error", "message": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not APISPORTS_KEY:
        logger.warning(
            "⚠️  APISPORTS_KEY is not set. "
            "Create a .env file — see .env.example for instructions."
        )
    logger.info("Starting server → http://localhost:%s", FLASK_PORT)
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
