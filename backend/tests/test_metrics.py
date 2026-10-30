import math

import pytest

from app.metrics import by_hour_of_day, error_histogram, quantile, summarize
from app.models import Pair

from conftest import ts


def _pair(hour, actual, forecast, minute=0):
    return Pair(ts(10, hour, minute), actual, forecast, ts(9, 0))


def test_quantile_matches_numpy_linear_convention():
    vals = [1.0, 2.0, 3.0, 4.0]
    assert quantile(vals, 0.5) == 2.5
    assert quantile(vals, 0.0) == 1.0
    assert quantile(vals, 1.0) == 4.0
    assert quantile(vals, 0.25) == 1.75


def test_quantile_rejects_empty_and_out_of_range():
    with pytest.raises(ValueError):
        quantile([], 0.5)
    with pytest.raises(ValueError):
        quantile([1.0], 1.5)


def test_summary_basic_numbers():
    pairs = [_pair(0, 100, 110), _pair(1, 100, 90), _pair(2, 100, 130)]
    s = summarize(pairs)
    assert s["n"] == 3
    assert s["bias_mw"] == pytest.approx(10.0)       # (+10 -10 +30)/3
    assert s["mae_mw"] == pytest.approx(50 / 3)
    assert s["rmse_mw"] == pytest.approx(math.sqrt((100 + 100 + 900) / 3))
    assert s["mean_actual_mw"] == 100.0
    assert s["nmae_pct"] == pytest.approx(50 / 3)
    assert s["over_forecast_share"] == pytest.approx(2 / 3)
    assert s["max_abs_error_mw"] == 30.0


def test_summary_ignores_incomplete_pairs():
    pairs = [_pair(0, 100, 110), Pair(ts(10, 1), None, 50.0, None), Pair(ts(10, 2), 80.0, None, None)]
    assert summarize(pairs)["n"] == 1


def test_summary_of_nothing():
    assert summarize([]) == {"n": 0}


def test_nmae_none_when_no_wind():
    assert summarize([_pair(0, 0.0, 10.0)])["nmae_pct"] is None


def test_by_hour_groups_by_utc_hour():
    rows = by_hour_of_day([_pair(3, 100, 120), _pair(3, 100, 80, minute=30), _pair(5, 100, 150)])
    assert rows[3] == {"hour": 3, "n": 2, "mae_mw": 20.0, "bias_mw": 0.0}
    assert rows[5]["bias_mw"] == 50.0
    assert rows[0]["n"] == 0 and rows[0]["mae_mw"] is None


def test_histogram_bins_cover_min_to_max():
    bins = error_histogram([_pair(0, 0, -700), _pair(1, 0, 10), _pair(2, 0, 1200)], bin_mw=500)
    assert bins[0]["from_mw"] == -1000 and bins[-1]["to_mw"] == 1500
    assert sum(b["count"] for b in bins) == 3
    assert bins[0]["count"] == 1  # -700 lands in [-1000, -500)
