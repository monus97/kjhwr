"""Thin client for the two Elexon BMRS stream endpoints we use.

Only parsing/normalisation lives here - no analysis. Requests are split into small
date chunks so a single slow or failed call is cheap to retry.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from typing import Any

import requests

from . import config
from .models import Actual, Forecast

log = logging.getLogger(__name__)


def parse_ts(value: str) -> datetime:
    """Parse Elexon ISO timestamps ('2026-01-01T00:00:00Z') into aware UTC datetimes."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=config.UTC)
    return dt.astimezone(config.UTC)


def _rows(payload: Any) -> list[dict]:
    # Stream endpoints return a bare JSON array; other endpoints wrap it in {"data": [...]}.
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    raise ValueError(f"Unexpected Elexon payload shape: {type(payload).__name__}")


def _get(session: requests.Session, path: str, params: dict, retries: int = 3) -> list[dict]:
    url = config.ELEXON_BASE_URL + path
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, params=params, timeout=config.HTTP_TIMEOUT_S)
            resp.raise_for_status()
            return _rows(resp.json())
        except (requests.RequestException, ValueError) as exc:
            if attempt == retries:
                raise
            log.warning("Elexon call failed (%s), retry %d/%d", exc, attempt, retries)
            time.sleep(1.5 * attempt)
    return []  # unreachable


def _chunks(start: datetime, end: datetime, days: int) -> Iterator[tuple[datetime, datetime]]:
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        yield cur, nxt
        cur = nxt


def parse_actuals(rows: Iterable[dict]) -> list[Actual]:
    """Keep WIND rows only; if a slot was revised, keep the latest publication."""
    best: dict[datetime, tuple[datetime | None, float]] = {}
    for r in rows:
        if str(r.get("fuelType", "")).upper() != config.WIND_FUEL_TYPE:
            continue
        if r.get("startTime") is None or r.get("generation") is None:
            continue
        start = parse_ts(r["startTime"])
        pub = parse_ts(r["publishTime"]) if r.get("publishTime") else None
        prev = best.get(start)
        if prev is None or (pub is not None and (prev[0] is None or pub >= prev[0])):
            best[start] = (pub, float(r["generation"]))
    return [Actual(t, v[1]) for t, v in sorted(best.items())]


def parse_forecasts(rows: Iterable[dict]) -> list[Forecast]:
    out = {}
    for r in rows:
        if r.get("startTime") is None or r.get("publishTime") is None or r.get("generation") is None:
            continue
        f = Forecast(parse_ts(r["startTime"]), parse_ts(r["publishTime"]), float(r["generation"]))
        out[(f.start_time, f.publish_time)] = f
    return sorted(out.values(), key=lambda f: (f.start_time, f.publish_time))


def fetch_actuals(start: datetime, end: datetime, session: requests.Session | None = None) -> list[Actual]:
    """Wind actuals with start_time in [start, end)."""
    session = session or requests.Session()
    rows: list[dict] = []
    # settlementDate is a calendar date; pad a day each side then trim on startTime.
    for a, b in _chunks(start - timedelta(days=1), end + timedelta(days=1), config.FETCH_CHUNK_DAYS):
        rows += _get(session, config.ACTUALS_PATH, {
            "settlementDateFrom": a.date().isoformat(),
            "settlementDateTo": (b - timedelta(days=1)).date().isoformat(),
            "fuelType": config.WIND_FUEL_TYPE,
        })
    return [x for x in parse_actuals(rows) if start <= x.start_time < end]


def fetch_forecasts(
    publish_from: datetime, publish_to: datetime, session: requests.Session | None = None
) -> list[Forecast]:
    """All wind forecasts published in [publish_from, publish_to)."""
    session = session or requests.Session()
    rows: list[dict] = []
    for a, b in _chunks(publish_from, publish_to, config.FETCH_CHUNK_DAYS):
        rows += _get(session, config.FORECAST_PATH, {
            "publishDateTimeFrom": a.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "publishDateTimeTo": b.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return [f for f in parse_forecasts(rows) if publish_from <= f.publish_time < publish_to]