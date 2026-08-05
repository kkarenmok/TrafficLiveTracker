from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class StopResponse(BaseModel):
    id: str
    name: str
    routes: list[str] = Field(default_factory=list)


class StopCreate(BaseModel):
    id: str = Field(min_length=3, max_length=32)

    @field_validator("id")
    @classmethod
    def clean_id(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Stop id must contain at least three characters")
        return cleaned


class StopSearchResult(BaseModel):
    id: str
    name: str
    indicator: str | None = None
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
