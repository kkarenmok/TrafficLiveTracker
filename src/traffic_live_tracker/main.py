from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from functools import lru_cache
from threading import Lock
from time import monotonic

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from traffic_live_tracker.config import BusStop, load_settings
from traffic_live_tracker.database import DuplicateStopError, StopRepository
from traffic_live_tracker.models import (
    DashboardResponse,
    DashboardStop,
    StopCreate,
    StopResponse,
    StopSearchResult,
    utc_now,
)
from traffic_live_tracker.tfl_client import TflClient, TflClientError

app = FastAPI(
    title="TrafficLiveTracker",
    description="API for the TrafficLiveTracker London bus dashboard.",
    version="0.1.0",
)
_allowed_origins = set(load_settings().cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

_mutation_requests: dict[str, deque[float]] = defaultdict(deque)
_mutation_lock = Lock()


@app.middleware("http")
async def limit_public_mutations(request: Request, call_next):
    if request.method in {"POST", "DELETE"} and request.url.path.startswith("/stops"):
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        client_key = forwarded or (request.client.host if request.client else "unknown")
        now = monotonic()
        with _mutation_lock:
            attempts = _mutation_requests[client_key]
            while attempts and attempts[0] <= now - 600:
                attempts.popleft()
            if len(attempts) >= 30:
                headers = {}
                origin = request.headers.get("origin")
                if origin in _allowed_origins:
                    headers["Access-Control-Allow-Origin"] = origin
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many stop changes. Try again later."},
                    headers=headers,
                )
            attempts.append(now)
    return await call_next(request)


def get_settings():
    return load_settings()


@lru_cache(maxsize=1)
def get_stop_repository() -> StopRepository:
    repository = StopRepository(get_settings().database_url)
    repository.initialize()
    return repository


def get_stops() -> list[BusStop]:
    return get_stop_repository().list_stops()


def get_tfl_client() -> TflClient:
    settings = get_settings()
    return TflClient(
        app_key=settings.tfl_app_key,
        timeout_seconds=settings.tfl_timeout_seconds,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stops", response_model=list[StopResponse])
async def stops() -> list[StopResponse]:
    return [_stop_response(stop) for stop in get_stops()]


@app.get("/stops/search", response_model=list[StopSearchResult])
async def search_stops(
    q: str = Query(min_length=2, max_length=80), modes: str | None = Query(default="bus")
) -> list[StopSearchResult]:
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Search query is too short")
    try:
        return await get_tfl_client().search_stop_points(query, limit=8, modes=modes)
    except TflClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/stops", response_model=StopResponse, status_code=status.HTTP_201_CREATED)
async def add_stop(stop_input: StopCreate) -> StopResponse:
    client = get_tfl_client()
    try:
        stop = await client.bus_stop_for_id(stop_input.id)
    except TflClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    try:
        get_stop_repository().add_stop(stop)
    except DuplicateStopError as exc:
        raise HTTPException(status_code=409, detail=f"Stop already added: {stop.id}") from exc
    return _stop_response(stop)


@app.delete("/stops/{stop_id}", response_model=StopResponse)
async def remove_stop(stop_id: str) -> StopResponse:
    stop = get_stop_repository().remove_stop(stop_id)
    if stop is None:
        raise HTTPException(status_code=404, detail=f"Unknown stop: {stop_id}")
    return _stop_response(stop)


@app.get("/arrivals/{stop_id}")
async def arrivals(stop_id: str):
    stop = _find_stop(stop_id, get_stops())
    client = get_tfl_client()
    try:
        return await client.arrivals_for_stop(stop)
    except TflClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/dashboard", response_model=DashboardResponse)
async def dashboard() -> DashboardResponse:
    settings = get_settings()
    configured_stops = get_stops()
    client = get_tfl_client()

    try:
        arrivals_by_stop = await asyncio.gather(
            *(client.arrivals_for_stop(stop) for stop in configured_stops)
        )
    except TflClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return DashboardResponse(
        refresh_seconds=settings.refresh_seconds,
        generated_at=utc_now(),
        stops=[
            DashboardStop(stop=_stop_response(stop), arrivals=arrivals)
            for stop, arrivals in zip(configured_stops, arrivals_by_stop)
        ],
    )


def _find_stop(stop_id: str, stops: list[BusStop]) -> BusStop:
    for stop in stops:
        if stop.id == stop_id:
            return stop
    raise HTTPException(status_code=404, detail=f"Unknown stop: {stop_id}")


def _stop_response(stop: BusStop) -> StopResponse:
    return StopResponse(id=stop.id, name=stop.name, routes=list(stop.routes))
