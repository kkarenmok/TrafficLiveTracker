from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class StopResponse(BaseModel):
    id: str
    name: str
    routes: list[str] = Field(default_factory=list)


class Arrival(BaseModel):
    stop_id: str
    stop_name: str
    route: str
    destination: str
    expected_arrival: datetime
    minutes_until_arrival: int
    platform_name: str | None = None
    vehicle_id: str | None = None
    source_timestamp: datetime | None = None


class DashboardStop(BaseModel):
    stop: StopResponse
    arrivals: list[Arrival]


class DashboardResponse(BaseModel):
    refresh_seconds: int
    generated_at: datetime
    stops: list[DashboardStop]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
