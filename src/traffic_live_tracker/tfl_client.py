from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from traffic_live_tracker.config import BusStop
from traffic_live_tracker.models import Arrival, StopSearchResult


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
        payload = await self._get_json(url)

        if not isinstance(payload, list):
            raise TflClientError(f"TfL returned an unexpected payload for stop {stop.id}")

        return normalize_arrivals(payload, stop)

    async def search_stop_points(
        self, query: str, limit: int = 8, modes: str | None = "bus"
    ) -> list[StopSearchResult]:
        params = {"maxResults": min(limit, 8)}
        if modes:
            params["modes"] = modes
        payload = await self._get_json(
            f"{self.base_url}/StopPoint/Search/{quote(query, safe='')}",
            params=params,
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
            raise TflClientError("TfL returned an unexpected stop search payload")

        parent_ids = [
            str(match.get("id", "")).strip()
            for match in payload["matches"]
            if isinstance(match, dict) and str(match.get("id", "")).strip()
        ]
        families = await asyncio.gather(*(self.stop_point(stop_id) for stop_id in parent_ids))
        results: list[StopSearchResult] = []
        seen: set[str] = set()
        for family in families:
            candidates = family.get("children") or [family]
            if not isinstance(candidates, list):
                continue
            for candidate in candidates:
                result = normalize_stop_point(candidate)
                if result is None or result.id in seen:
                    continue
                seen.add(result.id)
                results.append(result)
                if len(results) >= limit:
                    return results
        return results

    async def stop_point(self, stop_id: str) -> dict[str, Any]:
        payload = await self._get_json(f"{self.base_url}/StopPoint/{stop_id}")
        if not isinstance(payload, dict):
            raise TflClientError(f"TfL returned an unexpected payload for stop {stop_id}")
        return payload

    async def bus_stop_for_id(self, stop_id: str) -> BusStop:
        result = normalize_stop_point(await self.stop_point(stop_id))
        if result is None:
            raise TflClientError(f"TfL stop {stop_id} is not an individual bus stop")
        suffix = f" {result.indicator}" if result.indicator else ""
        return BusStop(id=result.id, name=f"{result.name}{suffix}", routes=())

    async def _get_json(
        self, url: str, params: dict[str, Any] | None = None
    ) -> Any:
        request_params = dict(params or {})
        if self.app_key:
            request_params["app_key"] = self.app_key

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, params=request_params or None)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TflClientError(
                f"TfL returned {exc.response.status_code} for {url}"
            ) from exc
        except httpx.HTTPError as exc:
            raise TflClientError(f"Could not reach TfL: {exc}") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise TflClientError("TfL returned invalid JSON") from exc


def normalize_stop_point(payload: Any) -> StopSearchResult | None:
    if not isinstance(payload, dict):
        return None
    modes = payload.get("modes") or []
    # normalize modes to lowercase strings for checking
    modes_lc = [str(m).casefold() for m in modes if isinstance(m, str)]
    if not modes_lc:
        return None
    stop_type = str(payload.get("stopType") or "")
    # If the search/modes include 'bus', keep the original strict bus stopType check
    if any("bus" in m for m in modes_lc):
        if stop_type != "NaptanPublicBusCoachTram":
            return None
    else:
        # Accept common rail-related modes (tube, elizabeth, overground, national-rail, dlr, tram)
        allowed_keywords = (
            "rail",
            "tube",
            "elizabeth",
            "overground",
            "national-rail",
            "dlr",
            "tram",
        )
        if not any(any(kw in m for kw in allowed_keywords) for m in modes_lc):
            return None
    stop_id = str(payload.get("naptanId") or payload.get("id") or "").strip()
    name = str(payload.get("commonName") or "").strip()
    if not stop_id or not name:
        return None
    lines = payload.get("lines") or []
    routes = [
        str(line.get("name") or line.get("id") or "").strip()
        for line in lines
        if isinstance(line, dict) and str(line.get("name") or line.get("id") or "").strip()
    ]
    indicator = _optional_string(payload.get("indicator") or payload.get("stopLetter"))
    if indicator and not indicator.casefold().startswith("stop"):
        indicator = f"Stop {indicator}"
    return StopSearchResult(id=stop_id, name=name, indicator=indicator, routes=routes)


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
