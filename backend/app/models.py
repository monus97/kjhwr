"""Plain data records used across the backend (no framework dependencies)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Actual:
    start_time: datetime  # UTC, start of the 30-min settlement slot
    generation_mw: float


@dataclass(frozen=True, slots=True)
class Forecast:
    start_time: datetime    # UTC target time the forecast is for
    publish_time: datetime  # UTC time the forecast was issued
    generation_mw: float


@dataclass(frozen=True, slots=True)
class Pair:
    """One target time with the actual value and the forecast chosen for it."""
    start_time: datetime
    actual_mw: float | None
    forecast_mw: float | None
    publish_time: datetime | None

    @property
    def lead_hours(self) -> float | None:
        if self.publish_time is None:
            return None
        return (self.start_time - self.publish_time).total_seconds() / 3600.0

    @property
    def error_mw(self) -> float | None:
        """forecast - actual. Positive = over-forecast (less wind than expected)."""
        if self.actual_mw is None or self.forecast_mw is None:
            return None
        return self.forecast_mw - self.actual_mw
