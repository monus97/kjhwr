"""Core domain logic: which forecast was available when a decision was made.

The WINDFOR dataset contains many forecasts for the same target time, each issued
at a different ``publish_time``. Comparing an actual with "the forecast" is only
meaningful once we fix *when* we look. Two questions drive the product:

1. Horizon view - "how good is the forecast issued at least H hours ahead?"
   For target time T we use the latest forecast with publish_time <= T - H.

2. Decision view - "what did the forecast look like at my decision moment?"
   For every target T in the delivery day we use the latest forecast with
   publish_time <= decision_time (a single cut-off for the whole day).

Both reduce to "latest forecast published at or before a cut-off", which this
module answers with a binary search per target time. Using a later forecast than
that would leak information that was not available at decision time.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timedelta

from .models import Actual, Forecast, Pair


class ForecastIndex:
    """Forecasts grouped by target time and sorted by publish time."""

    def __init__(self, forecasts: Iterable[Forecast]):
        grouped: dict[datetime, dict[datetime, float]] = defaultdict(dict)
        for f in forecasts:
            # If the same (target, publish) pair appears twice, the last one wins.
            grouped[f.start_time][f.publish_time] = f.generation_mw
        self._publish_times: dict[datetime, list[datetime]] = {}
        self._values: dict[datetime, list[float]] = {}
        for target, by_publish in grouped.items():
            pubs = sorted(by_publish)
            self._publish_times[target] = pubs
            self._values[target] = [by_publish[p] for p in pubs]

    def __len__(self) -> int:
        return sum(len(v) for v in self._values.values())

    @property
    def target_times(self) -> list[datetime]:
        return sorted(self._publish_times)

    def latest_before(self, target: datetime, cutoff: datetime) -> tuple[datetime, float] | None:
        """Latest forecast for ``target`` with publish_time <= ``cutoff``."""
        pubs = self._publish_times.get(target)
        if not pubs:
            return None
        i = bisect_right(pubs, cutoff) - 1
        if i < 0:
            return None
        return pubs[i], self._values[target][i]

    def all_for(self, target: datetime) -> list[tuple[datetime, float]]:
        pubs = self._publish_times.get(target, [])
        return list(zip(pubs, self._values.get(target, []), strict=True))


def _pair_up(
    actuals: dict[datetime, float],
    index: ForecastIndex,
    targets: Sequence[datetime],
    cutoff_for: Callable[[datetime], datetime],
) -> list[Pair]:
    pairs = []
    for t in targets:
        chosen = index.latest_before(t, cutoff_for(t))
        pairs.append(Pair(
            start_time=t,
            actual_mw=actuals.get(t),
            forecast_mw=chosen[1] if chosen else None,
            publish_time=chosen[0] if chosen else None,
        ))
    return pairs


def targets_in_range(
    actuals: dict[datetime, float], index: ForecastIndex, start: datetime, end: datetime
) -> list[datetime]:
    """Target times in [start, end) that have an actual or any forecast."""
    keys = set(actuals) | set(index.target_times)
    return sorted(t for t in keys if start <= t < end)


def pairs_for_horizon(
    actuals: dict[datetime, float],
    index: ForecastIndex,
    start: datetime,
    end: datetime,
    horizon_hours: float,
) -> list[Pair]:
    """For each target T in [start, end): latest forecast published <= T - horizon."""
    if horizon_hours < 0:
        raise ValueError("horizon_hours must be >= 0")
    h = timedelta(hours=horizon_hours)
    return _pair_up(actuals, index, targets_in_range(actuals, index, start, end), lambda t: t - h)


def pairs_for_decision(
    actuals: dict[datetime, float],
    index: ForecastIndex,
    start: datetime,
    end: datetime,
    decision_time: datetime,
) -> list[Pair]:
    """For each target T in [start, end): latest forecast published <= decision_time."""
    return _pair_up(
        actuals, index, targets_in_range(actuals, index, start, end), lambda _t: decision_time
    )


def actuals_to_dict(actuals: Iterable[Actual]) -> dict[datetime, float]:
    return {a.start_time: a.generation_mw for a in actuals}
