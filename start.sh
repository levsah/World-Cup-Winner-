#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Copy .env.example if .env doesn't exist
if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Created .env from .env.example — add your APISPORTS_KEY before running."
  exit 1
fi

# Create venv if missing
if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
fi

# Activate and install deps
. "$ROOT/.venv/bin/activate"
pip install -q -r "$ROOT/backend/requirements.txt"

echo "Starting at http://localhost:8080"
cd "$ROOT/backend" && python app.py
