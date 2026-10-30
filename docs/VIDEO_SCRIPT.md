# Video script (target 9 minutes total)

Record the deployed app. Keep the browser at 125% zoom so charts are readable. Numbers in
brackets are placeholders — read the real values off the Accuracy tab before recording.

---

## Part 1 — Client pitch (≤ 5 min)

**[0:00] Open on the Decision view, 15 Jan selected.**

"Good morning. Your desk buys power on the day-ahead market, and every morning you have to decide
how much to buy before you know how much wind will actually show up. Over the pilot we built a
monitor that answers two questions: *what did we know when we bought*, and *how much should we
trust it*. Everything you see is national GB wind from Elexon — the same numbers you already use —
for the January 2026 trading month."

**[0:40] Decision view.**

"This is the view for one delivery day. The date is the delivery day; the time is your decision
moment on the day before — 09:00 by default, you can change it. The orange line is the wind
forecast *exactly as it existed at that moment*. Not the latest one, not the one from this morning —
the one you could actually have seen. The blue line is what happened."

Hover a point. "Each half-hour shows the forecast, the actual, the error, and how far ahead that
forecast was issued — here 28 hours."

"The shaded band is the range that past January errors at this lead time would have put around
this forecast. In nine cases out of ten, the actual fell inside this band. That band is the practical
answer to 'how much buffer do I hold'."

Click Next day two or three times. "Every day in the month, same view. Here's a day it got right…
here's one where the forecast ran [1.7 GW] high — that's [1.7 GW] you'd have had to buy intraday."

**[2:10] Accuracy view, horizon at 24h.**

"Second question: how good is the forecast in general? Across the whole of January, a day ahead,
the forecast missed by [X MW] on average — about [Y %] of typical output. The bias is [+Z MW]: it
tends to run slightly [high/low]. And the number I'd put on your wall: on nine days out of ten,
the shortfall was less than [P90 MW]. Hold that much cover and you're protected 90% of the time."

**[3:00] Drag the slider from 6 h to 48 h.**

"Now the interesting part. Here's the same evaluation if you'd had to decide six hours ahead…
twelve… twenty-four… forty-eight. The chart on the left shows how error grows with lead time. The
value of waiting until the gate closes, versus hedging two days out, is visible in megawatts."

**[3:40] By-hour and distribution charts.**

"By hour of day: the forecast runs [high in the early morning / low in the afternoon]. That's a
systematic pattern you can trade on. And the distribution: most misses are small, but there's a
tail — those are the days to watch."

**[4:15] Close.**

"To summarise: one screen to see the forecast you actually bought on, one screen to size your
buffer, every number traceable to Elexon. The pilot covers January; extending to a rolling window
and adding your own demand forecast is straightforward. Thank you."

---

## Part 2 — Tech lead review (≤ 5 min)

**[0:00] Repo README open at the layout tree.**

"Python backend, React frontend, Docker, deployed on Vercel. Let me go through architecture, the
core rule, data, tests and what I'd change."

**[0:20] Architecture diagram in README.**

"Data is historical and immutable, so I fetch January once with a script, commit a compact JSON
snapshot, and load it into memory at start. Every request is sub-100 ms and nothing depends on
Elexon being up. Live fetch exists as a fallback. The backend is Starlette — FastAPI's core without
the extra weight, which matters for serverless cold starts. No numpy: the dataset is small and
`bisect` is enough."

**[1:00] `backend/app/forecasting.py`.**

"This is the file I'd want you to read. WINDFOR has many forecasts per half-hour, each with its own
publishTime. The whole product reduces to: *latest forecast with publishTime ≤ cut-off*. For the
horizon view the cut-off is T minus H; for the decision view it's a single decision moment. I index
forecasts by target time, sort by publish time, and binary-search. Using anything later would be
hindsight leaking into the evaluation."

**[1:45] `backend/tests/test_forecasting.py`.**

"Thirty-three tests. These pin the rule: inclusive cut-off, falling back to an older run at long
horizons, returning None when no run is old enough, and a leakage guard that asserts no chosen
forecast was published after the cut-off. Metrics are tested against hand-computed numbers; the API
tests go through the ASGI app with an injected dataset."

**[2:30] `metrics.py` and `service.py`.**

"Error is forecast minus actual throughout — positive means a shortfall. I deliberately skipped MAPE
because it explodes in calm periods; I show normalised MAE instead. Signed percentiles are what the
desk uses: P90 of the error is the buffer. The band on the decision view is an empirical backtest by
lead-time hour, computed once per process and cached — I label it as empirical, not a model."

**[3:10] `elexon_client.py` and `scripts/fetch_data.py`.**

"Chunked requests, retry with backoff, WIND rows only, latest publication wins if an actual is
revised. Timestamps are parsed to aware UTC on entry and never touched again; the UI formats in UTC.
January is GMT, so local equals UTC."

**[3:40] Frontend.**

"Vite + React + Recharts, two screens, one `api.js` that knows the backend URL. Horizon slider is
debounced. Colours are a colour-blind-safe pair and every series is also labelled. Light and dark
via CSS tokens."

**[4:00] Docker, CI, deploy.**

"Multi-stage Dockerfile builds the UI and serves it from the Python process on one port — that's
what Heroku runs. Compose gives hot reload for dev. CI runs ruff, pytest, eslint, the Vite build and
the Docker build. Vercel serves the static build and routes /api to a Python function."

**[4:30] Trade-offs and next steps.**

"Trade-offs: snapshot over live means a refresh script, not a scheduler; Starlette over FastAPI means
no auto-docs. Next: proper quantile calibration for the band, more forecast sources, CSV export,
and a rolling window with a scheduled refresh. AI assistance was used and is declared in the README;
every line was reviewed. Happy to take questions."
