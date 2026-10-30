"""End-to-end through the ASGI app, with an injected in-memory dataset."""
from datetime import timedelta

import pytest
from conftest import ts
from starlette.testclient import TestClient

from app import data_store
from app.data_store import build_dataset
from app.main import app
from app.models import Actual, Forecast


@pytest.fixture(autouse=True)
def dataset():
    # 2 days of actuals, forecast runs every 12h out to 48h ahead.
    half_hour, actuals, forecasts = timedelta(minutes=30), [], []
    t = ts(10, 0)
    while t < ts(12, 0):
        actuals.append(Actual(t, 4000.0 + 10 * t.hour))
        t += half_hour
    pub = ts(8, 0)
    while pub < ts(12, 0):
        tgt = pub
        while tgt <= pub + timedelta(hours=48):
            forecasts.append(Forecast(tgt, pub, 4000.0 + 10 * tgt.hour + 100))
            tgt += half_hour
        pub += timedelta(hours=12)
    data_store.set_dataset(build_dataset(actuals, forecasts, source="test"))
    yield
    data_store.set_dataset(None)


client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta_reports_counts():
    m = client.get("/api/meta").json()
    assert m["source"] == "test" and m["n_actuals"] == 96 and m["n_forecasts"] > 0


def test_accuracy_default_horizon_is_24h():
    r = client.get("/api/accuracy", params={"start": "2026-01-10T00:00Z", "end": "2026-01-12T00:00Z"}).json()
    assert r["horizon_h"] == 24.0
    assert r["summary"]["n"] == 96
    assert r["summary"]["bias_mw"] == pytest.approx(100.0)   # forecast = actual + 100
    assert all(p["lead_h"] >= 24 for p in r["series"] if p["lead_h"] is not None)
    assert len(r["by_hour"]) == 24 and r["histogram"]


def test_accuracy_rejects_bad_horizon():
    assert client.get("/api/accuracy", params={"horizon": "99"}).status_code == 400
    assert client.get("/api/accuracy", params={"horizon": "abc"}).status_code == 400


def test_accuracy_rejects_empty_range():
    r = client.get("/api/accuracy", params={"start": "2026-01-12T00:00Z", "end": "2026-01-10T00:00Z"})
    assert r.status_code == 400


def test_decision_view_single_run():
    r = client.get("/api/decision", params={"delivery_day": "2026-01-11", "decision_time": "09:00"}).json()
    assert r["decision_time"] == "2026-01-10T09:00:00Z"
    assert r["forecast_run_used"] == "2026-01-10T00:00:00Z"   # latest run at/before 09:00 on D-1
    assert len(r["series"]) == 48
    assert r["hindsight"]["n"] == 48
    assert "band_low" in r["series"][0]


def test_decision_view_out_of_scope_day():
    assert client.get("/api/decision", params={"delivery_day": "2026-03-01"}).status_code == 400


def test_horizon_curve_shape():
    r = client.get("/api/horizon-curve").json()
    hs = [p["horizon_h"] for p in r["points"]]
    assert hs[0] == 0 and hs[-1] == 48