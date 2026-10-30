# Architecture notes

## Request flow

```
┌──────────┐   GET /api/decision?delivery_day&decision_time   ┌───────────────────────┐
│  React   │ ───────────────────────────────────────────────► │ main.py (Starlette)   │
│ (Vite)   │ ◄─────────────── JSON view model ─────────────── │   parse query → 400   │
└──────────┘                                                  └──────────┬────────────┘
                                                                         ▼
                                                              ┌───────────────────────┐
                                                              │ service.py            │
                                                              │  decision_view        │
                                                              │  accuracy_view        │
                                                              │  horizon_curve        │
                                                              └──────┬────────┬───────┘
                                                                     ▼        ▼
                                                   ┌──────────────────┐  ┌─────────────┐
                                                   │ forecasting.py   │  │ metrics.py  │
                                                   │ ForecastIndex    │  │ summarize   │
                                                   │ latest_before()  │  │ by_hour…    │
                                                   └────────┬─────────┘  └─────────────┘
                                                            ▼
                                                   ┌──────────────────┐
                                                   │ data_store.py    │  snapshot → cache → live
                                                   │ Dataset (memory) │◄── elexon_client.py ◄── Elexon
                                                   └──────────────────┘
```

## Data model

| Record | Fields | Source |
|---|---|---|
| `Actual` | `start_time` (UTC), `generation_mw` | FUELHH, `fuelType == WIND`, latest publication per slot |
| `Forecast` | `start_time`, `publish_time`, `generation_mw` | WINDFOR, de-duplicated on (start, publish) |
| `Pair` | `start_time`, `actual_mw?`, `forecast_mw?`, `publish_time?` → `lead_hours`, `error_mw` | derived |

## Forecast selection

`ForecastIndex` maps each target time to a sorted list of `(publish_time, value)`.
`latest_before(target, cutoff)` is `bisect_right(publish_times, cutoff) - 1`.

| View | cut-off per target T | question |
|---|---|---|
| Horizon H | `T − H` | accuracy of forecasts issued ≥ H hours ahead |
| Decision | `decision_time` (constant for the day) | what the desk saw at 09:00 on D-1 |

Both reject hindsight: no chosen forecast was published after its cut-off (tested).

## Complexity

- Index build: O(F log F) once at start (F = forecast rows).
- Each view: O(N log R) where N = targets in window, R = runs per target (~tens).
- Horizon curve: 25 horizons × N — still < 100 ms for the full month.
- Error-band quantiles: 49 horizons over the full month, computed once per process.

## Storage

JSON arrays, not objects: `[[t, v], …]` and `[[t, publish, v], …]`. The full month compresses
well and loads in well under a second. No database is justified for one immutable month; the
`Dataset` object is the only state, built once per process (thread-safe double-checked lock).

## Deployment shapes

| Shape | UI | API | Used for |
|---|---|---|---|
| Dockerfile | built into image, served by Starlette `StaticFiles` | same process | Heroku, any container host |
| Vercel | static build from `frontend/dist` | `api/index.py` serverless function | submitted demo |
| Compose | Vite dev server (proxy `/api`) | uvicorn `--reload` | local development |
