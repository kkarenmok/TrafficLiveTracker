from datetime import datetime, timedelta, timezone

import httpx
import pytest

from traffic_live_tracker.config import BusStop
from traffic_live_tracker.main import app
from traffic_live_tracker.models import Arrival


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
