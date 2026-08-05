from datetime import datetime, timedelta, timezone

import httpx
import pytest

from traffic_live_tracker.config import BusStop
from traffic_live_tracker.main import app
from traffic_live_tracker.models import Arrival, StopSearchResult


class FakeTflClient:
    async def arrivals_for_stop(self, stop: BusStop):
        return [
            Arrival(
                stop_id=stop.id,
                stop_name=stop.name,
                route="12",
                destination="Dulwich Library",
                expected_arrival=datetime.now(timezone.utc) + timedelta(minutes=4),
                minutes_until_arrival=4,
            )
        ]

    async def search_bus_stops(self, query: str, limit: int = 8):
        return [
            StopSearchResult(
                id="490000001A",
                name="Example Road",
                indicator="Stop A",
                routes=["12"],
            )
        ]

    async def search_stop_points(self, query: str, limit: int = 8, modes: str | None = "bus"):
        return await self.search_bus_stops(query, limit)

    async def bus_stop_for_id(self, stop_id: str):
        return BusStop(id=stop_id, name="Example Road Stop A")


class FakeStopRepository:
    def __init__(self):
        self.stops = [BusStop(id="490003314R", name="Default Stop R")]

    def list_stops(self):
        return list(self.stops)

    def add_stop(self, stop: BusStop):
        self.stops.append(stop)
        return stop

    def remove_stop(self, stop_id: str):
        for stop in self.stops:
            if stop.id == stop_id:
                self.stops.remove(stop)
                return stop
        return None


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_stops_and_dashboard(monkeypatch):
    monkeypatch.setattr(
        "traffic_live_tracker.main.get_stops",
        lambda: [BusStop(id="490000091A", name="Example Stop", routes=("12",))],
    )
    monkeypatch.setattr("traffic_live_tracker.main.get_tfl_client", lambda: FakeTflClient())

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        stops_response = await client.get("/stops")
        dashboard_response = await client.get("/dashboard")

    assert stops_response.status_code == 200
    assert stops_response.json() == [
        {"id": "490000091A", "name": "Example Stop", "routes": ["12"]}
    ]
    assert dashboard_response.status_code == 200
    body = dashboard_response.json()
    assert body["refresh_seconds"] == 30
    assert body["stops"][0]["arrivals"][0]["route"] == "12"


@pytest.mark.anyio
async def test_unknown_stop_returns_404(monkeypatch):
    monkeypatch.setattr("traffic_live_tracker.main.get_stops", lambda: [])

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/arrivals/missing")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_search_add_and_remove_stop(monkeypatch):
    repository = FakeStopRepository()
    monkeypatch.setattr("traffic_live_tracker.main.get_stop_repository", lambda: repository)
    monkeypatch.setattr("traffic_live_tracker.main.get_tfl_client", lambda: FakeTflClient())

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        search_response = await client.get("/stops/search", params={"q": "Example"})
        add_response = await client.post("/stops", json={"id": "490000001A"})
        remove_response = await client.delete("/stops/490000001A")

    assert search_response.status_code == 200
    assert search_response.json()[0]["indicator"] == "Stop A"
    assert add_response.status_code == 201
    assert remove_response.status_code == 200
    assert remove_response.json()["id"] == "490000001A"


@pytest.mark.anyio
async def test_stop_search_validates_minimum_query():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/stops/search", params={"q": "x"})

    assert response.status_code == 422


@pytest.mark.anyio
async def test_pages_origin_is_allowed_by_cors():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.options(
            "/stops",
            headers={
                "Origin": "https://kkarenmok.github.io",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://kkarenmok.github.io"
