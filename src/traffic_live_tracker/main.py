from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from traffic_live_tracker.config import BusStop, load_settings, load_stops
from traffic_live_tracker.models import DashboardResponse, DashboardStop, StopResponse, utc_now
from traffic_live_tracker.tfl_client import TflClient, TflClientError

app = FastAPI(
    title="TrafficLiveTracker",
    description="Local API for live London bus arrivals.",
    version="0.1.0",
)


def get_settings():
    return load_settings()


def get_stops() -> list[BusStop]:
    settings = get_settings()
    try:
        return load_stops(settings.stops_config_path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
