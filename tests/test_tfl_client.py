from datetime import datetime, timedelta, timezone

from traffic_live_tracker.config import BusStop
from traffic_live_tracker.tfl_client import normalize_arrivals


def test_normalize_arrivals_sorts_and_filters_routes():
    stop = BusStop(id="490000091A", name="Example Stop", routes=("12",))
    later = datetime.now(timezone.utc) + timedelta(minutes=9)
    sooner = datetime.now(timezone.utc) + timedelta(minutes=3)

    arrivals = normalize_arrivals(
        [
            {
                "lineName": "24",
                "destinationName": "Pimlico",
                "expectedArrival": sooner.isoformat(),
            },
            {
                "lineName": "12",
                "destinationName": "Dulwich Library",
                "expectedArrival": later.isoformat(),
                "platformName": "A",
                "vehicleId": "BUS123",
                "timestamp": sooner.isoformat(),
            },
            {
                "lineName": "12",
                "destinationName": "Oxford Circus",
                "expectedArrival": sooner.isoformat(),
            },
        ],
        stop,
    )

    assert [arrival.route for arrival in arrivals] == ["12", "12"]
    assert arrivals[0].destination == "Oxford Circus"
    assert arrivals[1].platform_name == "A"
    assert arrivals[1].vehicle_id == "BUS123"


def test_normalize_arrivals_skips_invalid_expected_arrival():
    stop = BusStop(id="490000091A", name="Example Stop")

    arrivals = normalize_arrivals(
        [{"lineName": "12", "destinationName": "Nowhere", "expectedArrival": "bad"}],
        stop,
    )

    assert arrivals == []
