from app.elexon_client import parse_actuals, parse_forecasts, parse_ts

from conftest import ts


def test_parse_ts_handles_z_suffix_and_offsets():
    assert parse_ts("2026-01-05T10:30:00Z") == ts(5, 10, 30)
    assert parse_ts("2026-01-05T11:30:00+01:00") == ts(5, 10, 30)
    assert parse_ts("2026-01-05T10:30:00") == ts(5, 10, 30)  # naive -> assume UTC


def test_parse_actuals_keeps_wind_only_and_latest_publication():
    rows = [
        {"fuelType": "CCGT", "startTime": "2026-01-05T10:00:00Z", "generation": 999, "publishTime": "2026-01-05T10:35:00Z"},
        {"fuelType": "WIND", "startTime": "2026-01-05T10:00:00Z", "generation": 5000, "publishTime": "2026-01-05T10:35:00Z"},
        {"fuelType": "WIND", "startTime": "2026-01-05T10:00:00Z", "generation": 5100, "publishTime": "2026-01-05T11:35:00Z"},
        {"fuelType": "WIND", "startTime": "2026-01-05T10:30:00Z", "generation": None},
    ]
    out = parse_actuals(rows)
    assert len(out) == 1
    assert out[0].start_time == ts(5, 10) and out[0].generation_mw == 5100.0


def test_parse_forecasts_dedupes_and_sorts():
    rows = [
        {"startTime": "2026-01-05T10:00:00Z", "publishTime": "2026-01-04T06:00:00Z", "generation": 10},
        {"startTime": "2026-01-05T10:00:00Z", "publishTime": "2026-01-04T06:00:00Z", "generation": 11},
        {"startTime": "2026-01-05T09:30:00Z", "publishTime": "2026-01-04T06:00:00Z", "generation": 9},
        {"startTime": "2026-01-05T10:00:00Z", "publishTime": None, "generation": 1},
    ]
    out = parse_forecasts(rows)
    assert [(f.start_time, f.generation_mw) for f in out] == [(ts(5, 9, 30), 9.0), (ts(5, 10), 11.0)]
