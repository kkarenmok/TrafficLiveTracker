from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from traffic_live_tracker.config import BusStop
from traffic_live_tracker.models import Arrival


class TflClientError(RuntimeError):
    pass


class TflClient:
    def __init__(
        self,
        app_key: str | None,
        timeout_seconds: float = 10.0,
        base_url: str = "https://api.tfl.gov.uk",
    ) -> None:
        self.app_key = app_key
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url.rstrip("/")

    async def arrivals_for_stop(self, stop: BusStop) -> list[Arrival]:
        url = f"{self.base_url}/StopPoint/{stop.id}/Arrivals"
        params = {"app_key": self.app_key} if self.app_key else None

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TflClientError(
                f"TfL returned {exc.response.status_code} for stop {stop.id}"
            ) from exc
        except httpx.HTTPError as exc:
            raise TflClientError(f"Could not reach TfL for stop {stop.id}: {exc}") from exc

        payload = response.json()
        if not isinstance(payload, list):
            raise TflClientError(f"TfL returned an unexpected payload for stop {stop.id}")

        return normalize_arrivals(payload, stop)


def normalize_arrivals(payload: list[dict[str, Any]], stop: BusStop) -> list[Arrival]:
    route_filter = {route.casefold() for route in stop.routes}
    arrivals: list[Arrival] = []

    for item in payload:
        route = str(item.get("lineName") or item.get("lineId") or "").strip()
        if not route:
            continue
        if route_filter and route.casefold() not in route_filter:
            continue

        expected_arrival = _parse_datetime(item.get("expectedArrival"))
        if expected_arrival is None:
            continue

        arrivals.append(
            Arrival(
                stop_id=stop.id,
                stop_name=stop.name,
                route=route,
                destination=str(item.get("destinationName") or "Unknown destination"),
                expected_arrival=expected_arrival,
                minutes_until_arrival=max(
                    0,
                    round((expected_arrival - datetime.now(timezone.utc)).total_seconds() / 60),
                ),
                platform_name=_optional_string(item.get("platformName")),
                vehicle_id=_optional_string(item.get("vehicleId")),
                source_timestamp=_parse_datetime(item.get("timestamp")),
            )
        )

    return sorted(arrivals, key=lambda arrival: arrival.expected_arrival)


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
