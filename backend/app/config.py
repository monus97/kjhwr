"""Central configuration. Every tunable lives here so reviewers can find it in one place."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc

# --- Elexon BMRS (Insights Solution) API -----------------------------------
ELEXON_BASE_URL = os.getenv("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")
ACTUALS_PATH = "/datasets/FUELHH/stream"   # actual generation by fuel type, 30-min
FORECAST_PATH = "/datasets/WINDFOR/stream"  # national wind generation forecast
WIND_FUEL_TYPE = "WIND"
HTTP_TIMEOUT_S = float(os.getenv("ELEXON_TIMEOUT_S", "30"))
FETCH_CHUNK_DAYS = 3  # keep each request small; the stream endpoints dislike huge ranges

# --- Scope: purchase decisions made in January 2026 -------------------------
# A day-ahead decision taken on day D-1 is for delivery day D. Decisions taken on
# 1-31 Jan 2026 therefore cover delivery from 2 Jan to 1 Feb. We load all of
# January plus 1 Feb so every one of those delivery days is complete, and pull
# forecasts published from a few days earlier so long horizons (up to 48h+) at the
# start of the month still have a forecast to choose from.
TARGET_START = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
TARGET_END = datetime(2026, 2, 2, 0, 0, tzinfo=UTC)  # exclusive
FORECAST_PUBLISH_START = datetime(2025, 12, 28, 0, 0, tzinfo=UTC)
FORECAST_PUBLISH_END = TARGET_END  # exclusive

# --- Analysis defaults ------------------------------------------------------
DEFAULT_HORIZON_H = 24.0
MAX_HORIZON_H = 48.0
# GB day-ahead auctions close mid-morning on D-1; 09:00 UK time is a sensible
# "decision moment" default (UK is on GMT = UTC throughout January).
DEFAULT_DECISION_TIME = "09:00"

# --- Storage ----------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
# Snapshot committed to the repo by scripts/fetch_data.py (fast, offline-safe).
DATA_DIR = Path(os.getenv("DATA_DIR", BACKEND_DIR / "data"))
# Writable cache for live fetches (Vercel only allows writes under /tmp).
CACHE_DIR = Path(os.getenv("CACHE_DIR", "/tmp/wind-forecast-cache"))

# Built React app, served by FastAPI in the Docker image (optional).
FRONTEND_DIST = os.getenv("FRONTEND_DIST", "")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
