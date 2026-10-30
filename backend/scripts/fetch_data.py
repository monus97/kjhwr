"""Download the January 2026 wind actuals + forecasts from Elexon into backend/data.

Run once (needs internet):   python scripts/fetch_data.py
The resulting JSON snapshot is committed so the app starts instantly and works
even if Elexon is slow or down. Re-run to refresh.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, elexon_client  # noqa: E402
from app.data_store import save_snapshot  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("fetch_data")


def main() -> None:
    log.info("Fetching wind actuals %s -> %s", config.TARGET_START.date(), config.TARGET_END.date())
    actuals = elexon_client.fetch_actuals(config.TARGET_START, config.TARGET_END)
    log.info("  %d half-hour actuals", len(actuals))

    log.info("Fetching wind forecasts published %s -> %s",
             config.FORECAST_PUBLISH_START.date(), config.FORECAST_PUBLISH_END.date())
    forecasts = elexon_client.fetch_forecasts(config.FORECAST_PUBLISH_START, config.FORECAST_PUBLISH_END)
    log.info("  %d forecast rows across %d runs", len(forecasts), len({f.publish_time for f in forecasts}))

    if not actuals or not forecasts:
        log.error("Empty result - check the Elexon API parameters in app/config.py")
        sys.exit(1)
    save_snapshot(config.DATA_DIR, actuals, forecasts)
    log.info("Saved snapshot to %s", config.DATA_DIR)


if __name__ == "__main__":
    main()
