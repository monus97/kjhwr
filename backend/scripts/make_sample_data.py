"""Generate a SYNTHETIC January 2026 dataset with the same shape as the Elexon data.

Use this only for offline development / tests. Real data: scripts/fetch_data.py.

  python scripts/make_sample_data.py            -> writes backend/data-sample/
  DATA_DIR=backend/data-sample uvicorn app.main:app

The generator mimics the real structure: a smooth-ish "true" wind signal at 30-min
resolution, and forecast runs issued every 6 hours whose error grows with lead time.
"""
from __future__ import annotations

import math
import random
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.data_store import save_snapshot  # noqa: E402
from app.models import Actual, Forecast  # noqa: E402

CAPACITY_MW = 22000.0


def true_wind(hour: float, rng: random.Random, state: dict) -> float:
    # Slow weather systems (~3 days) + diurnal ripple + random walk, clipped to capacity.
    base = 0.45 + 0.35 * math.sin(hour / 72.0 * 2 * math.pi + 1.0) + 0.1 * math.sin(hour / 24.0 * 2 * math.pi)
    state["walk"] = max(-0.25, min(0.25, state["walk"] + rng.gauss(0, 0.02)))
    return max(0.0, min(CAPACITY_MW, CAPACITY_MW * (base + state["walk"])))


def main(out_dir: Path = config.BACKEND_DIR / "data-sample", seed: int = 7) -> None:
    rng = random.Random(seed)
    state = {"walk": 0.0}
    actuals: list[Actual] = []
    t = config.FORECAST_PUBLISH_START
    truth = {}
    while t < config.TARGET_END + timedelta(days=3):
        hours = (t - config.FORECAST_PUBLISH_START).total_seconds() / 3600
        truth[t] = true_wind(hours, rng, state)
        if config.TARGET_START <= t < config.TARGET_END:
            actuals.append(Actual(t, round(truth[t], 1)))
        t += timedelta(minutes=30)

    forecasts: list[Forecast] = []
    pub = config.FORECAST_PUBLISH_START
    while pub < config.FORECAST_PUBLISH_END:
        run_bias = rng.gauss(0, 400)  # each run has its own systematic offset
        target = pub + timedelta(minutes=30)
        while target <= pub + timedelta(hours=72):
            lead_h = (target - pub).total_seconds() / 3600
            noise = rng.gauss(0, 250 + 45 * lead_h)  # error grows with lead time
            value = max(0.0, min(CAPACITY_MW, truth[target] + run_bias * (lead_h / 24) + noise))
            forecasts.append(Forecast(target, pub, round(value, 1)))
            target += timedelta(minutes=30)
        pub += timedelta(hours=6)

    save_snapshot(out_dir, actuals, forecasts)
    print(f"wrote {len(actuals)} actuals and {len(forecasts)} forecasts to {out_dir}")


if __name__ == "__main__":
    main()
