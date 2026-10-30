"""HTTP layer (Starlette ASGI app).

Starlette is the ASGI toolkit FastAPI is built on. Using it directly keeps the
dependency footprint tiny (fast cold starts on serverless) while the routes stay
one-liners over the service layer. Swap in FastAPI later if auto-generated docs
become worth the extra weight; the service functions would not change.

Endpoints (all GET, JSON):
  /api/health
  /api/meta
  /api/decision?delivery_day=2026-01-15&decision_time=09:00
  /api/accuracy?start=2026-01-01T00:00Z&end=2026-02-01T00:00Z&horizon=24
  /api/horizon-curve?start=...&end=...
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, time

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import config, service
from .data_store import get_dataset

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


# --- query parsing helpers ---------------------------------------------------

def _dt(value: str | None, default: datetime) -> datetime:
    if not value:
        return default
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (dt if dt.tzinfo else dt.replace(tzinfo=config.UTC)).astimezone(config.UTC)


def _float(value: str | None, default: float) -> float:
    return float(value) if value not in (None, "") else default


def _bad_request(exc: Exception) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=400)


# --- routes -------------------------------------------------------------------

async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def meta(_: Request) -> JSONResponse:
    return JSONResponse(service.meta(get_dataset()))


async def decision(request: Request) -> JSONResponse:
    q = request.query_params
    try:
        day = date.fromisoformat(q.get("delivery_day", "2026-01-15"))
        clock = time.fromisoformat(q.get("decision_time", config.DEFAULT_DECISION_TIME))
        return JSONResponse(service.decision_view(get_dataset(), day, clock))
    except ValueError as exc:
        return _bad_request(exc)


async def accuracy(request: Request) -> JSONResponse:
    q = request.query_params
    try:
        return JSONResponse(service.accuracy_view(
            get_dataset(),
            _dt(q.get("start"), config.TARGET_START),
            _dt(q.get("end"), config.TARGET_END),
            _float(q.get("horizon"), config.DEFAULT_HORIZON_H),
        ))
    except ValueError as exc:
        return _bad_request(exc)


async def horizon_curve(request: Request) -> JSONResponse:
    q = request.query_params
    try:
        return JSONResponse(service.horizon_curve(
            get_dataset(),
            _dt(q.get("start"), config.TARGET_START),
            _dt(q.get("end"), config.TARGET_END),
        ))
    except ValueError as exc:
        return _bad_request(exc)


routes = [
    Route("/api/health", health),
    Route("/api/meta", meta),
    Route("/api/decision", decision),
    Route("/api/accuracy", accuracy),
    Route("/api/horizon-curve", horizon_curve),
]
if config.FRONTEND_DIST and os.path.isdir(config.FRONTEND_DIST):
    # Single-container mode: serve the built React app from the same origin.
    routes.append(Mount("/", app=StaticFiles(directory=config.FRONTEND_DIST, html=True), name="ui"))

app = Starlette(
    routes=routes,
    middleware=[Middleware(
        CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET"], allow_headers=["*"],
    )],
)
