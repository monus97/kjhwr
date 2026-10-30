# Wind Forecast Monitor — GB day-ahead, January 2026

A small web app for a UK supplier's day-ahead procurement desk. It answers two questions
using only Elexon BMRS national wind data:

1. **What did we know when we bought?** For any delivery day, show the latest wind forecast
   that existed at the moment the day-ahead decision was taken (default 09:00 UTC on D-1), and —
   in hindsight — what actually happened.
2. **How much should we trust it?** Quantify forecast error (MAE, RMSE, bias, P10/P50/P90) for
   any window in January and any forecast horizon from 0 to 48 hours, so the desk can size a buffer.

**Live app:** `https://<your-deployment>.vercel.app` ← *replace after deploying (see below)*

> AI assistance: this codebase was written with the help of an AI coding assistant (Anthropic's
> Claude). All design decisions, the forecast-selection rule, tests and this README were reviewed by
> the author. See "AI tools" at the end.

---

## The one rule that matters

The WINDFOR dataset holds **many forecasts for the same half-hour**, each issued at a different
`publishTime`. Comparing "the forecast" with the actual is meaningless until you fix *when you look*.
Everything in this app reduces to one rule:

> For target time **T** and cut-off **C**, use the latest forecast with `publishTime ≤ C`.

- **Horizon view:** `C = T − H` (e.g. H = 24 h → "the forecast as it stood a day ahead of each half-hour").
- **Decision view:** `C = decision moment on D-1` (one cut-off for the whole delivery day).

Forecasts published after the cut-off are never used — that would be hindsight leaking into the
evaluation. `backend/app/forecasting.py` implements this with a per-target binary search;
`backend/tests/test_forecasting.py` pins it down, including the leakage guard.

Error sign convention everywhere: **error = forecast − actual**. Positive = less wind arrived than
planned = a shortfall the desk has to cover.

## Headline findings (January 2026, 24 h ahead)

- MAE ≈ 2.05 GW (≈ 18 % of mean output of 11.6 GW); RMSE ≈ 2.5 GW.
- **Bias ≈ +1.85 GW, over-forecast in 87 % of half-hours.** The error is systematic, not random.
  The likely reason: WINDFOR forecasts *available* wind, while FUELHH records *metered* output after
  curtailment (wind turned down behind transmission constraints, mostly Scotland→England). This
  should be confirmed against NESO curtailment/constraint data before being relied on.
- Practical reading for the desk: plan for roughly 1.8 GW less than the forecast, and hold a further
  buffer sized by the P90 over-forecast (≈ 4.1 GW at 24 h) to cover 9 shortfalls in 10.
- Error grows with lead time; the horizon slider shows how much a later decision would buy back.

## Scope and assumptions

- "Purchase decisions made in January 2026": a day-ahead decision on D-1 is for delivery day D, so
  decisions on 1–31 Jan cover deliveries **2 Jan – 1 Feb 2026**. The app loads actuals for
  1 Jan – 1 Feb inclusive and forecasts **published from 28 Dec 2025**, so that long horizons at the
  start of the window still have a forecast to pick.
- All times are UTC. The UK is on GMT (= UTC) throughout January, so hour-of-day analysis is in
  local time too.
- Default decision time 09:00 UTC: the GB day-ahead auction gate closes mid-morning on D-1. It is a
  control in the UI, not a hard-coded assumption.
- MAPE is deliberately not shown: it explodes when wind is near zero. Normalised MAE (MAE / mean
  actual) is shown instead.
- The P10–P90 band on the decision view is an **empirical backtest** of January error at the same
  lead time, not a probabilistic forecast model. It is labelled as such in the UI.

## Repository layout

```
.
├── backend/
│   ├── app/
│   │   ├── config.py          # every tunable: API URLs, date window, defaults, paths
│   │   ├── models.py          # Actual / Forecast / Pair dataclasses
│   │   ├── elexon_client.py   # fetch + parse FUELHH (WIND) and WINDFOR streams
│   │   ├── data_store.py      # load snapshot → cache → live fetch; in-memory dataset
│   │   ├── forecasting.py     # THE rule: latest forecast published ≤ cut-off
│   │   ├── metrics.py         # MAE / RMSE / bias / percentiles / by-hour / histogram
│   │   ├── service.py         # view models for the three screens
│   │   └── main.py            # Starlette ASGI app, routes, CORS, static serving
│   ├── scripts/
│   │   ├── fetch_data.py      # one-off download of the January dataset → backend/data/
│   │   └── make_sample_data.py# SYNTHETIC data with the same shape, for offline dev
│   ├── data/                  # committed snapshot (actuals.json, forecasts.json)
│   ├── tests/                 # pytest: rule, metrics, parsing, HTTP API (33 tests)
│   ├── requirements.txt       # runtime deps (starlette, uvicorn, requests)
│   ├── requirements-dev.txt   # + pytest, httpx, ruff
│   └── pyproject.toml         # ruff + pytest config
├── frontend/
│   ├── src/
│   │   ├── App.jsx                    # shell, tabs, dataset banner
│   │   ├── components/DecisionView.jsx# "what did we know when we bought?"
│   │   ├── components/AccuracyView.jsx# horizon slider, metrics, 4 charts, definitions
│   │   ├── components/ChartTooltip.jsx, StatTile.jsx
│   │   ├── lib/api.js                 # the only place that knows the backend URL
│   │   ├── lib/format.js              # MW / time formatting (always UTC)
│   │   └── styles.css                 # light + dark theme tokens
│   ├── index.html, vite.config.js, package.json, eslint.config.js
├── api/index.py               # Vercel Python function entry → backend app
├── vercel.json                # Vercel: build frontend, route /api/* to the function
├── Dockerfile                 # multi-stage: build UI, serve UI + API from one container
├── docker-compose.yml         # dev: hot-reload API + Vite dev server
├── heroku.yml                 # Heroku container deploy
├── requirements.txt           # root copy for Vercel's Python runtime
├── docs/                      # video script, deployment notes, architecture
└── .github/workflows/ci.yml   # ruff + pytest + eslint + vite build + docker build
```

## Running it

### 1. Get the data (once, needs internet)

```bash
cd backend
pip install -r requirements-dev.txt
python scripts/fetch_data.py          # → backend/data/actuals.json, forecasts.json
```

Commit `backend/data/` so deployments and Docker images start instantly and never depend on
Elexon's availability. If `backend/data/` is missing, the backend fetches live on first request and
caches to `CACHE_DIR` (`/tmp/...` by default).

No internet right now? `python scripts/make_sample_data.py` writes **synthetic** data to
`backend/data-sample/`; run with `DATA_DIR=data-sample`. Never present synthetic numbers as real.

### 2a. Docker (one container, production-like)

```bash
docker build -t wind-monitor .
docker run --rm -p 8000:8000 wind-monitor
# → http://localhost:8000
```

### 2b. Docker Compose (development, hot reload)

```bash
docker compose up --build
# UI  → http://localhost:5173   (Vite, proxies /api to the backend)
# API → http://localhost:8000/api/meta
```

### 2c. Bare metal

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload --port 8000
# terminal 2
cd frontend && npm install && npm run dev
```

### Tests and lint

```bash
cd backend && pytest -q && ruff check .
cd frontend && npm run lint && npm run build
```

## API

All GET, JSON, UTC ISO-8601 timestamps.

| Endpoint | Purpose |
|---|---|
| `/api/health` | liveness |
| `/api/meta` | dataset coverage, counts, defaults |
| `/api/decision?delivery_day=2026-01-15&decision_time=09:00` | forecast at the decision moment + actuals + P10–P90 band |
| `/api/accuracy?start=…&end=…&horizon=24` | paired series + summary metrics + by-hour + histogram |
| `/api/horizon-curve?start=…&end=…` | summary metrics for horizons 0,2,…,48 h |

## Architecture

```
Browser ── React (Vite, Recharts) ──► /api/* ──► Starlette (ASGI, Python)
                                                     │
                                                     ├─ data_store: JSON snapshot in memory
                                                     ├─ forecasting: latest run ≤ cut-off (bisect)
                                                     └─ metrics: pure functions, no numpy
                                                             ▲
                                   scripts/fetch_data.py ────┘  ◄── Elexon BMRS
                                   (FUELHH fuelType=WIND, WINDFOR; chunked, retried)
```

Design choices, briefly:

- **Snapshot, not live calls.** January 2026 is history and immutable. One fetch script, a committed
  JSON snapshot, everything in memory → sub-100 ms responses and no dependency on Elexon uptime.
  Live fetch remains as a fallback.
- **Logic is framework-free.** `forecasting.py`, `metrics.py` and `service.py` import nothing from
  the web layer; the tests call them directly and the HTTP routes are one-liners.
- **Starlette instead of FastAPI.** Same ASGI core, a fraction of the dependencies → fast serverless
  cold starts. Swapping to FastAPI for auto-docs is a 20-line change in `main.py` only.
- **No numpy/pandas.** The dataset is ~1.5k actuals and tens of thousands of forecast rows; plain
  Python with `bisect` is fast enough and keeps the Vercel bundle tiny.
- **Horizon slider is debounced** on the client; the horizon curve is one request per window.
- **UTC everywhere**, converted only for display. Light/dark theme via CSS tokens; chart colours are
  a colour-blind-checked pair (blue = actual, orange = forecast) and every series is also labelled.

## Deployment

Vercel (frontend static + Python function) is configured in `vercel.json` and `api/index.py`:

```bash
npm i -g vercel
vercel          # follow prompts, accept detected settings
vercel --prod
```

Heroku (Docker, `heroku.yml`):

```bash
heroku create <random-name> --stack container
git push heroku main
```

Step-by-step notes, including verification in an incognito window, are in `docs/DEPLOY.md`.

## What I would do next

- Add NESO's day-ahead wind forecast (`NDF`/`WINDFOR` variants) and the BMRS `FUELINST` 5-minute
  actuals to compare forecast sources.
- Calibrate a proper probabilistic band (quantile regression on lead time, forecast level, hour).
- Persist user presets; export CSV of any paired series.
- Alerting: flag delivery days where the decision-time forecast sits outside the historical band.

## AI tools

Anthropic's Claude was used as a coding assistant for scaffolding, drafting code, tests and
documentation. The author reviewed and takes responsibility for every file; nothing here is
unreviewed generated output.