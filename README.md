# 2026 FIFA World Cup Predictor

AI-powered prediction engine using **live data** from API-Football + 50,000 Monte Carlo simulations.

## How it works

| Layer | Technology |
|---|---|
| Live data | API-Football via RapidAPI |
| Backend | Python / Flask |
| Simulation | Monte Carlo (50,000 runs) + Poisson goal model |
| Frontend | Vanilla HTML / CSS / JS |

**6 live metrics** are fetched and weighted:
- **25%** Recent form (last 10 fixtures)
- **20%** Current FIFA ranking
- **20%** Squad strength
- **15%** World Cup history (2006–2022)
- **10%** Goal difference (recent form window)
- **10%** Tournament experience (# of WC appearances)

## Quick start

### 1. Get a free API key
Sign up at [rapidapi.com/api-sports/api/api-football](https://rapidapi.com/api-sports/api/api-football) — the free tier covers all endpoints used here.

### 2. Configure
```bash
cp .env.example .env
# Edit .env and set RAPIDAPI_KEY=your_key_here
```

### 3. Run
```bash
./start.sh
# Opens at http://localhost:5000
```

Or manually:
```bash
cd backend
pip install -r requirements.txt
python app.py
```

## Project structure

```
World-Cup-Winner-/
├── backend/
│   ├── app.py              # Flask REST API
│   ├── api_client.py       # API-Football wrapper (cached)
│   ├── data_processor.py   # Metric builder from raw API data
│   ├── predictor.py        # Monte Carlo simulator
│   ├── config.py           # Weights, API config, settings
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── .env.example
├── start.sh
└── README.md
```

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Frontend UI |
| `/api/health` | GET | Server health + API key status |
| `/api/predict` | GET | Run prediction (cached 1 hr) |
| `/api/predict/refresh` | POST | Force re-simulation |
| `/api/teams` | GET | All 48 qualified teams |
