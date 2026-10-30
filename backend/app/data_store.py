"""Loads the January 2026 dataset once and keeps it in memory.

Load order:
  1. committed snapshot in backend/data (created by scripts/fetch_data.py)
  2. writable cache from an earlier live fetch (CACHE_DIR)
  3. live fetch from Elexon, then written to CACHE_DIR

The data is historical and immutable, so caching is safe and keeps the app fast
and independent of Elexon availability.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import config, elexon_client
from .elexon_client import parse_ts
from .forecasting import ForecastIndex, actuals_to_dict
from .models import Actual, Forecast

log = logging.getLogger(__name__)

ACTUALS_FILE = "actuals.json"
FORECASTS_FILE = "forecasts.json"


@dataclass
class Dataset:
    actuals: dict[datetime, float]
    index: ForecastIndex
    source: str
    n_forecasts: int
    meta: dict = field(default_factory=dict)


def save_snapshot(directory: Path, actuals: list[Actual], forecasts: list[Forecast]) -> None:
    """Compact JSON: arrays instead of objects keeps the files small."""
    directory.mkdir(parents=True, exist_ok=True)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    (directory / ACTUALS_FILE).write_text(json.dumps(
        [[a.start_time.strftime(fmt), a.generation_mw] for a in actuals], separators=(",", ":")))
    (directory / FORECASTS_FILE).write_text(json.dumps(
        [[f.start_time.strftime(fmt), f.publish_time.strftime(fmt), f.generation_mw] for f in forecasts],
        separators=(",", ":")))


def load_snapshot(directory: Path) -> tuple[list[Actual], list[Forecast]] | None:
    a_path, f_path = directory / ACTUALS_FILE, directory / FORECASTS_FILE
    if not (a_path.exists() and f_path.exists()):
        return None
    actuals = [Actual(parse_ts(t), float(v)) for t, v in json.loads(a_path.read_text())]
    forecasts = [Forecast(parse_ts(t), parse_ts(p), float(v)) for t, p, v in json.loads(f_path.read_text())]
    return actuals, forecasts


def build_dataset(actuals: list[Actual], forecasts: list[Forecast], source: str) -> Dataset:
    publish_times = [f.publish_time for f in forecasts]
    return Dataset(
        actuals=actuals_to_dict(actuals),
        index=ForecastIndex(forecasts),
        source=source,
        n_forecasts=len(forecasts),
        meta={
            "first_actual": min((a.start_time for a in actuals), default=None),
            "last_actual": max((a.start_time for a in actuals), default=None),
            "first_publish": min(publish_times, default=None),
            "last_publish": max(publish_times, default=None),
            "n_forecast_runs": len(set(publish_times)),
        },
    )


_lock = threading.Lock()
_dataset: Dataset | None = None


def get_dataset() -> Dataset:
    global _dataset
    if _dataset is not None:
        return _dataset
    with _lock:
        if _dataset is None:
            _dataset = _load()
    return _dataset


def set_dataset(ds: Dataset | None) -> None:
    """Test hook: inject a dataset (or reset with None)."""
    global _dataset
    _dataset = ds


def _load() -> Dataset:
    for directory, label in ((config.DATA_DIR, "snapshot"), (config.CACHE_DIR, "cache")):
        snap = load_snapshot(directory)
        if snap:
            log.info("Loaded %s from %s", label, directory)
            return build_dataset(*snap, source=label)

    log.info("No local data; fetching from Elexon")
    actuals = elexon_client.fetch_actuals(config.TARGET_START, config.TARGET_END)
    forecasts = elexon_client.fetch_forecasts(config.FORECAST_PUBLISH_START, config.FORECAST_PUBLISH_END)
    try:
        save_snapshot(config.CACHE_DIR, actuals, forecasts)
    except OSError as exc:  # read-only FS is fine, we just lose the cache
        log.warning("Could not write cache: %s", exc)
    return build_dataset(actuals, forecasts, source="elexon-live")
