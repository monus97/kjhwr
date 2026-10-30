"""The forecast-selection rule is the heart of the product; these tests pin it down."""
from datetime import timedelta

import pytest
from conftest import ts

from app.forecasting import ForecastIndex, actuals_to_dict, pairs_for_decision, pairs_for_horizon
from app.models import Forecast


def _world(tiny_world):
    actuals, forecasts = tiny_world
    return actuals_to_dict(actuals), ForecastIndex(forecasts)


def test_latest_before_picks_most_recent_run_at_or_before_cutoff(tiny_world):
    _, index = _world(tiny_world)
    assert index.latest_before(ts(15, 12), ts(14, 8)) == (ts(14, 6), 5500.0)


def test_cutoff_is_inclusive(tiny_world):
    _, index = _world(tiny_world)
    assert index.latest_before(ts(15, 12), ts(14, 12)) == (ts(14, 12), 5800.0)


def test_no_forecast_before_cutoff_returns_none(tiny_world):
    _, index = _world(tiny_world)
    assert index.latest_before(ts(15, 12), ts(12, 0)) is None


def test_unknown_target_returns_none(tiny_world):
    _, index = _world(tiny_world)
    assert index.latest_before(ts(20, 0), ts(19, 0)) is None


def test_horizon_24h_uses_forecast_published_exactly_24h_ahead(tiny_world):
    actuals, index = _world(tiny_world)
    pairs = pairs_for_horizon(actuals, index, ts(15, 0), ts(16, 0), 24)
    by_t = {p.start_time: p for p in pairs}
    p = by_t[ts(15, 12)]
    assert p.forecast_mw == 5800.0 and p.publish_time == ts(14, 12)
    assert p.lead_hours == 24.0
    assert p.error_mw == -200.0  # forecast - actual


def test_horizon_0_uses_latest_forecast_before_delivery(tiny_world):
    actuals, index = _world(tiny_world)
    p = {p.start_time: p for p in pairs_for_horizon(actuals, index, ts(15, 0), ts(16, 0), 0)}[ts(15, 12)]
    assert p.forecast_mw == 6100.0


def test_long_horizon_falls_back_to_older_run(tiny_world):
    actuals, index = _world(tiny_world)
    p = {p.start_time: p for p in pairs_for_horizon(actuals, index, ts(15, 0), ts(16, 0), 48)}[ts(15, 12)]
    assert p.forecast_mw == 5000.0  # only the 13 Jan run is old enough


def test_horizon_beyond_any_run_gives_missing_forecast(tiny_world):
    actuals, index = _world(tiny_world)
    p = {p.start_time: p for p in pairs_for_horizon(actuals, index, ts(15, 0), ts(16, 0), 60)}[ts(15, 12)]
    assert p.forecast_mw is None and p.error_mw is None and p.actual_mw == 6000.0


def test_never_uses_a_forecast_published_after_the_cutoff(tiny_world):
    """Leakage guard: the 15 Jan 06:00 run must be invisible to a 24h-ahead view."""
    actuals, index = _world(tiny_world)
    for p in pairs_for_horizon(actuals, index, ts(15, 0), ts(16, 0), 24):
        if p.publish_time is not None:
            assert p.publish_time <= p.start_time - timedelta(hours=24)


def test_decision_view_uses_single_cutoff_for_whole_day(tiny_world):
    actuals, index = _world(tiny_world)
    pairs = pairs_for_decision(actuals, index, ts(15, 0), ts(16, 0), ts(14, 9))
    by_t = {p.start_time: p for p in pairs}
    assert by_t[ts(15, 12)].publish_time == ts(14, 6)
    assert by_t[ts(15, 12, 30)].publish_time == ts(14, 6)
    # Different lead times within the same day are expected.
    assert by_t[ts(15, 12)].lead_hours == 30.0
    assert by_t[ts(15, 12, 30)].lead_hours == 30.5


def test_targets_with_forecast_but_no_actual_are_kept(tiny_world):
    actuals, index = _world(tiny_world)
    index = ForecastIndex(list(tiny_world[1]) + [Forecast(ts(15, 13), ts(14, 6), 1.0)])
    pairs = pairs_for_horizon(actuals, index, ts(15, 0), ts(16, 0), 24)
    p = {p.start_time: p for p in pairs}[ts(15, 13)]
    assert p.actual_mw is None and p.forecast_mw == 1.0 and p.error_mw is None


def test_range_end_is_exclusive(tiny_world):
    actuals, index = _world(tiny_world)
    pairs = pairs_for_horizon(actuals, index, ts(15, 0), ts(15, 12, 30), 24)
    assert [p.start_time for p in pairs] == [ts(15, 12)]


def test_duplicate_rows_last_one_wins():
    index = ForecastIndex([Forecast(ts(1, 0), ts(1, 0), 10.0), Forecast(ts(1, 0), ts(1, 0), 20.0)])
    assert index.latest_before(ts(1, 0), ts(1, 0)) == (ts(1, 0), 20.0)
    assert len(index) == 1


def test_negative_horizon_rejected(tiny_world):
    actuals, index = _world(tiny_world)
    with pytest.raises(ValueError):
        pairs_for_horizon(actuals, index, ts(15, 0), ts(16, 0), -1)