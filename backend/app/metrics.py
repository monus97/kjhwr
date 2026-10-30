"""Forecast error statistics, written without numpy to keep the deploy small.

Sign convention everywhere: error = forecast - actual.
  * positive error  -> over-forecast  -> less wind than planned -> buy more at short notice
  * negative error  -> under-forecast -> more wind than planned -> surplus to sell back
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Sequence

from .models import Pair


def quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolated quantile (same as numpy's default) of pre-sorted values."""
    if not sorted_values:
        raise ValueError("quantile of empty sequence")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    pos = (len(sorted_values) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def complete(pairs: Iterable[Pair]) -> list[Pair]:
    """Only pairs that have both an actual and a forecast."""
    return [p for p in pairs if p.error_mw is not None]


def summarize(pairs: Iterable[Pair]) -> dict:
    """Headline accuracy metrics for a set of (actual, forecast) pairs."""
    usable = complete(pairs)
    n = len(usable)
    if n == 0:
        return {"n": 0}
    errors = [p.error_mw for p in usable]
    abs_errors = sorted(abs(e) for e in errors)
    errors_sorted = sorted(errors)
    actual_mean = sum(p.actual_mw for p in usable) / n
    mae = sum(abs_errors) / n
    return {
        "n": n,
        "mae_mw": mae,
        "rmse_mw": math.sqrt(sum(e * e for e in errors) / n),
        "bias_mw": sum(errors) / n,
        "median_abs_error_mw": quantile(abs_errors, 0.5),
        "p90_abs_error_mw": quantile(abs_errors, 0.9),
        "max_abs_error_mw": abs_errors[-1],
        # Error percentiles keep the sign: P90 = "90% of the time the forecast
        # over-shot by less than this" -> the buffer to hold against a wind shortfall.
        "error_p10_mw": quantile(errors_sorted, 0.1),
        "error_p50_mw": quantile(errors_sorted, 0.5),
        "error_p90_mw": quantile(errors_sorted, 0.9),
        "mean_actual_mw": actual_mean,
        # MAE relative to mean output. Avoids MAPE, which explodes on calm periods.
        "nmae_pct": (mae / actual_mean * 100.0) if actual_mean > 0 else None,
        "over_forecast_share": sum(1 for e in errors if e > 0) / n,
    }


def by_hour_of_day(pairs: Iterable[Pair]) -> list[dict]:
    """MAE and bias for each UTC hour of day (UK local = UTC in January)."""
    buckets: dict[int, list[float]] = defaultdict(list)
    for p in complete(pairs):
        buckets[p.start_time.hour].append(p.error_mw)
    out = []
    for hour in range(24):
        errs = buckets.get(hour, [])
        out.append({
            "hour": hour,
            "n": len(errs),
            "mae_mw": (sum(abs(e) for e in errs) / len(errs)) if errs else None,
            "bias_mw": (sum(errs) / len(errs)) if errs else None,
        })
    return out


def error_histogram(pairs: Iterable[Pair], bin_mw: float = 500.0) -> list[dict]:
    errors = [p.error_mw for p in complete(pairs)]
    if not errors:
        return []
    lo = math.floor(min(errors) / bin_mw) * bin_mw
    hi = math.floor(max(errors) / bin_mw) * bin_mw
    counts: dict[float, int] = defaultdict(int)
    for e in errors:
        counts[math.floor(e / bin_mw) * bin_mw] += 1
    out, b = [], lo
    while b <= hi:
        out.append({"from_mw": b, "to_mw": b + bin_mw, "count": counts.get(b, 0)})
        b += bin_mw
    return out
