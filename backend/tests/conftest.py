import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import Actual, Forecast  # noqa: E402

UTC = timezone.utc


def ts(day: int, hour: int, minute: int = 0, month: int = 1) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


@pytest.fixture
def tiny_world():
    """Two target slots on 15 Jan, several forecast runs for each.

    Target 12:00 on 15 Jan has forecasts published:
      13 Jan 06:00 -> 5000   (lead 54h)
      14 Jan 06:00 -> 5500   (lead 30h)
      14 Jan 12:00 -> 5800   (lead 24h exactly)
      15 Jan 06:00 -> 6100   (lead 6h)
    Actual at 15 Jan 12:00 = 6000.
    """
    actuals = [Actual(ts(15, 12), 6000.0), Actual(ts(15, 12, 30), 6200.0)]
    forecasts = [
        Forecast(ts(15, 12), ts(13, 6), 5000.0),
        Forecast(ts(15, 12), ts(14, 6), 5500.0),
        Forecast(ts(15, 12), ts(14, 12), 5800.0),
        Forecast(ts(15, 12), ts(15, 6), 6100.0),
        Forecast(ts(15, 12, 30), ts(14, 6), 5600.0),
        Forecast(ts(15, 12, 30), ts(15, 6), 6300.0),
    ]
    return actuals, forecasts
