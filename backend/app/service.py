"""Use-case layer: turns the dataset into JSON-ready view models.

Framework-free on purpose - the FastAPI routes in main.py are one-liners over these
functions, and the tests call them directly.
"""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta

from . import config
from .data_store import Dataset
from .forecasting import pairs_for_decision, pairs_for_horizon
from .metrics import by_hour_of_day, complete, error_histogram, quantile, summarize
from .models import Pair

ISO = "%Y-%m-%dT%H:%M:%SZ"


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(config.UTC).strftime(ISO) if dt else None


def _series(pairs: list[Pair]) -> list[dict]:
    return [{
        "t": iso(p.start_time),
        "actual": p.actual_mw,
        "forecast": p.forecast_mw,
        "publish_time": iso(p.publish_time),
        "lead_h": round(p.lead_hours, 2) if p.lead_hours is not None else None,
        "error": p.error_mw,
    } for p in pairs]


def _clamp_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start = max(start, config.TARGET_START)
    end = min(end, config.TARGET_END)
    if end <= start:
        raise ValueError("Empty time range: pick dates between 1 Jan and 1 Feb 2026")
    return start, end


# --- caches (dataset is immutable for the life of the process) ---------------

_quantile_cache: dict[int, tuple[Dataset, dict]] = {}


def error_quantiles(ds: Dataset) -> dict[int, tuple[float, float, float]]:
    """P10/P50/P90 of error for each whole-hour horizon over the full January window.

    Used to draw an empirical uncertainty band on the decision view. It is a
    backtest over the same month, so it describes past error rather than being a
    predictive model - the UI labels it accordingly. Computed once per dataset.
    """
    cached = _quantile_cache.get(id(ds))
    if cached and cached[0] is ds:
        return cached[1]
    out = {}
    for h in range(0, int(config.MAX_HORIZON_H) + 1):
        errs = sorted(p.error_mw for p in complete(pairs_for_horizon(
            ds.actuals, ds.index, config.TARGET_START, config.TARGET_END, h)))
        if errs:
            out[h] = (quantile(errs, 0.1), quantile(errs, 0.5), quantile(errs, 0.9))
    _quantile_cache[id(ds)] = (ds, out)
    return out


# --- views ------------------------------------------------------------------

def meta(ds: Dataset) -> dict:
    m = ds.meta
    return {
        "source": ds.source,
        "target_start": iso(config.TARGET_START),
        "target_end": iso(config.TARGET_END),
        "first_actual": iso(m.get("first_actual")),
        "last_actual": iso(m.get("last_actual")),
        "first_publish": iso(m.get("first_publish")),
        "last_publish": iso(m.get("last_publish")),
        "n_actuals": len(ds.actuals),
        "n_forecasts": ds.n_forecasts,
        "n_forecast_runs": m.get("n_forecast_runs"),
        "default_horizon_h": config.DEFAULT_HORIZON_H,
        "max_horizon_h": config.MAX_HORIZON_H,
        "default_decision_time": config.DEFAULT_DECISION_TIME,
        # Decisions in Jan 2026 -> delivery days 2 Jan .. 1 Feb.
        "delivery_days": {"first": "2026-01-02", "last": "2026-02-01"},
    }


def decision_view(ds: Dataset, delivery_day: date, decision_clock: time) -> dict:
    """What the buyer saw at the decision moment on D-1, and how it turned out."""
    day_start = datetime.combine(delivery_day, time(0), tzinfo=config.UTC)
    day_end = day_start + timedelta(days=1)
    decision_at = datetime.combine(delivery_day - timedelta(days=1), decision_clock, tzinfo=config.UTC)
    if not (config.TARGET_START <= day_start and day_end <= config.TARGET_END):
        raise ValueError("Delivery day must be between 1 Jan and 1 Feb 2026")

    pairs = pairs_for_decision(ds.actuals, ds.index, day_start, day_end, decision_at)
    quants = error_quantiles(ds)
    series = _series(pairs)
    for row, p in zip(series, pairs):
        row["band_low"] = row["band_high"] = None
        if p.forecast_mw is None or p.lead_hours is None:
            continue
        q = quants.get(min(int(math.floor(p.lead_hours)), int(config.MAX_HORIZON_H)))
        if q:
            # error = forecast - actual  ->  actual = forecast - error
            row["band_low"] = max(0.0, p.forecast_mw - q[2])
            row["band_high"] = max(0.0, p.forecast_mw - q[0])

    forecasts = [p.forecast_mw for p in pairs if p.forecast_mw is not None]
    used_runs = sorted({p.publish_time for p in pairs if p.publish_time})
    return {
        "delivery_day": delivery_day.isoformat(),
        "decision_time": iso(decision_at),
        "forecast_run_used": iso(used_runs[-1]) if used_runs else None,
        "forecast_runs_used": [iso(t) for t in used_runs],
        "forecast_summary": {
            "n_points": len(forecasts),
            "mean_mw": sum(forecasts) / len(forecasts) if forecasts else None,
            "min_mw": min(forecasts, default=None),
            "max_mw": max(forecasts, default=None),
        },
        "hindsight": summarize(pairs),
        "series": series,
    }


def accuracy_view(ds: Dataset, start: datetime, end: datetime, horizon_h: float) -> dict:
    start, end = _clamp_range(start, end)
    if not 0 <= horizon_h <= config.MAX_HORIZON_H:
        raise ValueError(f"horizon must be between 0 and {config.MAX_HORIZON_H:g} hours")
    pairs = pairs_for_horizon(ds.actuals, ds.index, start, end, horizon_h)
    return {
        "start": iso(start),
        "end": iso(end),
        "horizon_h": horizon_h,
        "summary": summarize(pairs),
        "by_hour": by_hour_of_day(pairs),
        "histogram": error_histogram(pairs),
        "series": _series(pairs),
    }


def horizon_curve(ds: Dataset, start: datetime, end: datetime, step_h: int = 2) -> dict:
    """How accuracy degrades as the forecast is issued further ahead."""
    start, end = _clamp_range(start, end)
    rows = []
    for h in range(0, int(config.MAX_HORIZON_H) + 1, step_h):
        s = summarize(pairs_for_horizon(ds.actuals, ds.index, start, end, h))
        rows.append({"horizon_h": h, **s})
    return {"start": iso(start), "end": iso(end), "points": rows}
